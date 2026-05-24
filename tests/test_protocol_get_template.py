"""Protocol coverage for ``get_template`` — happy path returns the full
envelope; unknown name returns ``plotsim.template.unknown`` with the
``available`` list intact in ``details``.
"""
from __future__ import annotations

import json

import plotsim
import pytest
from mcp.shared.memory import create_connected_server_and_client_session

from plotsim_mcp.server import build_server


@pytest.mark.asyncio
async def test_get_template_happy_path() -> None:
    server = build_server()
    async with create_connected_server_and_client_session(server._mcp_server) as session:
        result = await session.call_tool("get_template", {"name": "saas"})

    assert result.isError is False
    assert len(result.content) == 1
    text = getattr(result.content[0], "text", None)
    assert isinstance(text, str)
    envelope = json.loads(text)
    assert envelope["name"] == "saas"
    assert envelope["yaml"].strip()
    assert isinstance(envelope["parsed"], dict)


@pytest.mark.asyncio
async def test_get_template_unknown_name_returns_error_envelope() -> None:
    server = build_server()
    async with create_connected_server_and_client_session(server._mcp_server) as session:
        result = await session.call_tool(
            "get_template", {"name": "no_such_template"}
        )

    assert result.isError is True
    text = getattr(result.content[0], "text", None)
    assert isinstance(text, str)
    payload = json.loads(text)
    assert payload["code"] == "plotsim.template.unknown"
    assert "no_such_template" in payload["message"]
    assert set(payload["details"]["available"]) == set(plotsim.list_templates())
