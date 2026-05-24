"""Regression: every plotsim-mcp tool returns exactly one ``TextContent``
block on the happy path.

Background: FastMCP 1.27 splits a bare ``list`` return into one
``TextContent`` block per element, which breaks downstream clients that
expect to ``json.loads`` the first block. The fix is dict-wrapping every
collection (see ``[m35/fastmcp-1_27-splits-bare-lists]``). This file locks
the convention so any future tool that forgets the wrapper fails fast.

Coverage: registered tools are introspected from ``build_server()`` rather
than hard-coded so adding a new tool implicitly extends the regression.
"""
from __future__ import annotations

import importlib.resources as _resources

import pytest
import yaml
from mcp.shared.memory import create_connected_server_and_client_session

from plotsim_mcp.server import build_server

# Per-tool happy-path arguments — the test calls each tool and asserts the
# single-content-block envelope. Tools whose happy path needs arguments
# declare them here; the rest get ``{}``.
_HAPPY_PATH_ARGS: dict[str, dict[str, object]] = {
    "list_templates": {},
    "get_schema": {},
    "describe_capability": {"area": "curves"},
    "get_template": {"name": "saas"},
    "validate_config": {},  # filled in at runtime — needs the saas YAML
}


def _saas_yaml_text() -> str:
    root = _resources.files("plotsim.configs.templates")
    for candidate in ("saas.yaml", "saas_template.yaml"):
        entry = root / candidate
        if entry.is_file():
            return entry.read_text(encoding="utf-8")
    raise FileNotFoundError("saas template missing")


@pytest.mark.asyncio
async def test_every_tool_returns_single_textcontent_block() -> None:
    saas_yaml = _saas_yaml_text()
    _HAPPY_PATH_ARGS["validate_config"] = {"config": saas_yaml}

    server = build_server()
    async with create_connected_server_and_client_session(server._mcp_server) as session:
        tools = await session.list_tools()
        registered_names = {t.name for t in tools.tools}

        # Sanity guard: every name we plan to call must actually be
        # registered on the server, otherwise the loop silently skips.
        assert registered_names == set(_HAPPY_PATH_ARGS.keys()), (
            f"happy-path arg map drift: registered={registered_names}, "
            f"covered={set(_HAPPY_PATH_ARGS.keys())}"
        )

        for tool_name in sorted(registered_names):
            args = _HAPPY_PATH_ARGS[tool_name]
            result = await session.call_tool(tool_name, args)
            assert result.isError is False, (
                f"{tool_name} returned an error envelope on the happy path: "
                f"{result.content!r}"
            )
            assert len(result.content) == 1, (
                f"{tool_name} returned {len(result.content)} content blocks "
                f"(expected exactly 1 — dict-wrap the collection)."
            )
            text = getattr(result.content[0], "text", None)
            assert isinstance(text, str), (
                f"{tool_name}'s content block is not text-typed: "
                f"{result.content[0]!r}"
            )
            # Must parse as JSON — the M035 finding boils down to "one
            # TextContent block carrying the JSON-encoded dict envelope".
            import json as _json

            _json.loads(text)
            # Smoke: ``yaml.safe_load`` should agree (JSON is YAML).
            yaml.safe_load(text)
