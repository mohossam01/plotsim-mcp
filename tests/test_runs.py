"""Coverage for :mod:`plotsim_mcp.runs` — run-id determinism, sandbox-root
override, allocation collision handling, and the path-traversal refusal.

The sandbox-root override goes through ``monkeypatch.setenv`` + a tmp_path
so each test runs against a fresh directory and never touches the operator's
real ``$PLOTSIM_MCP_RUN_ROOT`` (or the system temp dir).
"""
from __future__ import annotations

import datetime as _dt
from pathlib import Path

import pytest

from plotsim_mcp import runs


@pytest.fixture(autouse=True)
def _isolated_sandbox(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    root = tmp_path / "runs"
    monkeypatch.setenv(runs.ENV_VAR, str(root))
    return root


def test_sandbox_root_honors_env_var(_isolated_sandbox: Path) -> None:
    root = runs.sandbox_root()
    assert root == _isolated_sandbox
    assert root.is_dir()


def test_sandbox_root_falls_back_to_temp_when_unset(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # Force the override OFF for this test; redirect the system temp dir so
    # we don't pollute the operator's real /tmp.
    monkeypatch.delenv(runs.ENV_VAR, raising=False)
    monkeypatch.setenv("TMPDIR", str(tmp_path))
    monkeypatch.setenv("TEMP", str(tmp_path))
    monkeypatch.setenv("TMP", str(tmp_path))
    import importlib
    import tempfile as _tempfile

    importlib.reload(_tempfile)
    root = runs.sandbox_root()
    assert root.name == "plotsim-mcp-runs"
    assert root.is_dir()


def test_generate_run_id_format() -> None:
    moment = _dt.datetime(2026, 5, 24, 18, 30, 5, tzinfo=_dt.timezone.utc)
    rid = runs.generate_run_id("about: x\n", seed=42, moment=moment)
    timestamp, _, sha = rid.partition("-")
    assert timestamp == "20260524T183005Z"
    assert len(sha) == 8
    assert all(c in "0123456789abcdef" for c in sha)


def test_generate_run_id_is_deterministic_for_same_inputs() -> None:
    moment = _dt.datetime(2026, 5, 24, tzinfo=_dt.timezone.utc)
    a = runs.generate_run_id("config: same\n", seed=7, moment=moment)
    b = runs.generate_run_id("config: same\n", seed=7, moment=moment)
    assert a == b


def test_generate_run_id_changes_with_seed() -> None:
    moment = _dt.datetime(2026, 5, 24, tzinfo=_dt.timezone.utc)
    a = runs.generate_run_id("config: same\n", seed=1, moment=moment)
    b = runs.generate_run_id("config: same\n", seed=2, moment=moment)
    assert a != b


def test_generate_run_id_changes_with_config_text() -> None:
    moment = _dt.datetime(2026, 5, 24, tzinfo=_dt.timezone.utc)
    a = runs.generate_run_id("config: a\n", seed=1, moment=moment)
    b = runs.generate_run_id("config: b\n", seed=1, moment=moment)
    assert a != b


def test_generate_run_id_uses_now_when_moment_omitted() -> None:
    # No fixed moment — just assert the timestamp parses as a UTC stamp
    # within the current minute window.
    rid = runs.generate_run_id("config\n", seed=0)
    stamp = rid.split("-", 1)[0]
    parsed = _dt.datetime.strptime(stamp, "%Y%m%dT%H%M%SZ")
    delta = abs(
        (_dt.datetime.now(tz=_dt.timezone.utc).replace(tzinfo=None) - parsed).total_seconds()
    )
    assert delta < 60


def test_allocate_creates_fresh_directory() -> None:
    rid = "20260524T000000Z-abc12345"
    path = runs.allocate(rid)
    assert path.is_dir()
    assert path.name == rid


def test_allocate_resolves_collision_with_suffix() -> None:
    rid = "20260524T000000Z-collide1"
    first = runs.allocate(rid)
    second = runs.allocate(rid)
    third = runs.allocate(rid)
    assert first != second != third
    assert first.name == rid
    assert second.name == f"{rid}-1"
    assert third.name == f"{rid}-2"


def test_resolve_returns_existing_directory() -> None:
    rid = "20260524T000000Z-deadbeef"
    created = runs.allocate(rid)
    found = runs.resolve(rid)
    assert found == created


def test_resolve_raises_runnotfound_when_missing() -> None:
    with pytest.raises(runs.RunNotFound):
        runs.resolve("20260524T000000Z-nopath00")


def test_ensure_within_sandbox_accepts_subpath() -> None:
    rid = "20260524T000000Z-subok123"
    created = runs.allocate(rid)
    nested = created / "nested" / "file.csv"
    nested.parent.mkdir(parents=True, exist_ok=True)
    nested.write_text("ok")
    resolved = runs.ensure_within_sandbox(nested)
    assert resolved == nested.resolve()


def test_ensure_within_sandbox_rejects_outside_path(tmp_path: Path) -> None:
    outside = tmp_path / "outside" / "elsewhere"
    outside.mkdir(parents=True)
    with pytest.raises(runs.PathForbidden):
        runs.ensure_within_sandbox(outside)


def test_ensure_within_sandbox_rejects_traversal() -> None:
    root = runs.sandbox_root()
    traversal = root / ".." / ".." / "evil"
    with pytest.raises(runs.PathForbidden):
        runs.ensure_within_sandbox(traversal)
