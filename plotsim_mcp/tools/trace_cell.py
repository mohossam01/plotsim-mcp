"""``trace_cell`` — reconstruct the full pipeline trace for one fact-table cell.

Wraps :func:`plotsim.debug.trace_metric_cell`. The tool resolves ``run_id``
to its sandbox directory, loads the run's engine-shape ``config.yaml``,
locates the row identified by ``row_id`` in ``<run_dir>/<table>.<ext>``,
maps the supplied ``column`` back to its metric source, and asks
``plotsim.debug`` to reconstruct the trajectory → distribution → noise →
realized-cell chain.

Lock #1 — ``trace_source`` semantics. When the run's manifest only
sampled a subset of entity trajectories (``trajectory_sample_rate <
1.0``) and the target entity is NOT in the sampled set, the trace is
sourced from a seed+config re-derivation rather than the manifest.
``trace_metric_cell`` already re-runs ``generate_tables_with_state``
internally so the realized cell value is bit-identical to the actual
fact-table value either way — the ``trace_source`` field documents which
path was authoritative for the trajectory position the trace reports.

Row addressing. Only ``per_entity_per_period`` fact tables are
supported in v1. Row order in those tables is entity-major, period-minor
(documented in §7 of the acceptance notebook and asserted in
``plotsim.debug._resolve_realized_cell``), so a flat integer ``row_id``
divmods cleanly into ``(entity_idx, period_index)``. Other grains have
no single (entity, period) axis pair and refuse with
``plotsim.trace.column_not_metric``.
"""
from __future__ import annotations

import json
import traceback as _traceback
import uuid
import warnings
from pathlib import Path
from typing import Any

import pandas as pd
from mcp.server.fastmcp import FastMCP

from plotsim_mcp import runs
from plotsim_mcp.errors import CODE_INTERNAL, CODE_RUN_NOT_FOUND, ToolError


TOOL_NAME = "trace_cell"
TOOL_DESCRIPTION = (
    "Reconstruct the full pipeline trace for one fact-table cell. Returns "
    "{run_id, table, row_id, column, trace} where trace carries the "
    "archetype, trajectory_position, distribution family, noise realization, "
    "realized cell value, and trace_source ('manifest' or "
    "'rederived_from_seed'). Use create_dataset to produce a run_id then "
    "inspect a fact table to pick (table, row_id, column). row_id is the "
    "zero-based integer row index in the table file."
)

CODE_ROW_NOT_FOUND = "plotsim.trace.row_not_found"
CODE_COLUMN_NOT_METRIC = "plotsim.trace.column_not_metric"
CODE_ENTITY_NOT_FOUND = "plotsim.trace.entity_not_found"

_CONFIG_FILENAME = "config.yaml"
_MANIFEST_FILENAME = "manifest.json"
_TABLE_EXTS = (".csv", ".parquet", ".jsonl")


class _RowNotFound(LookupError):
    """Internal — raised when ``row_id`` does not index a row."""


class _ColumnNotMetric(LookupError):
    """Internal — raised when ``column`` does not name a metric source."""


class _EntityNotFound(LookupError):
    """Internal — raised when the derived entity_idx is past ``config.entities``."""


def _load_config(run_dir: Path) -> Any:
    from plotsim.config import PlotsimConfig

    config_path = run_dir / _CONFIG_FILENAME
    if not config_path.is_file():
        raise _RowNotFound(
            f"run directory missing {_CONFIG_FILENAME}; cannot reconstruct config"
        )
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return PlotsimConfig.from_yaml(config_path)


def _find_table_file(run_dir: Path, table: str) -> Path:
    for ext in _TABLE_EXTS:
        candidate = run_dir / f"{table}{ext}"
        if candidate.is_file():
            return candidate
    raise _RowNotFound(
        f"no file named {table!r} with a supported extension "
        f"({', '.join(_TABLE_EXTS)}) in the run directory"
    )


def _read_table(path: Path) -> pd.DataFrame:
    ext = path.suffix.lower()
    if ext == ".csv":
        return pd.read_csv(path)
    if ext == ".parquet":
        return pd.read_parquet(path)
    if ext == ".jsonl":
        return pd.read_json(path, lines=True)
    raise _RowNotFound(f"unsupported table extension: {ext}")


def _table_decl_for(config: Any, table_name: str) -> Any:
    for tbl in config.tables:
        if tbl.name == table_name:
            return tbl
    return None


def _metric_for_column(table_decl: Any, column: str) -> str:
    from plotsim.config import MetricSource, parse_source

    for col in table_decl.columns:
        if col.name != column:
            continue
        parsed = parse_source(col.source)
        if isinstance(parsed, MetricSource):
            return str(parsed.metric)
        raise _ColumnNotMetric(
            f"column {column!r} in table {table_decl.name!r} is sourced from "
            f"{type(parsed).__name__}, not a metric"
        )
    raise _ColumnNotMetric(
        f"column {column!r} not found in table {table_decl.name!r}"
    )


