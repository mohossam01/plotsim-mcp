"""Protocol coverage for ``preview`` — happy path returns one
``TextContent`` block with the estimate envelope; an invalid config surfaces
the structured ``plotsim.config.invalid`` error envelope.
"""
from __future__ import annotations

import importlib.resources as _resources
import json

import pytest
from mcp.shared.memory import create_connected_server_and_client_session

from plotsim_mcp.server import build_server


def _load_saas_yaml_text() -> str:
    root = _resources.files("plotsim.configs.templates")
    for candidate in ("saas.yaml", "saas_template.yaml"):
        entry = root / candidate
        if entry.is_file():
            return entry.read_text(encoding="utf-8")
    raise FileNotFoundError("saas template missing")


@pytest.mark.asyncio
async def test_preview_happy_path_yaml() -> None:
    yaml_text = _load_saas_yaml_text()
    server = build_server()
    async with create_connected_server_and_client_session(server._mcp_server) as session:
        result = await session.call_tool("preview", {"config": yaml_text})

    assert result.isError is False
    assert len(result.content) == 1
    text = getattr(result.content[0], "text")
    envelope = json.loads(text)
    assert envelope["entities"] > 0
    assert "cell_budget" in envelope
    assert "exceeds_budget" in envelope


@pytest.mark.asyncio
async def test_preview_invalid_config_returns_structured_error() -> None:
    server = build_server()
    async with create_connected_server_and_client_session(server._mcp_server) as session:
        result = await session.call_tool("preview", {"config": {"about": "x", "unit": "u"}})

    assert result.isError is True
    text = getattr(result.content[0], "text")
    payload = json.loads(text)
    assert payload["code"] == "plotsim.config.invalid"
    assert isinstance(payload["details"]["errors"], list)
