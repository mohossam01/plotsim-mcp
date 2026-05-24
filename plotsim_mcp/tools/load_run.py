"""``load_run`` — fetch everything an MCP client needs to iterate on a run.

Combines the raw + parsed config (``get_template``-style) with the
manifest summary (``describe_run``-style) and the validation status
(``get_validation_report``-style) in a single envelope. Saves the caller
the three round-trips that ``describe_run`` + ``get_validation_report``
+ a raw file read would otherwise require for the common "modify this
config and re-run" loop.

Composes existing tool payload functions rather than re-deriving the
same numbers — any future schema change to the summary or report parser
automatically propagates here.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from mcp.server.fastmcp import FastMCP

from plotsim_mcp import runs
from plotsim_mcp.errors import CODE_RUN_NOT_FOUND, ToolError
from plotsim_mcp.tools.describe_run import describe_run_payload
from plotsim_mcp.tools.get_validation_report import get_validation_report_payload


TOOL_NAME = "load_run"
TOOL_DESCRIPTION = (
    "Load a run's config + manifest summary + validation status in one "
    "call. Returns {run_id, config_yaml, config_parsed, manifest_summary, "
    "validation_ok, tables_written}. Optimized for the modify-and-rerun "
    "flow — saves three separate calls to get_template / describe_run / "
    "get_validation_report."
)

_CONFIG_FILENAME = "config.yaml"


def _read_config_text(run_dir: Path) -> str:
    config_path = run_dir / _CONFIG_FILENAME
    if not config_path.is_file():
        return ""
    return config_path.read_text(encoding="utf-8")


def load_run_payload(run_id: str) -> dict[str, Any]:
    """Return the combined envelope; raise :class:`runs.RunNotFound` if absent.

    The wrapper in :func:`register` translates ``RunNotFound`` into the
    ``plotsim.run.not_found`` ToolError. Other failures (parse errors,
    missing manifest) are absorbed by the underlying payload functions
    and returned as empty defaults — a run with no manifest still loads.
    """
    run_dir = runs.resolve(run_id)
    config_yaml = _read_config_text(run_dir)
    parsed = yaml.safe_load(config_yaml) if config_yaml else None
    if not isinstance(parsed, dict):
        parsed = {}

    described = describe_run_payload(run_id)
    report = get_validation_report_payload(run_id)

    return {
        "run_id": run_id,
        "config_yaml": config_yaml,
        "config_parsed": parsed,
        "manifest_summary": described["summary"],
        "validation_ok": bool(report["ok"]),
        "tables_written": list(described["tables"]),
    }


def register(server: FastMCP) -> None:
    @server.tool(
        name=TOOL_NAME, description=TOOL_DESCRIPTION, structured_output=False
    )
    def load_run(run_id: str) -> Any:
        try:
            return load_run_payload(run_id)
        except runs.RunNotFound as exc:
            return ToolError(
                code=CODE_RUN_NOT_FOUND,
                message=f"no run with id {exc.args[0]!r}",
                details={"sandbox_root": str(runs.sandbox_root())},
            ).to_tool_result()
