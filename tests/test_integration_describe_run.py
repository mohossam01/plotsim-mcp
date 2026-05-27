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


def test_archetype_counts_keys_are_builder_shape_words() -> None:
    """``archetype_counts`` rolls up the manifest's per-segment instance
    names back to the user-authored archetype word via the
    ``config.userinput.yaml`` sidecar. Two segments sharing the same
    archetype word collapse into a single key.
    """
    cfg = {
        **_TINY_CONFIG,
        "segments": [
            {"name": "alpha_cohort", "count": 5, "archetype": "growth"},
            {"name": "beta_cohort", "count": 5, "archetype": "growth"},
        ],
    }
    created = create_dataset_payload(cfg, seed=43)
    summary = describe_run_payload(created["run_id"])["summary"]
    # 5 + 5 entities, all archetype "growth" — keys must surface as the
    # user-authored word, not the per-segment instance names.
    assert summary["archetype_counts"] == {"growth": 10}, (
        f"expected builder-shape archetype key 'growth'; got "
        f"{summary['archetype_counts']!r}"
    )


def test_describe_run_summary_keys_match_real_manifest_field_names() -> None:
    """Regression: the summarizer must read manifest field names that
    actually exist on plotsim's pydantic manifest classes
    (``TrajectorySample.entity``, ``EventFiring.table``,
    ``BridgeAssociationRecord.bridge``) — not the ``_id`` / ``_name``
    variants the hand-built unit fixtures used to encode. Drives an
    end-to-end run through the banking template so every count
    exercises a real-shape manifest written by the engine, with
    segment counts trimmed to keep the run fast.
    """
    # Trim every segment count without touching the window — the
    # banking template's archetypes carry transition periods (e.g.
    # 'flat > growth > spike_then_crash @ 8 @ 16') that require the
    # native 24-month window.
    overrides = {
        "segments.0.count": 4,
        "segments.1.count": 4,
        "segments.2.count": 4,
        "segments.3.count": 4,
        "segments.4.count": 4,
        "segments.5.count": 4,
    }
    created = create_dataset_payload("banking", seed=7, overrides=overrides)
    summary = describe_run_payload(created["run_id"])["summary"]

    # Trajectory sampling is on by default (rate 1.0); every entity in
    # the run contributes at least one TrajectorySample, so the unique
    # count must be > 0.
    assert summary["trajectory_sampled_entities"] > 0, (
        "trajectory_sampled_entities reads TrajectorySample.entity; a "
        "stale `entity_id` read would silently return 0 here."
    )

    # The banking template declares two event tables: evt_transaction
    # (proportional) and evt_default (threshold). Bucket keys must
    # match the configured event table names — not `"unknown"`.
    event_counts = summary["event_counts"]
    assert "unknown" not in event_counts, (
        f"event_counts read EventFiring.table; got buckets under "
        f"'unknown': {event_counts!r}"
    )
    assert "evt_transaction" in event_counts or "evt_default" in event_counts, (
        f"expected at least one banking event table in event_counts; got {event_counts!r}"
    )

    # The banking template declares one bridge: bridge_customer_product.
    bridge_counts = summary["bridge_association_counts"]
    assert "unknown" not in bridge_counts, (
        f"bridge_association_counts read BridgeAssociationRecord.bridge; "
        f"got buckets under 'unknown': {bridge_counts!r}"
    )
    assert "bridge_customer_product" in bridge_counts, (
        f"expected 'bridge_customer_product' bucket; got {bridge_counts!r}"
    )