def _resolve_entity_and_period(
    config: Any,
    table_decl: Any,
    df: pd.DataFrame,
    row_id: str,
) -> tuple[str, int]:
    """Map ``row_id`` to ``(entity_name, period_index)`` for the target table.

    Only ``per_entity_per_period`` is supported — the engine writes those
    rows in entity-major, period-minor order so ``divmod(flat_idx,
    n_periods)`` recovers the original coordinates exactly. ``n_periods``
    is inferred from ``len(df) // len(config.entities)`` rather than the
    manifest so trace_cell works on runs whose manifest was disabled.
    """
    grain = getattr(table_decl, "grain", None)
    if grain != "per_entity_per_period":
        raise _ColumnNotMetric(
            f"trace_cell only supports per_entity_per_period grain; "
            f"table {table_decl.name!r} has grain {grain!r}"
        )
    try:
        flat_idx = int(row_id)
    except (TypeError, ValueError) as exc:
        raise _RowNotFound(
            f"row_id {row_id!r} is not an integer index"
        ) from exc
    if flat_idx < 0 or flat_idx >= len(df):
        raise _RowNotFound(
            f"row_id {flat_idx} outside table {table_decl.name!r} "
            f"row count {len(df)}"
        )
    entity_count = len(config.entities)
    if entity_count == 0:
        raise _EntityNotFound("config declares no entities")
    n_periods = max(len(df) // entity_count, 1)
    entity_idx, period_index = divmod(flat_idx, n_periods)
    if entity_idx >= entity_count:
        raise _EntityNotFound(
            f"row_id {flat_idx} maps to entity_idx {entity_idx} but config "
            f"has only {entity_count} entities"
        )
    return str(config.entities[entity_idx].name), int(period_index)


def _trace_source_for(manifest_path: Path, entity_name: str) -> str:
    """Return ``'manifest'`` iff the entity's trajectory is in the manifest.

    Manifest absence, parse failure, missing ``trajectory_samples``
    section, or entity not in the sampled subset all collapse to
    ``'rederived_from_seed'``. The semantics: "did the manifest carry
    enough state to source this trace, or did we fall back to running
    the engine again."
    """
    if not manifest_path.is_file():
        return "rederived_from_seed"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return "rederived_from_seed"
    samples = manifest.get("trajectory_samples", []) or []
    for s in samples:
        if isinstance(s, dict) and s.get("entity") == entity_name:
            return "manifest"
    return "rederived_from_seed"


def trace_cell_payload(
    run_id: str,
    table: str,
    row_id: str,
    column: str,
) -> dict[str, Any]:
    """Return the trace envelope; raise typed exceptions on failure.

    Exceptions raised here are caught by the wrapper in ``register`` and
    translated into ``ToolError`` envelopes. Splitting payload-shaping
    from wire-error formatting keeps the function callable directly from
    unit tests.
    """
    from plotsim.debug import (
        EntityNotFound as _PlotsimEntityNotFound,
        MetricNotFound as _PlotsimMetricNotFound,
        PeriodOutOfRange as _PlotsimPeriodOutOfRange,
        trace_metric_cell,
    )

    run_dir = runs.resolve(run_id)
    config = _load_config(run_dir)

    table_decl = _table_decl_for(config, table)
    if table_decl is None or getattr(table_decl, "type", None) != "fact":
        raise _ColumnNotMetric(
            f"table {table!r} is not a fact table in the run's config"
        )
    metric_name = _metric_for_column(table_decl, column)

    table_path = _find_table_file(run_dir, table)
    df = _read_table(table_path)
    entity_name, period_index = _resolve_entity_and_period(
        config, table_decl, df, row_id
    )

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        try:
            trace = trace_metric_cell(
                config,
                entity_name,
                period_index,
                metric_name,
                seed=config.seed,
            )
        except _PlotsimEntityNotFound as exc:
            raise _EntityNotFound(str(exc)) from exc
        except _PlotsimPeriodOutOfRange as exc:
            raise _RowNotFound(str(exc)) from exc
        except _PlotsimMetricNotFound as exc:
            raise _ColumnNotMetric(str(exc)) from exc

    if trace.noised_value is not None and trace.correlated_draw is not None:
        noise_realization: float | None = float(trace.noised_value) - float(
            trace.correlated_draw
        )
    else:
        noise_realization = None

    manifest_path = run_dir / _MANIFEST_FILENAME
    source = _trace_source_for(manifest_path, entity_name)

    realized_value: float | None = (
        float(trace.realized_cell) if trace.realized_cell is not None else None
    )

    return {
        "run_id": run_id,
        "table": table,
        "row_id": row_id,
        "column": column,
        "trace": {
            "archetype": str(trace.archetype_name),
            "trajectory_position": float(trace.trajectory_position),
            "distribution": str(trace.distribution_family),
            "noise_realization": noise_realization,
            "realized_value": realized_value,
            "trace_source": source,
        },
    }


def register(server: FastMCP) -> None:
    @server.tool(
        name=TOOL_NAME, description=TOOL_DESCRIPTION, structured_output=False
    )
    def trace_cell(run_id: str, table: str, row_id: str, column: str) -> Any:
        try:
            return trace_cell_payload(run_id, table, row_id, column)
        except runs.RunNotFound as exc:
            return ToolError(
                code=CODE_RUN_NOT_FOUND,
                message=f"no run with id {exc.args[0]!r}",
                details={"sandbox_root": str(runs.sandbox_root())},
            ).to_tool_result()
        except _RowNotFound as exc:
            return ToolError(
                code=CODE_ROW_NOT_FOUND,
                message=str(exc),
                details={"table": table, "row_id": row_id},
            ).to_tool_result()
        except _ColumnNotMetric as exc:
            return ToolError(
                code=CODE_COLUMN_NOT_METRIC,
                message=str(exc),
                details={"table": table, "column": column},
            ).to_tool_result()
        except _EntityNotFound as exc:
            return ToolError(
                code=CODE_ENTITY_NOT_FOUND,
                message=str(exc),
                details={"table": table, "row_id": row_id},
            ).to_tool_result()
        except Exception as exc:
            traceback_id = uuid.uuid4().hex[:12]
            return ToolError(
                code=CODE_INTERNAL,
                message=str(exc),
                details={
                    "exception_type": type(exc).__name__,
                    "traceback_id": traceback_id,
                    "traceback": _traceback.format_exc(),
                },
                traceback_id=traceback_id,
            ).to_tool_result()
