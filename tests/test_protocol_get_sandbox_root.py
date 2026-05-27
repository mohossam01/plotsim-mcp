"""Protocol coverage for ``get_sandbox_root`` — in-process MCP client
round-trip asserts ``isError=False``, single ``TextContent`` block,
and the ``{sandbox_root, env_var}`` envelope.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from mcp.shared.memory import create_connected_server_and_client_session

from plotsim_mcp import runs
from plotsim_mcp.server import build_server


@pytest.fixture(autouse=True)
def _isolated_sandbox(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    monkeypatch.setenv(runs.ENV_VAR, str(tmp_path / "runs"))
    return tmp_path / "runs"


@pytest.mark.asyncio
async def test_get_sandbox_root_protocol_roundtrip() -> None:
    server = build_server()
    async with create_connected_server_and_client_session(server._mcp_server) as session:
        result = await session.call_tool("get_sandbox_root", {})

    assert result.isError is False, (
        f"get_sandbox_root returned an error envelope: {result.content!r}"
    )
    assert len(result.content) == 1
    text = getattr(result.content[0], "text", None)
    assert isinstance(text, str)
    envelope = json.loads(text)
    assert set(envelope.keys()) == {"sandbox_root", "env_var"}
    assert envelope["env_var"] == "PLOTSIM_MCP_RUN_ROOT"
    # The sandbox the protocol surface reports must match the in-process
    # runs module's view — same env var, same code path.
    assert Path(envelope["sandbox_root"]).resolve() == runs.sandbox_root().resolve()
