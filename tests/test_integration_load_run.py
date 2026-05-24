"""Integration coverage for ``load_run`` — runs ``create_dataset``
end-to-end then asserts the load_run envelope reflects what the engine
actually produced (config round-trips through yaml.safe_load,
validation report status surfaces, manifest summary counts agree with
the engine's manifest).
"""
from __future__ import annotations

from pathlib import Path

import pytest

from plotsim_mcp import runs
from plotsim_mcp.tools.create_dataset import create_dataset_payload
from plotsim_mcp.tools.load_run import load_run_payload


_TINY_CONFIG: dict = {
    "about": "load_run integration fixture",
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


def test_load_run_envelope_reflects_real_run() -> None:
    created = create_dataset_payload(_TINY_CONFIG, seed=127)
    envelope = load_run_payload(created["run_id"])

    assert envelope["run_id"] == created["run_id"]
    # The engine writes engine-shape YAML; the parsed dict must at least carry
    # the top-level sections plotsim is documented to emit.
    parsed = envelope["config_parsed"]
    assert isinstance(parsed, dict)
    assert "domain" in parsed
    assert "metrics" in parsed
    assert "entities" in parsed
    # 5 entities → 5 archetype assignments in the manifest summary.
    assert envelope["manifest_summary"]["archetype_assignments_total"] == 5
    assert envelope["validation_ok"] is True
    # tables_written includes the engine artifacts.
    assert "config.yaml" in envelope["tables_written"]
    assert "manifest.json" in envelope["tables_written"]
    assert "validation_report.txt" in envelope["tables_written"]
