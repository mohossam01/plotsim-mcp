"""Protocol coverage for ``get_schema`` — in-process MCP client round-trip,
asserts ``isError=False``, a single ``TextContent`` block, and that the
payload's ``schema`` parses as JSON-Schema-shaped.
"""
from __future__ import annotations

import json

import pytest
from mcp.shared.memory import create_connected_server_and_client_session

from plotsim_mcp.server import build_server


@pytest.mark.asyncio
async def test_get_schema_protocol_roundtrip() -> None:
    server = build_server()
    async with create_connected_server_and_client_session(server._mcp_server) as session:
        result = await session.call_tool("get_schema", {})

    assert result.isError is False, (
        f"get_schema returned an error envelope: {result.content!r}"
    )
    assert len(result.content) == 1, (
        f"expected a single TextContent block, got {len(result.content)}"
    )
    text = getattr(result.content[0], "text", None)
    assert isinstance(text, str)
    envelope = json.loads(text)
    assert set(envelope.keys()) == {"schema", "schema_version"}
    assert envelope["schema"].get("type") == "object"
