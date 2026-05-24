"""Regression: every plotsim-mcp tool returns exactly one ``TextContent``
block on the happy path.

Background: FastMCP 1.27 splits a bare ``list`` return into one
``TextContent`` block per element, which breaks downstream clients that
expect to ``json.loads`` the first block. The fix is dict-wrapping every
collection (see ``[m35/fastmcp-1_27-splits-bare-lists]``). This file locks
the convention so any future tool that forgets the wrapper fails fast.

Coverage: registered tools are introspected from ``build_server()`` rather
than hard-coded so adding a new tool implicitly extends the regression.
``describe_run`` and ``get_validation_report`` are exercised against a
real run created in-fixture so the happy path doesn't surface a
``plotsim.run.not_found`` error envelope.
"""
from __future__ import annotations

import importlib.resources as _resources
from pathlib import Path

import pytest
import yaml
from mcp.shared.memory import create_connected_server_and_client_session

from plotsim_mcp import runs
from plotsim_mcp.server import build_server
from plotsim_mcp.tools.create_dataset import create_dataset_payload


_TINY_CONFIG: dict = {
    "about": "envelope fixture",
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
    created = create_dataset_payload(_TINY_CONFIG, seed=61)
    # trace_cell needs a real fact-table coordinate; discover it from the
    # written config so the test doesn't hard-code engine-generated names.
    from plotsim_mcp.tools.trace_cell import _load_config as _trace_load_config

    from plotsim.config import MetricSource, parse_source

    _trace_config = _trace_load_config(runs.resolve(created["run_id"]))
    _trace_table = None
    _trace_column = None
    for tbl in _trace_config.tables:
        if (
            getattr(tbl, "type", None) == "fact"
            and getattr(tbl, "grain", None) == "per_entity_per_period"
        ):
            for col in tbl.columns:
                if isinstance(parse_source(col.source), MetricSource):
                    _trace_table = str(tbl.name)
                    _trace_column = str(col.name)
                    break
            if _trace_table is not None:
                break
    assert _trace_table is not None and _trace_column is not None
    happy_path_args: dict[str, dict[str, object]] = {
        "list_templates": {},
        "get_schema": {},
        "describe_capability": {"area": "curves"},
        "get_template": {"name": "saas"},
        "validate_config": {"config": saas_yaml},
        "preview": {"config": saas_yaml},
        "create_dataset": {"template_or_config": _TINY_CONFIG, "seed": 67},
        "describe_run": {"run_id": created["run_id"]},
        "get_validation_report": {"run_id": created["run_id"]},
        "trace_cell": {
            "run_id": created["run_id"],
            "table": _trace_table,
            "row_id": "0",
            "column": _trace_column,
        },
        "load_run": {"run_id": created["run_id"]},
    }

    server = build_server()
    async with create_connected_server_and_client_session(server._mcp_server) as session:
        tools = await session.list_tools()
        registered_names = {t.name for t in tools.tools}

        # Sanity guard: every name we plan to call must actually be
        # registered on the server, otherwise the loop silently skips.
        assert registered_names == set(happy_path_args.keys()), (
            f"happy-path arg map drift: registered={registered_names}, "
            f"covered={set(happy_path_args.keys())}"
        )

        for tool_name in sorted(registered_names):
            args = happy_path_args[tool_name]
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
