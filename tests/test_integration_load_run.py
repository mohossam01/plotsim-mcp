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
    # ``config_parsed`` is the builder-shape sidecar — it must carry the
    # builder vocabulary the caller authored against, not the engine-shape
    # keys plotsim's interpreter produces (``entities``, ``archetypes``,
    # ``time_window``).
    parsed = envelope["config_parsed"]
    assert isinstance(parsed, dict)
    assert "unit" in parsed
    assert "segments" in parsed
    assert "window" in parsed
    assert "metrics" in parsed
    # 5 entities → 5 archetype assignments in the manifest summary.
    assert envelope["manifest_summary"]["archetype_assignments_total"] == 5
    assert envelope["validation_ok"] is True
    # tables_written includes both the engine artifacts and the sidecar.
    assert "config.yaml" in envelope["tables_written"]
    assert "config.userinput.yaml" in envelope["tables_written"]
    assert "manifest.json" in envelope["tables_written"]
    assert "validation_report.txt" in envelope["tables_written"]


def test_load_run_config_yaml_round_trips_through_validate_config() -> None:
    """The modify-and-rerun loop's load-bearing claim: the YAML
    ``load_run`` returns can be fed back to ``validate_config`` (and
    on to ``create_dataset``) without coercion.
    """
    from plotsim_mcp.tools.validate_config import validate_config_payload

    created = create_dataset_payload(_TINY_CONFIG, seed=131)
    envelope = load_run_payload(created["run_id"])

    validated = validate_config_payload(envelope["config_yaml"])
    assert validated["valid"] is True, (
        f"builder-shape sidecar must round-trip through validate_config; "
        f"got {validated!r}"
    )

    # And the second create_dataset call against the same builder-shape
    # YAML produces another valid run — the full modify-and-rerun loop.
    rerun = create_dataset_payload(envelope["config_yaml"], seed=137)
    assert rerun["run_id"]
    assert rerun["validation_summary"]["ok"] is True


def test_load_run_falls_back_to_engine_shape_when_sidecar_absent() -> None:
    """A run with no sidecar (the legacy artifact path) still loads — the
    fallback engine-shape ``config.yaml`` surfaces in ``config_yaml`` /
    ``config_parsed`` even though it won't round-trip through the builder
    tools.
    """
    created = create_dataset_payload(_TINY_CONFIG, seed=139)
    run_dir = Path(created["output_dir"])
    sidecar = run_dir / "config.userinput.yaml"
    assert sidecar.is_file(), "sidecar must exist before we delete it"
    sidecar.unlink()

    envelope = load_run_payload(created["run_id"])
    parsed = envelope["config_parsed"]
    assert isinstance(parsed, dict)
    # Engine-shape: ``entities`` and ``archetypes`` are populated by the
    # interpreter; ``segments`` / ``unit`` do not appear here.
    assert "entities" in parsed
    assert "segments" not in parsed
