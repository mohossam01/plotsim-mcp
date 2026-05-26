"""Unit coverage for ``describe_run`` — summarizer covers a hand-built
manifest dict; resolution layer raises ``RunNotFound`` for unknown ids
and returns the envelope for a real run dir.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from plotsim_mcp import runs
from plotsim_mcp.tools.describe_run import (
    _summarize_manifest,
    describe_run_payload,
)


@pytest.fixture(autouse=True)
def _isolated_sandbox(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    monkeypatch.setenv(runs.ENV_VAR, str(tmp_path / "runs"))
    return tmp_path / "runs"


def test_summarize_manifest_handles_empty_input() -> None:
    summary = _summarize_manifest({})
    assert summary["archetype_assignments_total"] == 0
    assert summary["event_counts"] == {}
    assert summary["correlation_phase_count"] == 0
    assert summary["bridges"] == []


def test_summarize_manifest_counts_archetypes_and_events() -> None:
    # Field names mirror the pydantic classes in ``plotsim/manifest.py``:
    # ``EntityArchetypeAssignment.entity``, ``TrajectorySample.entity``,
    # ``EventFiring.table``, ``BridgeAssociationRecord.bridge``.
    manifest = {
        "schema_version": "1.11",
        "seed": 7,
        "config_sha256": "abc123",
        "archetype_assignments": [
            {"entity": "e0", "archetype": "growth"},
            {"entity": "e1", "archetype": "growth"},
            {"entity": "e2", "archetype": "decline"},
        ],
        "trajectory_samples": [
            {"entity": "e0", "period_index": 0, "position": 0.1},
            {"entity": "e1", "period_index": 0, "position": 0.2},
        ],
        "event_firings": [
            {"table": "churn", "entity": "e2", "period_indices": [5]},
            {"table": "churn", "entity": "e3", "period_indices": [6]},
            {"table": "signup", "entity": "e4", "period_indices": [1]},
        ],
        "treatment_cohorts": [{"label": "control"}, {"label": "treated"}],
        "correlation_phases": [{"phase_index": 0}, {"phase_index": 1}],
        "bridges": [{"name": "user_team"}],
        "bridge_associations": [
            {"bridge": "user_team", "entity": "e0", "targets": [], "cardinality": 0}
        ] * 12,
    }
    summary = _summarize_manifest(manifest)
    assert summary["archetype_counts"] == {"growth": 2, "decline": 1}
    assert summary["event_counts"] == {"churn": 2, "signup": 1}
    assert summary["trajectory_sampled_entities"] == 2
    assert summary["treatment_cohorts"] == ["control", "treated"]
    assert summary["correlation_phase_count"] == 2
    assert summary["bridges"] == ["user_team"]
    assert summary["bridge_association_counts"] == {"user_team": 12}


def test_describe_run_payload_returns_envelope_for_real_dir(
    _isolated_sandbox: Path,
) -> None:
    rid = "20260524T000000Z-describ1"
    run_dir = runs.allocate(rid)
    manifest = {
        "schema_version": "1.11",
        "seed": 1,
        "config_sha256": "xyz",
        "archetype_assignments": [{"entity": "e0", "archetype": "growth"}],
    }
    (run_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (run_dir / "config.yaml").write_text("about: x", encoding="utf-8")
    (run_dir / "users.csv").write_text("id\n1\n", encoding="utf-8")

    envelope = describe_run_payload(rid)
    assert envelope["run_id"] == rid
    assert envelope["manifest_path"] is not None
    assert envelope["manifest_path"].endswith("manifest.json")
    assert set(envelope["tables"]) == {"manifest.json", "config.yaml", "users.csv"}
    assert envelope["summary"]["archetype_assignments_total"] == 1


def test_describe_run_payload_handles_missing_manifest(
    _isolated_sandbox: Path,
) -> None:
    rid = "20260524T000000Z-nomanifest"
    run_dir = runs.allocate(rid)
    (run_dir / "config.yaml").write_text("about: x", encoding="utf-8")

    envelope = describe_run_payload(rid)
    assert envelope["manifest_path"] is None
    assert envelope["summary"]["archetype_assignments_total"] == 0


def test_describe_run_payload_unknown_run_raises() -> None:
    with pytest.raises(runs.RunNotFound):
        describe_run_payload("20260524T000000Z-missing0")
