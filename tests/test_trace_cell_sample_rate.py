"""Regression for lock #1 — ``trace_cell`` under ``trajectory_sample_rate
< 1.0`` re-derives the trajectory from seed + config and returns a
bit-identical realized cell value.

The lock contract: when the manifest only sampled a subset of entity
trajectories, traces for non-sampled entities must NOT degrade to
interpolation. ``trace_metric_cell`` re-runs
``generate_tables_with_state`` internally so the realized cell value is
guaranteed to match the actual fact-table value either way; this test
locks that contract by asserting both ``trace_source ==
"rederived_from_seed"`` AND ``realized_value == table cell value`` for a
deliberately non-sampled entity.

``trajectory_sample_rate`` lives on the engine config (not the builder
input), so the test goes through ``plotsim.create`` → ``model_copy`` to
set the rate → ``plotsim.run`` rather than via ``create_dataset``. Same
sandbox conventions otherwise; the resulting run reaches every
inspection tool through ``runs.resolve(...)``.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import plotsim
from plotsim_mcp import runs
from plotsim_mcp.tools.trace_cell import _load_config, trace_cell_payload


_LARGER_CONFIG: dict = {
    # 20 entities so ceil(20 * 0.1) = 2 sampled, 18 not sampled — plenty of
    # non-sampled rows to address.
    "about": "trace_cell sample-rate regression fixture",
    "unit": "customer",
    "window": {"start": "2024-01", "end": "2024-04", "every": "monthly"},
    "segments": [{"name": "cohort_a", "count": 20, "archetype": "growth"}],
    "metrics": [
        {"name": "engagement", "type": "score", "polarity": "positive"}
    ],
    "seed": 113,
}


@pytest.fixture(autouse=True)
def _isolated_sandbox(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    monkeypatch.setenv(runs.ENV_VAR, str(tmp_path / "runs"))
    return tmp_path / "runs"


def _build_run_with_sampled_subset(sample_rate: float) -> tuple[str, Path]:
    """Generate a run with ``manifest.trajectory_sample_rate=sample_rate``.

    Uses ``model_copy(update=...)`` because the engine ``ManifestConfig``
    is frozen; otherwise we'd mutate in place. ``runs.allocate(...)``
    picks the sandbox directory so the resulting run reaches the
    standard inspection tools.
    """
    base = plotsim.create(**_LARGER_CONFIG)
    new_manifest = base.manifest.model_copy(
        update={"trajectory_sample_rate": sample_rate}
    )
    config = base.model_copy(update={"manifest": new_manifest})

    import yaml as _yaml

    canonical = _yaml.safe_dump(_LARGER_CONFIG, sort_keys=True)
    run_id = runs.generate_run_id(canonical, seed=_LARGER_CONFIG["seed"])
    run_dir = runs.allocate(run_id)
    plotsim.run(config, run_dir, seed=_LARGER_CONFIG["seed"])
    return run_id, run_dir


def _pick_metric_column(run_dir: Path) -> tuple[str, str]:
    from plotsim.config import MetricSource, parse_source

    config = _load_config(run_dir)
    for tbl in config.tables:
        if (
            getattr(tbl, "type", None) == "fact"
            and getattr(tbl, "grain", None) == "per_entity_per_period"
        ):
            for col in tbl.columns:
                parsed = parse_source(col.source)
                if isinstance(parsed, MetricSource):
                    return str(tbl.name), str(col.name)
    raise AssertionError("no per_entity_per_period fact table with metric column")


def test_trace_cell_under_low_sample_rate_uses_rederived_source() -> None:
    """With rate=0.1 on 20 entities, only ~2 entities are in trajectory_samples.

    Pick a row mapping to an entity ~mid-list so it's not in the sampled
    subset (the sampler takes the first ``ceil(n * rate)`` names in sorted
    order). ``trace_source`` must be ``"rederived_from_seed"`` for that
    entity.
    """
    run_id, run_dir = _build_run_with_sampled_subset(sample_rate=0.1)
    table, column = _pick_metric_column(run_dir)

    df = pd.read_csv(run_dir / f"{table}.csv")
    n_periods = len(df) // 20  # 20 entities in the fixture
    # Entity index 10 — well beyond the ~2-entity sampled subset.
    flat_idx = 10 * n_periods + 1

    envelope = trace_cell_payload(run_id, table, str(flat_idx), column)
    assert envelope["trace"]["trace_source"] == "rederived_from_seed"


def test_trace_cell_under_low_sample_rate_matches_engine_value_bit_for_bit() -> None:
    """Lock #1 contract — the rederived realized_value is bit-identical
    to what the engine itself produces for the same (config, seed,
    entity, period, metric).

    The CSV writer uses ``%.4f`` formatting so a CSV-roundtripped cell
    can't be the cross-check target — instead the assertion runs
    ``generate_tables_with_state`` in-memory against the same config +
    seed and compares the trace tool's full-precision realized_value to
    the engine's in-memory float. Any precision drift in the
    re-derivation path would surface here.
    """
    from plotsim.config import MetricSource, parse_source
    from plotsim.tables import generate_tables_with_state

    run_id, run_dir = _build_run_with_sampled_subset(sample_rate=0.1)
    table, column = _pick_metric_column(run_dir)
    config = _load_config(run_dir)

    # In-memory rerun — produces full-precision DataFrames that plotsim
    # itself wrote (lossily) to CSV. We compare against this canonical
    # value, not against the rounded CSV cell.
    tables, _state = generate_tables_with_state(
        config, np.random.default_rng(config.seed)
    )
    in_memory_df = tables[table]
    n_periods = len(in_memory_df) // 20

    entity_idx = 15
    period_index = 2
    flat_idx = entity_idx * n_periods + period_index
    engine_value = in_memory_df.iloc[flat_idx][column]

    envelope = trace_cell_payload(run_id, table, str(flat_idx), column)
    if pd.isna(engine_value):
        assert envelope["trace"]["realized_value"] is None
    else:
        # Bit-for-bit equality — re-derivation goes through the same code
        # path generate_tables_with_state uses, so the float bits must match.
        assert envelope["trace"]["realized_value"] == float(engine_value)


def test_trace_cell_at_full_sample_rate_can_source_from_manifest() -> None:
    """Sanity: with rate=1.0 every entity is sampled, so trace_source is
    ``"manifest"`` for any row.
    """
    run_id, run_dir = _build_run_with_sampled_subset(sample_rate=1.0)
    table, column = _pick_metric_column(run_dir)

    envelope = trace_cell_payload(run_id, table, "0", column)
    assert envelope["trace"]["trace_source"] == "manifest"
