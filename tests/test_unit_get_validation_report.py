"""Unit coverage for ``get_validation_report`` — Status-line parser, then
the resolution layer against a sandbox dir.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from plotsim_mcp import runs
from plotsim_mcp.tools.get_validation_report import (
    _parse_ok,
    get_validation_report_payload,
)


@pytest.fixture(autouse=True)
def _isolated_sandbox(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    monkeypatch.setenv(runs.ENV_VAR, str(tmp_path / "runs"))
    return tmp_path / "runs"


def test_parse_ok_matches_valid_status() -> None:
    text = "Plotsim Validation Report\nStatus: VALID\n"
    assert _parse_ok(text) is True


def test_parse_ok_matches_invalid_status() -> None:
    text = "Plotsim Validation Report\nStatus: INVALID\n"
    assert _parse_ok(text) is False


def test_parse_ok_missing_status_line_returns_false() -> None:
    assert _parse_ok("no status line here") is False


def test_get_validation_report_payload_real_dir() -> None:
    rid = "20260524T000000Z-validrep"
    run_dir = runs.allocate(rid)
    body = (
        "Plotsim Validation Report\n"
        "==========================\n"
        "Generated: deterministic\n"
        "Errors: 0 | Warnings: 1 | Total: 1\n"
        "Status: VALID\n"
        "\n"
    )
    (run_dir / "validation_report.txt").write_text(body, encoding="utf-8")

    envelope = get_validation_report_payload(rid)
    assert envelope["run_id"] == rid
    assert envelope["ok"] is True
    assert "Status: VALID" in envelope["report"]


def test_get_validation_report_payload_missing_report_returns_empty() -> None:
    rid = "20260524T000000Z-noreport"
    runs.allocate(rid)
    envelope = get_validation_report_payload(rid)
    assert envelope["report"] == ""
    assert envelope["ok"] is False


def test_get_validation_report_payload_unknown_id_raises() -> None:
    with pytest.raises(runs.RunNotFound):
        get_validation_report_payload("20260524T000000Z-missing0")
