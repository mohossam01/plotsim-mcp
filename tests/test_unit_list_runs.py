"""Unit coverage for ``list_runs`` — payload assembly against a
fixture-populated sandbox; field shape, sort order, and the
``validation_ok`` tri-state (True / False / None) all asserted here so
the integration test can focus on real-run plumbing.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from plotsim_mcp import runs
from plotsim_mcp.tools.list_runs import list_runs_payload


@pytest.fixture(autouse=True)
def _isolated_sandbox(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    monkeypatch.setenv(runs.ENV_VAR, str(tmp_path / "runs"))
    return tmp_path / "runs"


def _write_report(run_dir: Path, *, ok: bool) -> None:
    status = "VALID" if ok else "INVALID"
    (run_dir / "validation_report.txt").write_text(
        "Plotsim Validation Report\n==========================\n"
        f"Errors: {0 if ok else 1} | Warnings: 0 | Total: {0 if ok else 1}\n"
        f"Status: {status}\n",
        encoding="utf-8",
    )


def test_empty_sandbox_returns_empty_runs_list(_isolated_sandbox: Path) -> None:
    # Touching the sandbox via the tool — empty dir, no entries.
    payload = list_runs_payload()
    assert payload == {"runs": []}


def test_entry_shape_carries_all_required_fields(_isolated_sandbox: Path) -> None:
    rid = "20260524T000000Z-listrun1"
    run_dir = runs.allocate(rid)
    _write_report(run_dir, ok=True)

    payload = list_runs_payload()
    assert "runs" in payload
    assert len(payload["runs"]) == 1
    entry = payload["runs"][0]
    assert set(entry.keys()) == {"run_id", "output_dir", "modified_at", "validation_ok"}
    assert entry["run_id"] == rid
    assert Path(entry["output_dir"]).resolve() == run_dir.resolve()
    # ISO 8601 UTC with Z suffix — no timezone offset, no microseconds.
    assert entry["modified_at"].endswith("Z")
    assert "T" in entry["modified_at"]
    assert entry["validation_ok"] is True


def test_validation_ok_is_false_for_invalid_report(_isolated_sandbox: Path) -> None:
    rid = "20260524T000000Z-listrun2"
    run_dir = runs.allocate(rid)
    _write_report(run_dir, ok=False)
    entry = list_runs_payload()["runs"][0]
    assert entry["validation_ok"] is False


def test_validation_ok_is_none_when_report_absent(_isolated_sandbox: Path) -> None:
    # A run dir with no validation_report.txt — list_runs must surface
    # the entry with validation_ok=None rather than False, so callers
    # can distinguish "haven't validated" from "validation failed."
    rid = "20260524T000000Z-listrun3"
    runs.allocate(rid)
    entry = list_runs_payload()["runs"][0]
    assert entry["validation_ok"] is None


def test_entries_sorted_by_modified_at_descending(_isolated_sandbox: Path) -> None:
    import time

    # Allocate three runs with explicit mtime nudges so the sort order
    # is deterministic on platforms whose iterdir ordering is filesystem-
    # native (Windows is not guaranteed-sorted).
    rids = [
        "20260524T000000Z-older001",
        "20260524T000000Z-middle01",
        "20260524T000000Z-newer001",
    ]
    dirs = [runs.allocate(r) for r in rids]
    # Forward bias the mtimes so 'newer' really is newer.
    base = time.time()
    import os

    for i, d in enumerate(dirs):
        os.utime(d, (base + i, base + i))

    payload = list_runs_payload()
    ordered_ids = [e["run_id"] for e in payload["runs"]]
    assert ordered_ids == list(reversed(rids))


def test_non_directory_entries_are_skipped(_isolated_sandbox: Path) -> None:
    # A stray file in the sandbox root (e.g. an operator's note) must
    # not surface as a fake run entry.
    rid = "20260524T000000Z-listrun4"
    runs.allocate(rid)
    (runs.sandbox_root() / "operator-note.txt").write_text(
        "ignore me", encoding="utf-8"
    )
    payload = list_runs_payload()
    assert {e["run_id"] for e in payload["runs"]} == {rid}
