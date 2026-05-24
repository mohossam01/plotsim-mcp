"""Regression: FastMCP must pass a returned ``CallToolResult`` through intact.

Outcome of the M036 spike: when a ``@server.tool`` function returns a
``CallToolResult(isError=True, ...)`` directly, FastMCP forwards it unchanged
— the ``isError`` flag and the structured payload survive the round-trip. By
contrast, raising an exception lands the client with an auto-wrapped plain
text error (``Error executing tool ...: <repr>``) that strips the structured
payload.

The implementation rule that falls out: every plotsim-mcp tool that can fail
catches its own failure modes and returns ``ToolError(...).to_tool_result()``
directly. Letting an exception bubble loses the contract. This file locks
that behaviour so a future FastMCP / MCP SDK upgrade can't silently
re-introduce the wrapping path.
"""
from __future__ import annotations

import json
from typing import Any

import pytest
from mcp.server.fastmcp import FastMCP
from mcp.shared.memory import create_connected_server_and_client_session

from plotsim_mcp.errors import CODE_TEMPLATE_UNKNOWN, ToolError


def _build_passthrough_server() -> FastMCP:
    server = FastMCP("test-passthrough")

    @server.tool(name="returns_tool_error", structured_output=False)
    def returns_tool_error() -> Any:
        return ToolError(
            code=CODE_TEMPLATE_UNKNOWN,
            message="probe",
            details={"available": ["alpha", "beta"]},
        ).to_tool_result()

    @server.tool(name="raises_value_error")
    def raises_value_error() -> dict[str, str]:
        raise ValueError("probe raised")

    return server


@pytest.mark.asyncio
async def test_returned_calltoolresult_passes_through_unchanged() -> None:
    server = _build_passthrough_server()
    async with create_connected_server_and_client_session(server._mcp_server) as session:
        result = await session.call_tool("returns_tool_error", {})

    assert result.isError is True, (
        "FastMCP must pass through a returned CallToolResult with isError=True; "
        "if this assertion fails the SDK has changed behaviour and every fail-able "
        "tool needs the wrapper path documented in the M2 spike notes."
    )
    assert len(result.content) == 1
    text = getattr(result.content[0], "text", None)
    assert isinstance(text, str)
    payload = json.loads(text)
    assert payload == {
        "code": "plotsim.template.unknown",
        "message": "probe",
        "details": {"available": ["alpha", "beta"]},
    }


@pytest.mark.asyncio
async def test_unhandled_exception_loses_structured_payload() -> None:
    server = _build_passthrough_server()
    async with create_connected_server_and_client_session(server._mcp_server) as session:
        result = await session.call_tool("raises_value_error", {})

    assert result.isError is True
    text = getattr(result.content[0], "text", None)
    assert isinstance(text, str)
    # The text is NOT structured JSON — it's FastMCP's auto-wrapped string.
    # If this assertion ever fails (the SDK started preserving structure on
    # exceptions), tools could optionally drop the manual catch path. Today
    # they cannot.
    try:
        json.loads(text)
        structured = True
    except json.JSONDecodeError:
        structured = False
    assert structured is False, (
        "FastMCP auto-wraps unhandled exceptions into a plain text error; "
        "if it starts returning JSON, tools may simplify their failure paths."
    )
