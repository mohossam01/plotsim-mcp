"""Protocol test — drives the stdio server through a real MCP client session.

Spawns ``python -m plotsim_mcp`` as a subprocess, performs the JSON-RPC
``initialize`` handshake, lists tools, calls ``list_templates``, and
asserts the wire-format envelope (``isError``, content shape, payload
parses as JSON, payload matches the integration-test catalogue).

If this test passes, the M1 acceptance criterion "wire format works
against a real client" is met.
"""
from __future__ import annotations

import json
import sys

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

EXPECTED_TEMPLATES = {"banking", "health", "hr", "marketing", "retail", "saas"}


@pytest.mark.asyncio
async def test_list_templates_protocol_roundtrip() -> None:
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "plotsim_mcp"],
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools = await session.list_tools()
            tool_names = {t.name for t in tools.tools}
            assert "list_templates" in tool_names, (
                f"expected list_templates in advertised tools, got {tool_names}"
            )

            result = await session.call_tool("list_templates", {})
            assert result.isError is False, (
                f"unexpected isError=True; content={result.content!r}"
            )
            assert result.content, "call_tool returned no content blocks"

            first = result.content[0]
            text = getattr(first, "text", None)
            assert isinstance(text, str), (
                f"expected first content block to carry text, got {first!r}"
            )

            envelope = json.loads(text)
            assert isinstance(envelope, dict)
            assert "templates" in envelope
            templates = envelope["templates"]
            assert isinstance(templates, list)

            names = {item["name"] for item in templates}
            assert names == EXPECTED_TEMPLATES

            for item in templates:
                assert set(item.keys()) == {"name", "description"}
                assert item["description"]
