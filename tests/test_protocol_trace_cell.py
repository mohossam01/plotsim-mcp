"""Protocol coverage for ``trace_cell`` — happy path against a real
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
from plotsim_mcp.tools.trace_cell import _load_config


_TINY_CONFIG: dict = {
    "about": "trace_cell protocol fixture",
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


def _pick_metric_column(run_dir: Path) -> tuple[str, str]:
    from plotsim.config import MetricSource, parse_source

    config = _load_config(run_dir)
    for tbl in config.tables:
        if (
            getattr(tbl, "type", None) == "fact"
            and getattr(tbl, "grain", None) == "per_entity_per_period"
        ):
            for col in tbl.columns:
                parsed = parse_source(col.source)
                if isinstance(parsed, MetricSource):
                    return str(tbl.name), str(col.name)
    raise AssertionError("no per_entity_per_period fact table with metric column")


@pytest.mark.asyncio
async def test_trace_cell_happy_path() -> None:
    created = create_dataset_payload(_TINY_CONFIG, seed=107)
    run_dir = runs.resolve(created["run_id"])
    table, column = _pick_metric_column(run_dir)

    server = build_server()
    async with create_connected_server_and_client_session(server._mcp_server) as session:
        result = await session.call_tool(
            "trace_cell",
            {
                "run_id": created["run_id"],
                "table": table,
                "row_id": "0",
                "column": column,
            },
        )

    assert result.isError is False
    text = getattr(result.content[0], "text")
    envelope = json.loads(text)
    assert envelope["run_id"] == created["run_id"]
    assert envelope["table"] == table
    assert envelope["column"] == column
    assert "archetype" in envelope["trace"]
    assert "trajectory_position" in envelope["trace"]
    assert envelope["trace"]["trace_source"] in {"manifest", "rederived_from_seed"}


@pytest.mark.asyncio
async def test_trace_cell_unknown_run_returns_error_envelope() -> None:
    server = build_server()
    async with create_connected_server_and_client_session(server._mcp_server) as session:
        result = await session.call_tool(
            "trace_cell",
            {
                "run_id": "20260524T000000Z-doesntex",
                "table": "fct_anything",
                "row_id": "0",
                "column": "some_metric",
            },
        )

    assert result.isError is True
    payload = json.loads(getattr(result.content[0], "text"))
    assert payload["code"] == "plotsim.run.not_found"
