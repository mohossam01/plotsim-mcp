"""Protocol coverage for ``describe_run`` — happy path against a real
run (built via ``create_dataset``) and the structured-error path for an
unknown ``run_id``.
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
    "about": "describe_run protocol fixture",
    "unit": "customer",
    "window": {"start": "2024-01", "end": "2024-03", "every": "monthly"},
    "segments": [{"name": "cohort_a", "count": 5, "archetype": "growth"}],
    "metrics": [
        {"name": "engagement", "type": "score", "polarity": "positive"}
    ],
}


@pytest.fixture(autouse=True)
def _isolated_sandbox(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    monkeypatch.setenv(runs.ENV_VAR, str(tmp_path / "runs"))
    return tmp_path / "runs"


@pytest.mark.asyncio
async def test_describe_run_happy_path() -> None:
    created = create_dataset_payload(_TINY_CONFIG, seed=43)
    server = build_server()
    async with create_connected_server_and_client_session(server._mcp_server) as session:
        result = await session.call_tool("describe_run", {"run_id": created["run_id"]})

    assert result.isError is False
    text = getattr(result.content[0], "text")
    envelope = json.loads(text)
    assert envelope["run_id"] == created["run_id"]
    assert envelope["summary"]["archetype_assignments_total"] == 5


@pytest.mark.asyncio
async def test_describe_run_unknown_id_returns_error_envelope() -> None:
    server = build_server()
    async with create_connected_server_and_client_session(server._mcp_server) as session:
        result = await session.call_tool(
            "describe_run", {"run_id": "20260524T000000Z-doesntex"}
        )

    assert result.isError is True
    payload = json.loads(getattr(result.content[0], "text"))
    assert payload["code"] == "plotsim.run.not_found"
