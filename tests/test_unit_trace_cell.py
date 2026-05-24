"""Unit coverage for ``trace_cell`` helpers — ``_trace_source_for`` keys
off the manifest's ``trajectory_samples`` list to decide whether a trace
was sourced from the manifest or re-derived from seed; ``_find_table_file``
walks the supported extensions in priority order; ``trace_cell_payload``
raises :class:`plotsim_mcp.runs.RunNotFound` for unknown ids.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from plotsim_mcp import runs
from plotsim_mcp.tools.trace_cell import (
    _find_table_file,
    _RowNotFound,
    _trace_source_for,
    trace_cell_payload,
)


@pytest.fixture(autouse=True)
def _isolated_sandbox(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    monkeypatch.setenv(runs.ENV_VAR, str(tmp_path / "runs"))
    return tmp_path / "runs"


def test_trace_source_falls_back_when_manifest_missing(tmp_path: Path) -> None:
    assert _trace_source_for(tmp_path / "nope.json", "entity_a") == "rederived_from_seed"


def test_trace_source_falls_back_when_manifest_unparseable(tmp_path: Path) -> None:
    bad = tmp_path / "manifest.json"
    bad.write_text("{not valid json", encoding="utf-8")
    assert _trace_source_for(bad, "entity_a") == "rederived_from_seed"


def test_trace_source_returns_manifest_when_entity_sampled(tmp_path: Path) -> None:
    manifest = {
        "trajectory_samples": [
            {"entity": "entity_a", "period_index": 0, "position": 0.1},
            {"entity": "entity_a", "period_index": 1, "position": 0.2},
            {"entity": "entity_b", "period_index": 0, "position": 0.3},
        ],
    }
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    assert _trace_source_for(path, "entity_a") == "manifest"


def test_trace_source_returns_rederived_when_entity_not_sampled(tmp_path: Path) -> None:
    manifest = {
        "trajectory_samples": [
            {"entity": "entity_a", "period_index": 0, "position": 0.1},
        ],
    }
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    assert _trace_source_for(path, "entity_zzz") == "rederived_from_seed"


def test_find_table_file_prefers_csv_when_present(tmp_path: Path) -> None:
    (tmp_path / "fct_users.csv").write_text("col\n", encoding="utf-8")
    (tmp_path / "fct_users.parquet").write_text("ignored", encoding="utf-8")
    assert _find_table_file(tmp_path, "fct_users").suffix == ".csv"


def test_find_table_file_falls_back_to_parquet_when_csv_absent(tmp_path: Path) -> None:
    (tmp_path / "fct_users.parquet").write_text("ignored", encoding="utf-8")
    assert _find_table_file(tmp_path, "fct_users").suffix == ".parquet"


def test_find_table_file_raises_when_no_supported_extension(tmp_path: Path) -> None:
    (tmp_path / "fct_users.txt").write_text("x", encoding="utf-8")
    with pytest.raises(_RowNotFound):
        _find_table_file(tmp_path, "fct_users")


def test_trace_cell_payload_unknown_run_raises() -> None:
    with pytest.raises(runs.RunNotFound):
        trace_cell_payload(
            "20260524T000000Z-missing0",
            table="fct_x",
            row_id="0",
            column="some_metric",
        )
