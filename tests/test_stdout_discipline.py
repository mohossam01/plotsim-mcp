"""Stdout-discipline regression — every wired tool's library path must
produce zero bytes on ``sys.stdout``. The MCP stdio transport interleaves
JSON-RPC frames on stdout; a stray byte from inside a tool function
corrupts the frame and the client either drops the message or terminates
the session.

The audit at ``project/notes/plotsim-stdout-audit-2026-05.md`` (plotsim
repo) confirmed that no plotsim library call writes to stdout as of
plotsim 0.7.0. This test catches a future regression — either a plotsim
release that changes a ``sys.stderr.write`` to ``print(...)``, or a new
plotsim-mcp tool that forgets the discipline.

The check uses ``contextlib.redirect_stdout`` rather than spawning a
subprocess so the test stays fast and runs in CI without requiring the
package to be installed under the test runner's interpreter. Subprocess
isolation is achieved indirectly: each tool runs against fresh state via
``tmp_path`` + the ``PLOTSIM_MCP_RUN_ROOT`` env var.
"""
from __future__ import annotations

import contextlib
import importlib.resources as _resources
import io
from pathlib import Path

import pytest

from plotsim_mcp import runs
from plotsim_mcp.tools.create_dataset import create_dataset_payload
from plotsim_mcp.tools.describe_capability import describe_capability_payload
from plotsim_mcp.tools.describe_run import describe_run_payload
from plotsim_mcp.tools.get_sandbox_root import get_sandbox_root_payload
from plotsim_mcp.tools.get_schema import get_schema_payload
from plotsim_mcp.tools.get_template import get_template_payload
from plotsim_mcp.tools.get_validation_report import get_validation_report_payload
from plotsim_mcp.tools.list_runs import list_runs_payload
from plotsim_mcp.tools.list_templates import list_templates_payload
from plotsim_mcp.tools.load_run import load_run_payload
from plotsim_mcp.tools.preview import preview_payload
from plotsim_mcp.tools.trace_cell import _load_config as _trace_load_config
from plotsim_mcp.tools.trace_cell import trace_cell_payload
from plotsim_mcp.tools.validate_config import validate_config_payload


_TINY_CONFIG: dict = {
    "about": "stdout discipline fixture",
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


def _capture_stdout(fn) -> str:  # type: ignore[no-untyped-def]
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        fn()
    return buf.getvalue()


def _assert_clean(captured: str, tool_name: str) -> None:
    assert captured == "", (
        f"{tool_name} wrote {len(captured)} byte(s) to stdout: "
        f"{captured[:200]!r}"
    )
    # Belt + suspenders: catch the specific banner the M035 finding
    # named, even if some future code path manages to drop it on stdout
    # via a different write call.
    assert "Config summary:" not in captured, (
        f"{tool_name} leaked the Config summary banner to stdout"
    )


def test_list_templates_writes_no_stdout() -> None:
    _assert_clean(_capture_stdout(lambda: list_templates_payload()), "list_templates")


def test_get_schema_writes_no_stdout() -> None:
    _assert_clean(_capture_stdout(lambda: get_schema_payload()), "get_schema")


@pytest.mark.parametrize(
    "area",
    [
        "archetypes",
        "curves",
        "distributions",
        "arrival_shapes",
        "output_formats",
        "quality_types",
        "validation_checks",
    ],
)
def test_describe_capability_writes_no_stdout(area: str) -> None:
    _assert_clean(
        _capture_stdout(lambda: describe_capability_payload(area)),
        f"describe_capability({area})",
    )


def test_get_template_writes_no_stdout() -> None:
    _assert_clean(
        _capture_stdout(lambda: get_template_payload("saas")),
        "get_template",
    )


def test_validate_config_writes_no_stdout() -> None:
    yaml_text = _saas_yaml_text()
    _assert_clean(
        _capture_stdout(lambda: validate_config_payload(yaml_text)),
        "validate_config",
    )


def test_preview_writes_no_stdout() -> None:
    yaml_text = _saas_yaml_text()
    _assert_clean(
        _capture_stdout(lambda: preview_payload(yaml_text)),
        "preview",
    )


def test_create_dataset_writes_no_stdout() -> None:
    _assert_clean(
        _capture_stdout(lambda: create_dataset_payload(_TINY_CONFIG, seed=71)),
        "create_dataset",
    )


def test_describe_run_writes_no_stdout() -> None:
    created = create_dataset_payload(_TINY_CONFIG, seed=73)
    _assert_clean(
        _capture_stdout(lambda: describe_run_payload(created["run_id"])),
        "describe_run",
    )


def test_get_validation_report_writes_no_stdout() -> None:
    created = create_dataset_payload(_TINY_CONFIG, seed=79)
    _assert_clean(
        _capture_stdout(
            lambda: get_validation_report_payload(created["run_id"])
        ),
        "get_validation_report",
    )


def test_load_run_writes_no_stdout() -> None:
    created = create_dataset_payload(_TINY_CONFIG, seed=83)
    _assert_clean(
        _capture_stdout(lambda: load_run_payload(created["run_id"])),
        "load_run",
    )


def test_list_runs_writes_no_stdout() -> None:
    # Create one run first so the listing has at least one entry — the
    # iterdir + per-entry stat path is what stdout-discipline most
    # plausibly regresses on if a future change adds a debug print.
    create_dataset_payload(_TINY_CONFIG, seed=91)
    _assert_clean(_capture_stdout(lambda: list_runs_payload()), "list_runs")


def test_get_sandbox_root_writes_no_stdout() -> None:
    _assert_clean(
        _capture_stdout(lambda: get_sandbox_root_payload()),
        "get_sandbox_root",
    )


def test_trace_cell_writes_no_stdout() -> None:
    from plotsim_mcp import runs as _runs
    from plotsim.config import MetricSource, parse_source

    created = create_dataset_payload(_TINY_CONFIG, seed=89)
    run_dir = _runs.resolve(created["run_id"])
    config = _trace_load_config(run_dir)
    table_name: str | None = None
    column_name: str | None = None
    for tbl in config.tables:
        if (
            getattr(tbl, "type", None) == "fact"
            and getattr(tbl, "grain", None) == "per_entity_per_period"
        ):
            for col in tbl.columns:
                if isinstance(parse_source(col.source), MetricSource):
                    table_name = str(tbl.name)
                    column_name = str(col.name)
                    break
            if table_name is not None:
                break
    assert table_name is not None and column_name is not None
    _assert_clean(
        _capture_stdout(
            lambda: trace_cell_payload(
                created["run_id"], table_name, "0", column_name
            )
        ),
        "trace_cell",
    )
