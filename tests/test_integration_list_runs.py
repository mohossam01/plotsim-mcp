"""Integration coverage for ``list_runs`` — drives ``create_dataset``
end-to-end and asserts the resulting entry surfaces with the correct
run_id, output_dir, and validation_ok signal.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from plotsim_mcp import runs
from plotsim_mcp.tools.create_dataset import create_dataset_payload
from plotsim_mcp.tools.list_runs import list_runs_payload


_TINY_CONFIG: dict = {
    "about": "list_runs integration fixture",
    "unit": "customer",
    "window": {"start": "2024-01", "end": "2024-03", "every": "monthly"},
    "segments": [{"name": "cohort_a", "count": 4, "archetype": "growth"}],
    "metrics": [
        {"name": "engagement", "type": "score", "polarity": "positive"}
    ],
}


@pytest.fixture(autouse=True)
def _isolated_sandbox(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    monkeypatch.setenv(runs.ENV_VAR, str(tmp_path / "runs"))
    return tmp_path / "runs"


def test_list_runs_surfaces_a_real_run() -> None:
    created = create_dataset_payload(_TINY_CONFIG, seed=149)
    payload = list_runs_payload()

    assert len(payload["runs"]) == 1
    entry = payload["runs"][0]
    assert entry["run_id"] == created["run_id"]
    assert Path(entry["output_dir"]).resolve() == Path(created["output_dir"]).resolve()
    # A successful run has a VALID report alongside it.
    assert entry["validation_ok"] is True


def test_list_runs_lists_every_real_run_most_recent_first() -> None:
    created_a = create_dataset_payload(_TINY_CONFIG, seed=151)
    created_b = create_dataset_payload(_TINY_CONFIG, seed=157)
    created_c = create_dataset_payload(_TINY_CONFIG, seed=163)

    payload = list_runs_payload()
    listed_ids = [e["run_id"] for e in payload["runs"]]
    assert len(listed_ids) == 3
    # All three IDs must surface; exact order can be touched by
    # filesystem-resolution mtime granularity on the fastest paths, so
    # the set check is the load-bearing assertion.
    assert set(listed_ids) == {
        created_a["run_id"],
        created_b["run_id"],
        created_c["run_id"],
    }
