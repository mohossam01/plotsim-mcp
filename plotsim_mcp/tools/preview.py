"""``preview`` — estimate what a config would generate without running it.

Mirrors ``plotsim info``'s estimate logic against the public
``PlotsimConfig`` object so an MCP client can size a config before paying
for the full generation pass. The math is duplicated here (rather than
importing ``plotsim.cli._estimate_rows`` directly) so we don't couple to
private CLI helpers — the integration test asserts parity against plotsim's
implementation on the bundled ``saas`` template.

Cell-budget classification mirrors plotsim's gate exactly: cells = entities
× periods (the dimension the soft / hard cap is enforced against). Row
estimates are an upper-bound across dim / fact / event grains and are
strictly informational.
"""
from __future__ import annotations

import calendar
import datetime as _dt
import warnings
from typing import Any

import yaml
from mcp.server.fastmcp import FastMCP
from pydantic import ValidationError

from plotsim_mcp.errors import CODE_BUDGET_EXCEEDED, CODE_CONFIG_INVALID, ToolError


TOOL_NAME = "preview"
TOOL_DESCRIPTION = (
    "Estimate what a plotsim config would generate without running it. "
    "Returns domain name, entity/period counts, table counts by type, the "
    "estimated row count, the resolved cell budget, and whether the config "
    "exceeds it. Accepts a builder-shape YAML string or dict."
)

# Match plotsim/config.py:_CELL_SOFT_BUDGET_DEFAULT — used when neither the
# config nor PLOTSIM_CELL_BUDGET sets one. Duplicated rather than imported
# because the constant is module-private; the test_integration asserts the
# value still aligns.
_CELL_SOFT_BUDGET_DEFAULT = 2_000_000


def _coerce_to_dict(payload: str | dict[str, Any]) -> dict[str, Any]:
    if isinstance(payload, dict):
        return payload
    if isinstance(payload, str):
        parsed = yaml.safe_load(payload)
        if parsed is None:
            return {}
        if not isinstance(parsed, dict):
            raise TypeError(
                f"YAML must parse to a mapping; got {type(parsed).__name__}"
            )
        return parsed
    raise TypeError(
        f"preview expects a YAML string or dict; got {type(payload).__name__}"
    )


def _estimate_periods(config: Any) -> int:
    tw = config.time_window
    start = (
        _dt.date.fromisoformat(tw.start + "-01")
        if len(tw.start) == 7
        else _dt.date.fromisoformat(tw.start)
    )
    end = (
        _dt.date.fromisoformat(tw.end + "-01")
        if len(tw.end) == 7
        else _dt.date.fromisoformat(tw.end)
    )
    if tw.granularity == "monthly":
        return (end.year - start.year) * 12 + (end.month - start.month) + 1
    if tw.granularity == "weekly":
        return ((end - start).days // 7) + 1
    if tw.granularity == "daily":
        if len(tw.end) == 7:
            last_day = calendar.monthrange(end.year, end.month)[1]
            end = _dt.date(end.year, end.month, last_day)
        return (end - start).days + 1
    return 0


def _estimate_rows(config: Any, n_periods: int) -> int:
    n_entities = sum(ent.size for ent in config.entities)
    total = n_periods  # dim_date
    total += len(config.entities)  # dim_<entity>
    for tbl in config.tables:
        if tbl.grain == "per_entity_per_period":
            total += n_entities * n_periods
        elif tbl.grain == "per_period":
            total += n_periods
        elif tbl.grain == "per_reference":
            total += 1
    return total


def _resolved_cell_budget(config: Any) -> int:
    """Return the soft cell budget plotsim would enforce for ``config``.

    Mirrors ``plotsim.config._resolve_cell_budget`` precedence: explicit
    ``output.cell_budget`` first, then the default. Env var resolution is
    omitted because the MCP server's job is to report the static budget
    declared in the config, not the env-time override that may differ
    between the server process and the caller's generation context.
    """
    explicit = getattr(config.output, "cell_budget", None)
    if explicit is not None:
        return int(explicit)
    return _CELL_SOFT_BUDGET_DEFAULT


def preview_payload(payload: str | dict[str, Any]) -> dict[str, Any]:
    """Return the preview envelope; raise typed exceptions on failure.

    Callers (``register`` below) translate ``ValidationError`` /
    ``TypeError`` / ``yaml.YAMLError`` into the structured error envelope.
    """
    from plotsim import create
    from plotsim.config import _CELL_HARD_CEILING

    data = _coerce_to_dict(payload)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        config = create(**data)

    n_periods = _estimate_periods(config)
    n_entities = sum(ent.size for ent in config.entities)
    n_dim = sum(1 for t in config.tables if t.type == "dim")
    n_fact = sum(1 for t in config.tables if t.type == "fact")
    n_event = sum(1 for t in config.tables if t.type == "event")
    estimated_rows = _estimate_rows(config, n_periods)
    cell_count = n_entities * n_periods
    cell_budget = _resolved_cell_budget(config)
    return {
        "domain": config.domain.name,
        "entities": n_entities,
        "periods": n_periods,
        "tables": {
            "total": len(config.tables),
            "dim": n_dim,
            "fact": n_fact,
            "event": n_event,
        },
        "archetypes_in_use": sorted({ent.archetype for ent in config.entities}),
        "estimated_rows": estimated_rows,
        "cell_count": cell_count,
        "cell_budget": cell_budget,
        "cell_hard_ceiling": _CELL_HARD_CEILING,
        "headroom": cell_budget - cell_count,
        "exceeds_budget": cell_count > cell_budget,
    }


def _format_pydantic_errors(exc: ValidationError) -> list[dict[str, Any]]:
    return [
        {
            "loc": ".".join(str(p) for p in err.get("loc", ())),
            "msg": err.get("msg", ""),
            "type": err.get("type", ""),
        }
        for err in exc.errors()
    ]


def _is_budget_exceeded(exc: ValidationError) -> bool:
    """Detect plotsim's cell-budget gate firing inside ``create()``.

    ``PlotsimConfig`` enforces the cell ceiling in a pydantic
    ``model_validator``; the raised ``ValueError`` is re-wrapped as a
    ``ValidationError`` by pydantic. The wire-distinguishing signal is the
    error message string — the validator phrases it as
    ``"Config produces N cells ..."``.
    """
    for err in exc.errors():
        msg = str(err.get("msg", ""))
        if "Config produces" in msg and "cells" in msg:
            return True
    return False


def register(server: FastMCP) -> None:
    @server.tool(name=TOOL_NAME, description=TOOL_DESCRIPTION, structured_output=False)
    def preview(config: str | dict[str, Any]) -> Any:
        try:
            return preview_payload(config)
        except ValidationError as exc:
            if _is_budget_exceeded(exc):
                return ToolError(
                    code=CODE_BUDGET_EXCEEDED,
                    message="config exceeds plotsim's cell ceiling",
                    details={"errors": _format_pydantic_errors(exc)},
                ).to_tool_result()
            return ToolError(
                code=CODE_CONFIG_INVALID,
                message=f"{len(exc.errors())} validation error(s)",
                details={"errors": _format_pydantic_errors(exc)},
            ).to_tool_result()
        except (TypeError, yaml.YAMLError) as exc:
            return ToolError(
                code=CODE_CONFIG_INVALID,
                message=str(exc),
                details={"errors": []},
            ).to_tool_result()
