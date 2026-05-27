"""``list_runs`` — enumerate every dataset run under the sandbox root.

Returns one entry per run directory the MCP server has produced (or that
a caller materialized under the sandbox root explicitly). Each entry
carries the run handle other inspection tools key off (``run_id``), the
on-disk path (``output_dir``), the last-modified timestamp
(``modified_at``, ISO 8601 UTC), and the pass/fail signal from the run's
validation report (``validation_ok``, ``None`` when no report is
present).

Entries are sorted by modification time, most recent first — the common
"what's my latest run" lookup completes without the caller having to
re-sort. Empty sandbox returns ``{"runs": []}`` rather than raising; an
empty result is a valid state, not an error.
"""
from __future__ import annotations

import datetime as _dt
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from plotsim_mcp import runs
from plotsim_mcp.tools.get_validation_report import (
    get_validation_report_payload,
)


TOOL_NAME = "list_runs"
TOOL_DESCRIPTION = (
    "Enumerate every run directory under the sandbox root. Returns "
    "{runs: [{run_id, output_dir, modified_at, validation_ok}, ...]} "
    "sorted by modification time (most recent first). validation_ok is "
    "null when the run has no validation_report.txt. Use get_sandbox_root "
    "to discover the sandbox path the entries live under."
)

_REPORT_FILENAME = "validation_report.txt"


def _validation_ok_for(run_id: str, run_dir: Path) -> bool | None:
    """Return the run's validation status, ``None`` when no report exists.

    Routes through ``get_validation_report_payload`` so the parsing logic
    stays in one place — any future change to the report format
    propagates here automatically.
    """
    if not (run_dir / _REPORT_FILENAME).is_file():
        return None
    payload = get_validation_report_payload(run_id)
    return bool(payload["ok"])


def _entry_for(run_dir: Path) -> dict[str, Any]:
    stat = run_dir.stat()
    modified = _dt.datetime.fromtimestamp(stat.st_mtime, tz=_dt.timezone.utc)
    run_id = run_dir.name
    return {
        "run_id": run_id,
        "output_dir": str(run_dir),
        "modified_at": modified.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "validation_ok": _validation_ok_for(run_id, run_dir),
    }


def list_runs_payload() -> dict[str, list[dict[str, Any]]]:
    """Return the dict-wrapped list of run entries.

    Directories that fail to ``stat()`` (e.g. permission errors, races
    with concurrent deletion) are skipped silently rather than failing
    the whole call. The empty-sandbox path falls out naturally: an empty
    iterdir produces an empty list.
    """
    root = runs.sandbox_root()
    entries: list[dict[str, Any]] = []
    for child in root.iterdir():
        if not child.is_dir():
            continue
        try:
            entries.append(_entry_for(child))
        except OSError:
            continue
    entries.sort(key=lambda e: e["modified_at"], reverse=True)
    return {"runs": entries}


def register(server: FastMCP) -> None:
    @server.tool(name=TOOL_NAME, description=TOOL_DESCRIPTION)
    def list_runs() -> dict[str, list[dict[str, Any]]]:
        # No structured_output=False here — the payload function has no
        # fail modes that produce ToolError envelopes; sandbox discovery
        # is creation-on-read via ``runs.sandbox_root()``, and per-entry
        # stat failures are absorbed inside ``list_runs_payload``.
        return list_runs_payload()
