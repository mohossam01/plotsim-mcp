"""``get_schema`` — return plotsim's ``UserInput`` JSON Schema.

The schema is the contract every authoring tool's input is shaped against
— the same vocabulary ``validate_config``, ``preview``, and
``create_dataset`` accept. Clients fetch it once per session and use it
to drive form rendering, autocomplete, and client-side validation against
the **builder** layer (``unit``, ``segments``, ``metrics``, ``window``)
rather than the engine-shape (``entities``, ``archetypes``, ``tables``,
``time_window``) that plotsim's interpreter produces internally. Sourced
directly from pydantic (``UserInput.model_json_schema()``) rather than the
``plotsim schema`` CLI so we don't subprocess for what is a pure-Python
introspection.
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
    "Return the plotsim UserInput JSON Schema — the builder-shape contract "
    "validate_config, preview, and create_dataset accept. Clients should "
    "fetch it once per session and use it to drive form rendering, "
    "autocomplete, and client-side validation against the same vocabulary "
    "the user authors against."
)


def get_schema_payload() -> dict[str, Any]:
    """Assemble ``{schema, schema_version}`` for the tool payload."""
    from plotsim.builder.input import UserInput

    schema = UserInput.model_json_schema()
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
                message=f"failed to emit UserInput schema: {exc}",
                details={"traceback": traceback.format_exc()},
                traceback_id=traceback_id,
            ).to_tool_result()
