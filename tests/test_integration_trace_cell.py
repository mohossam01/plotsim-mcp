"""Integration coverage for ``trace_cell`` — runs ``create_dataset``
end-to-end, discovers a per_entity_per_period fact table from the
written config, then asserts ``trace_cell`` returns lineage matching
the actual table cell value.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from plotsim_mcp import runs
from plotsim_mcp.tools.create_dataset import create_dataset_payload
from plotsim_mcp.tools.trace_cell import (
    _load_config,
    trace_cell_payload,
)


_TINY_CONFIG: dict = {
    "about": "trace_cell integration fixture",
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


def _pick_metric_column(run_dir: Path) -> tuple[str, str]:
    """Return ``(table_name, column_name)`` for the first per_entity_per_period
    fact table whose column is sourced from a metric.
    """
    from plotsim.config import MetricSource, parse_source

    config = _load_config(run_dir)
    for tbl in config.tables:
        if getattr(tbl, "type", None) != "fact":
            continue
        if getattr(tbl, "grain", None) != "per_entity_per_period":
            continue
        for col in tbl.columns:
            parsed = parse_source(col.source)
            if isinstance(parsed, MetricSource):
                return str(tbl.name), str(col.name)
    raise AssertionError("no per_entity_per_period fact table with metric column")


def test_trace_cell_returns_lineage_for_real_run() -> None:
    created = create_dataset_payload(_TINY_CONFIG, seed=83)
    run_dir = runs.resolve(created["run_id"])
    table, column = _pick_metric_column(run_dir)

    envelope = trace_cell_payload(created["run_id"], table, "0", column)
    assert envelope["run_id"] == created["run_id"]
    assert envelope["table"] == table
    assert envelope["column"] == column
    trace = envelope["trace"]
    assert isinstance(trace["archetype"], str)
    assert 0.0 <= trace["trajectory_position"] <= 1.0
    assert isinstance(trace["distribution"], str) and trace["distribution"]
    assert trace["trace_source"] in {"manifest", "rederived_from_seed"}


def test_trace_cell_realized_value_matches_table_cell() -> None:
    """The realized_value the tool reports must agree with the CSV cell.

    Engine values are full-precision floats; plotsim's CSV writer uses
    ``float_format="%.4f"`` (see plotsim/output.py:31), so the maximum
    abs error a round-trip-through-CSV cross-check can require is
    ``5e-5``. The tool reports the full-precision in-memory value (this
    is by design — the trajectory-first contract is "the realized value
    is reproducible from the trajectory position"); the CSV is a lossy
    side artifact.
    """
    created = create_dataset_payload(_TINY_CONFIG, seed=89)
    run_dir = runs.resolve(created["run_id"])
    table, column = _pick_metric_column(run_dir)

    # Pick a non-trivial row near the middle so the assertion isn't sensitive
    # to off-by-one at the edges.
    df = pd.read_csv(run_dir / f"{table}.csv")
    target_row = min(5, len(df) - 1)

    envelope = trace_cell_payload(
        created["run_id"], table, str(target_row), column
    )
    actual = df.iloc[target_row][column]
    if pd.isna(actual):
        assert envelope["trace"]["realized_value"] is None
    else:
        assert envelope["trace"]["realized_value"] == pytest.approx(
            float(actual), abs=1e-4
        )


def test_trace_cell_row_id_out_of_range_raises() -> None:
    from plotsim_mcp.tools.trace_cell import _RowNotFound

    created = create_dataset_payload(_TINY_CONFIG, seed=97)
    run_dir = runs.resolve(created["run_id"])
    table, column = _pick_metric_column(run_dir)

    with pytest.raises(_RowNotFound):
        trace_cell_payload(created["run_id"], table, "9999", column)


def test_trace_cell_unknown_column_raises_column_not_metric() -> None:
    from plotsim_mcp.tools.trace_cell import _ColumnNotMetric

    created = create_dataset_payload(_TINY_CONFIG, seed=101)
    run_dir = runs.resolve(created["run_id"])
    table, _ = _pick_metric_column(run_dir)

    with pytest.raises(_ColumnNotMetric):
        trace_cell_payload(
            created["run_id"], table, "0", "definitely_not_a_real_column"
        )
