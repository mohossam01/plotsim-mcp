"""Protocol coverage for ``validate_config`` — happy path against a
bundled template (round-tripped through the tool) and the structured-error
path with malformed input.
"""
from __future__ import annotations

import importlib.resources as _resources
import json

import pytest
import yaml
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
async def test_validate_config_happy_path_yaml() -> None:
    yaml_text = _load_saas_yaml_text()
    server = build_server()
    async with create_connected_server_and_client_session(server._mcp_server) as session:
        result = await session.call_tool("validate_config", {"config": yaml_text})

    assert result.isError is False
    assert len(result.content) == 1
    payload = json.loads(getattr(result.content[0], "text"))
    assert payload["valid"] is True


@pytest.mark.asyncio
async def test_validate_config_invalid_returns_structured_error() -> None:
    yaml_text = _load_saas_yaml_text()
    bad = yaml.safe_load(yaml_text)
    bad["window"] = "not a window"
    server = build_server()
    async with create_connected_server_and_client_session(server._mcp_server) as session:
        result = await session.call_tool("validate_config", {"config": bad})

    assert result.isError is True
    payload = json.loads(getattr(result.content[0], "text"))
    assert payload["code"] == "plotsim.config.invalid"
    assert isinstance(payload["details"]["errors"], list)
    assert payload["details"]["errors"], "expected at least one structured error entry"
    for entry in payload["details"]["errors"]:
        assert set(entry.keys()) == {"loc", "msg", "type"}
