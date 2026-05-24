"""``get_validation_report`` — return the text validation report of a run.

Reads ``<run_dir>/validation_report.txt`` verbatim. The ``ok`` field is
parsed from the report's ``Status:`` header line (``VALID`` vs
``INVALID``) so the caller can short-circuit on a pass/fail signal
without re-parsing the body.

Returned shape: ``{run_id, report, ok}``. ``ok`` is ``False`` for any
run that lacks a validation_report.txt (the conservative default —
absence is not evidence of passing).
"""
from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from plotsim_mcp import runs
from plotsim_mcp.errors import CODE_RUN_NOT_FOUND, ToolError


TOOL_NAME = "get_validation_report"
TOOL_DESCRIPTION = (
    "Return the text validation report for a run. Returns "
    "{run_id, report, ok} where ``ok`` is parsed from the report's "
    "Status line (VALID/INVALID). Use create_dataset to produce a run_id."
)

_REPORT_FILENAME = "validation_report.txt"


def _parse_ok(text: str) -> bool:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("Status:"):
            value = stripped[len("Status:") :].strip().upper()
            return value == "VALID"
    return False


def get_validation_report_payload(run_id: str) -> dict[str, Any]:
    """Resolve ``run_id`` and return ``{run_id, report, ok}``.

    Raises :class:`plotsim_mcp.runs.RunNotFound` for unknown run ids;
    the wrapper translates that into ``plotsim.run.not_found``. A run
    whose dir exists but has no report yields an empty report string
    and ``ok=False`` rather than raising — the run is real, just doesn't
    have one.
    """
    run_dir = runs.resolve(run_id)
    report_path = run_dir / _REPORT_FILENAME
    if not report_path.is_file():
        return {"run_id": run_id, "report": "", "ok": False}
    text = report_path.read_text(encoding="utf-8")
    return {"run_id": run_id, "report": text, "ok": _parse_ok(text)}


def register(server: FastMCP) -> None:
    @server.tool(name=TOOL_NAME, description=TOOL_DESCRIPTION, structured_output=False)
    def get_validation_report(run_id: str) -> Any:
        try:
            return get_validation_report_payload(run_id)
        except runs.RunNotFound as exc:
            return ToolError(
                code=CODE_RUN_NOT_FOUND,
                message=f"no run with id {exc.args[0]!r}",
                details={"sandbox_root": str(runs.sandbox_root())},
            ).to_tool_result()
