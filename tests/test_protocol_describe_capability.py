"""Protocol coverage for ``describe_capability`` — happy path returns one
``TextContent`` block with the dict-wrapped values list; unknown area
returns an ``isError=True`` envelope with the ``plotsim.capability.unknown``
code and the full ``valid_areas`` list in ``details``.
"""
from __future__ import annotations

import json

import pytest
from mcp.shared.memory import create_connected_server_and_client_session

from plotsim_mcp.server import build_server
from plotsim_mcp.tools.describe_capability import VALID_AREAS


@pytest.mark.asyncio
async def test_describe_capability_happy_path() -> None:
    server = build_server()
    async with create_connected_server_and_client_session(server._mcp_server) as session:
        result = await session.call_tool("describe_capability", {"area": "curves"})

    assert result.isError is False
    assert len(result.content) == 1
    text = getattr(result.content[0], "text", None)
    assert isinstance(text, str)
    envelope = json.loads(text)
    assert envelope["area"] == "curves"
    assert isinstance(envelope["values"], list)
    assert envelope["values"], "curves vocabulary cannot be empty"


@pytest.mark.asyncio
async def test_describe_capability_unknown_area_returns_error_envelope() -> None:
    server = build_server()
    async with create_connected_server_and_client_session(server._mcp_server) as session:
        result = await session.call_tool(
            "describe_capability", {"area": "not_an_area"}
        )

    assert result.isError is True
    text = getattr(result.content[0], "text", None)
    assert isinstance(text, str)
    payload = json.loads(text)
    assert payload["code"] == "plotsim.capability.unknown"
    assert "not_an_area" in payload["message"]
    assert set(payload["details"]["valid_areas"]) == set(VALID_AREAS)
