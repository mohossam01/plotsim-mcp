"""Integration coverage for ``get_validation_report`` — runs
``create_dataset`` against a tiny config and asserts the returned report
text is the same bytes plotsim wrote to disk.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from plotsim_mcp import runs
from plotsim_mcp.tools.create_dataset import create_dataset_payload
from plotsim_mcp.tools.get_validation_report import get_validation_report_payload


_TINY_CONFIG: dict = {
    "about": "get_validation_report integration fixture",
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


def test_get_validation_report_matches_disk_bytes() -> None:
    created = create_dataset_payload(_TINY_CONFIG, seed=51)
    envelope = get_validation_report_payload(created["run_id"])
    on_disk = (Path(created["output_dir"]) / "validation_report.txt").read_text(
        encoding="utf-8"
    )
    assert envelope["report"] == on_disk
    assert envelope["ok"] is True
