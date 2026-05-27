"""Protocol coverage for ``list_runs`` — in-process MCP client round-trip
asserts ``isError=False``, single ``TextContent`` block, and the
dict-wrapped ``runs`` payload.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from mcp.shared.memory import create_connected_server_and_client_session

from plotsim_mcp import runs
from plotsim_mcp.server import build_server
from plotsim_mcp.tools.create_dataset import create_dataset_payload


_TINY_CONFIG: dict = {
    "about": "list_runs protocol fixture",
    "unit": "customer",
    "window": {"start": "2024-01", "end": "2024-03", "every": "monthly"},
    "segments": [{"name": "cohort_a", "count": 4, "archetype": "growth"}],
    "metrics": [
        {"name": "engagement", "type": "score", "polarity": "positive"}
    ],
}


@pytest.fixture(autouse=True)
def _isolated_sandbox(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    monkeypatch.setenv(runs.ENV_VAR, str(tmp_path / "runs"))
    return tmp_path / "runs"


@pytest.mark.asyncio
async def test_list_runs_protocol_roundtrip_with_real_run() -> None:
    created = create_dataset_payload(_TINY_CONFIG, seed=167)
    server = build_server()
    async with create_connected_server_and_client_session(server._mcp_server) as session:
        result = await session.call_tool("list_runs", {})

    assert result.isError is False, (
        f"list_runs returned an error envelope: {result.content!r}"
    )
    assert len(result.content) == 1
    text = getattr(result.content[0], "text", None)
    assert isinstance(text, str)
    envelope = json.loads(text)
    assert set(envelope.keys()) == {"runs"}
    listed_ids = [entry["run_id"] for entry in envelope["runs"]]
    assert created["run_id"] in listed_ids


@pytest.mark.asyncio
async def test_list_runs_empty_sandbox_returns_empty_list() -> None:
    server = build_server()
    async with create_connected_server_and_client_session(server._mcp_server) as session:
        result = await session.call_tool("list_runs", {})

    assert result.isError is False
    envelope = json.loads(getattr(result.content[0], "text"))
    assert envelope == {"runs": []}
