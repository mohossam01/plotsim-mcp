"""Unit coverage for ``get_sandbox_root`` — payload shape; env_var key is
fixed at ``PLOTSIM_MCP_RUN_ROOT``; sandbox_root key matches
``runs.sandbox_root()`` at call time.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from plotsim_mcp import runs
from plotsim_mcp.tools.get_sandbox_root import get_sandbox_root_payload


@pytest.fixture(autouse=True)
def _isolated_sandbox(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    monkeypatch.setenv(runs.ENV_VAR, str(tmp_path / "runs"))
    return tmp_path / "runs"


def test_payload_shape_keys() -> None:
    payload = get_sandbox_root_payload()
    assert set(payload.keys()) == {"sandbox_root", "env_var"}


def test_env_var_is_canonical_constant() -> None:
    payload = get_sandbox_root_payload()
    assert payload["env_var"] == "PLOTSIM_MCP_RUN_ROOT"
    # And matches the module constant — guards against the docstring
    # drifting from runs.ENV_VAR.
    assert payload["env_var"] == runs.ENV_VAR


def test_sandbox_root_matches_runs_module(_isolated_sandbox: Path) -> None:
    payload = get_sandbox_root_payload()
    # ``runs.sandbox_root()`` resolves to the env-var-set path and creates
    # it on read. Compare via Path.resolve() so trailing slashes and
    # case-normalization (Windows) don't false-fail.
    assert Path(payload["sandbox_root"]).resolve() == runs.sandbox_root().resolve()


def test_sandbox_root_directory_exists_after_call(_isolated_sandbox: Path) -> None:
    # Side-effect of ``runs.sandbox_root()`` is creation-on-read; the
    # tool inherits that, so the path is real on return.
    payload = get_sandbox_root_payload()
    assert Path(payload["sandbox_root"]).is_dir()


def test_sandbox_root_responds_to_env_override(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    custom = tmp_path / "custom-sandbox"
    monkeypatch.setenv(runs.ENV_VAR, str(custom))
    payload = get_sandbox_root_payload()
    assert Path(payload["sandbox_root"]).resolve() == custom.resolve()
