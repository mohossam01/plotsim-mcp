"""``get_schema`` — return plotsim's ``PlotsimConfig`` JSON Schema.

The schema is the contract every other tool's input/output is shaped around.
Clients call this once at session start to drive form rendering, validation,
and autocomplete. Sourced directly from pydantic
(``PlotsimConfig.model_json_schema()``) rather than the ``plotsim schema``
CLI so we don't subprocess for what is a pure-Python introspection.
"""
from __future__ import annotations

import traceback
import uuid
from typing import Any

import plotsim
from mcp.server.fastmcp import FastMCP

from plotsim_mcp.errors import CODE_INTERNAL, ToolError

TOOL_NAME = "get_schema"
TOOL_DESCRIPTION = (
    "Return the full plotsim PlotsimConfig JSON Schema. The schema is the "
    "contract for every input passed to plotsim — clients should fetch it "
    "once per session and use it to drive form rendering, autocomplete, and "
    "client-side validation."
)


def get_schema_payload() -> dict[str, Any]:
    """Assemble ``{schema, schema_version}`` for the tool payload."""
    from plotsim.config import PlotsimConfig

    schema = PlotsimConfig.model_json_schema()
    return {"schema": schema, "schema_version": plotsim.__version__}


def register(server: FastMCP) -> None:
    # ``structured_output=False`` opts out of FastMCP's output-schema
    # synthesis. We need that opt-out because the function can return
    # either a dict payload (happy path) or a ``CallToolResult`` envelope
    # (failure path) per the M036 spike — FastMCP's auto-synthesis would
    # try to validate the ``CallToolResult`` against the dict schema and
    # fail at runtime.
    @server.tool(name=TOOL_NAME, description=TOOL_DESCRIPTION, structured_output=False)
    def get_schema() -> Any:
        try:
            return get_schema_payload()
        except Exception as exc:  # pragma: no cover - defensive
            traceback_id = uuid.uuid4().hex
            return ToolError(
                code=CODE_INTERNAL,
                message=f"failed to emit PlotsimConfig schema: {exc}",
                details={"traceback": traceback.format_exc()},
                traceback_id=traceback_id,
            ).to_tool_result()
