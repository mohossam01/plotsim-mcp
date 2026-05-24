"""Protocol coverage for ``create_dataset`` — happy path against a tiny
inline config, plus the structured-error path for an out-of-sandbox
``output_dir``.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from mcp.shared.memory import create_connected_server_and_client_session

from plotsim_mcp import runs
from plotsim_mcp.server import build_server


_TINY_CONFIG: dict = {
    "about": "create_dataset protocol fixture",
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
async def test_create_dataset_happy_path() -> None:
    server = build_server()
    async with create_connected_server_and_client_session(server._mcp_server) as session:
        result = await session.call_tool(
            "create_dataset", {"template_or_config": _TINY_CONFIG, "seed": 31}
        )

    assert result.isError is False
    assert len(result.content) == 1
    text = getattr(result.content[0], "text")
    envelope = json.loads(text)
    assert envelope["run_id"]
    assert envelope["validation_summary"]["ok"] is True


@pytest.mark.asyncio
async def test_create_dataset_rejects_out_of_sandbox_output_dir(tmp_path: Path) -> None:
    outside = tmp_path / "elsewhere"
    outside.mkdir()
    server = build_server()
    async with create_connected_server_and_client_session(server._mcp_server) as session:
        result = await session.call_tool(
            "create_dataset",
            {
                "template_or_config": _TINY_CONFIG,
                "seed": 37,
                "output_dir": str(outside),
            },
        )

    assert result.isError is True
    payload = json.loads(getattr(result.content[0], "text"))
    assert payload["code"] == "plotsim.run.path_forbidden"
