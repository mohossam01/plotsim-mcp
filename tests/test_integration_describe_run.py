"""Integration coverage for ``describe_run`` — runs ``create_dataset``
end-to-end then asserts the manifest summary reflects what the engine
actually generated.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from plotsim_mcp import runs
from plotsim_mcp.tools.create_dataset import create_dataset_payload
from plotsim_mcp.tools.describe_run import describe_run_payload


_TINY_CONFIG: dict = {
    "about": "describe_run integration fixture",
    "unit": "customer",
    "window": {"start": "2024-01", "end": "2024-03", "every": "monthly"},
    "segments": [{"name": "cohort_a", "count": 5, "archetype": "growth"}],
    "metrics": [
        {"name": "engagement", "type": "score", "polarity": "positive"}
    ],
}


@pytest.fixture(autouse=True)
def _isolated_sandbox(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    monkeypatch.setenv(runs.ENV_VAR, str(tmp_path / "runs"))
    return tmp_path / "runs"


def test_describe_run_summarizes_a_real_run() -> None:
    created = create_dataset_payload(_TINY_CONFIG, seed=41)
    described = describe_run_payload(created["run_id"])

    assert described["run_id"] == created["run_id"]
    assert described["manifest_path"] is not None
    summary = described["summary"]
    assert summary["seed"] == 41
    # 5 entities → 5 archetype assignments
    assert summary["archetype_assignments_total"] == 5
    assert "config.yaml" in described["tables"]
    assert "manifest.json" in described["tables"]
