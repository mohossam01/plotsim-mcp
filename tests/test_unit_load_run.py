"""Unit coverage for ``load_run`` — payload reads the run's config.yaml
verbatim, parses it through ``yaml.safe_load``, and remixes
``describe_run`` + ``get_validation_report`` outputs into a single
envelope. Unknown run ids raise :class:`runs.RunNotFound`.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from plotsim_mcp import runs
from plotsim_mcp.tools.load_run import load_run_payload


@pytest.fixture(autouse=True)
def _isolated_sandbox(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    monkeypatch.setenv(runs.ENV_VAR, str(tmp_path / "runs"))
    return tmp_path / "runs"


def _write_minimal_run(rid: str) -> Path:
    run_dir = runs.allocate(rid)
    (run_dir / "config.yaml").write_text("about: synthetic\nseed: 1\n", encoding="utf-8")
    manifest = {
        "schema_version": "1.11",
        "seed": 1,
        "config_sha256": "abc",
        "archetype_assignments": [
            {"entity": "e0", "archetype": "growth"},
        ],
    }
    (run_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (run_dir / "validation_report.txt").write_text(
        "Plotsim Validation Report\n==========================\nGenerated: x\n"
        "Errors: 0 | Warnings: 0 | Total: 0\nStatus: VALID\n",
        encoding="utf-8",
    )
    (run_dir / "users.csv").write_text("id\n1\n", encoding="utf-8")
    return run_dir


def test_load_run_returns_combined_envelope() -> None:
    rid = "20260524T000000Z-loadrun1"
    _write_minimal_run(rid)
    envelope = load_run_payload(rid)
    assert envelope["run_id"] == rid
    assert "about: synthetic" in envelope["config_yaml"]
    assert envelope["config_parsed"] == {"about": "synthetic", "seed": 1}
    assert envelope["validation_ok"] is True
    assert envelope["manifest_summary"]["archetype_assignments_total"] == 1
    assert "users.csv" in envelope["tables_written"]


def test_load_run_handles_missing_manifest_and_report() -> None:
    rid = "20260524T000000Z-loadrun2"
    run_dir = runs.allocate(rid)
    (run_dir / "config.yaml").write_text("about: minimal\n", encoding="utf-8")

    envelope = load_run_payload(rid)
    assert envelope["config_parsed"] == {"about": "minimal"}
    assert envelope["validation_ok"] is False
    assert envelope["manifest_summary"]["archetype_assignments_total"] == 0
    assert envelope["tables_written"] == ["config.yaml"]


def test_load_run_handles_empty_config_yaml() -> None:
    rid = "20260524T000000Z-loadrun3"
    run_dir = runs.allocate(rid)
    (run_dir / "config.yaml").write_text("", encoding="utf-8")
    envelope = load_run_payload(rid)
    assert envelope["config_yaml"] == ""
    assert envelope["config_parsed"] == {}


def test_load_run_unknown_run_raises() -> None:
    with pytest.raises(runs.RunNotFound):
        load_run_payload("20260524T000000Z-missingX")
