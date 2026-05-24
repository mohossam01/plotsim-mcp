"""Unit coverage for ``create_dataset`` helpers and the payload function on
a small in-memory config. The full plotsim pipeline runs end-to-end here
because the path-resolution / run_id / output-dir logic only meaningfully
exercises against a real generation pass.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml
from pydantic import ValidationError

from plotsim_mcp import runs
from plotsim_mcp.tools.create_dataset import (
    _apply_overrides,
    _is_budget_exceeded,
    _looks_like_template_name,
    _resolve_template_or_config,
    _validation_summary,
    create_dataset_payload,
)


_TINY_CONFIG: dict = {
    "about": "create_dataset unit fixture",
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


def test_looks_like_template_name_accepts_bare_word() -> None:
    assert _looks_like_template_name("saas") is True


def test_looks_like_template_name_rejects_yaml_with_colon() -> None:
    assert _looks_like_template_name("about: x") is False


def test_resolve_template_or_config_dict_is_deep_copied() -> None:
    original: dict[str, Any] = {"about": "x", "nested": {"v": 1}}
    out = _resolve_template_or_config(original)
    out["nested"]["v"] = 99
    assert original["nested"]["v"] == 1


def test_resolve_template_or_config_loads_template_name() -> None:
    parsed = _resolve_template_or_config("saas")
    assert parsed["about"]
    assert isinstance(parsed["segments"], list)


def test_resolve_template_or_config_unknown_name_raises_keyerror() -> None:
    with pytest.raises(KeyError):
        _resolve_template_or_config("nonexistent_template_xyz")


def test_resolve_template_or_config_yaml_string() -> None:
    parsed = _resolve_template_or_config(yaml.safe_dump(_TINY_CONFIG))
    assert parsed["about"] == _TINY_CONFIG["about"]


def test_apply_overrides_walks_dict_and_list() -> None:
    cfg: dict[str, Any] = {
        "seed": 0,
        "segments": [{"name": "a", "count": 10}, {"name": "b", "count": 20}],
        "output": {"format": "csv"},
    }
    _apply_overrides(
        cfg,
        {
            "seed": 99,
            "segments.0.count": 7,
            "output.format": "parquet",
        },
    )
    assert cfg["seed"] == 99
    assert cfg["segments"][0]["count"] == 7
    assert cfg["output"]["format"] == "parquet"


def test_apply_overrides_creates_missing_dict_keys() -> None:
    cfg: dict = {"output": {}}
    _apply_overrides(cfg, {"output.new_key": "value"})
    assert cfg["output"]["new_key"] == "value"


def test_validation_summary_parses_real_report(tmp_path: Path) -> None:
    body = (
        "Plotsim Validation Report\n"
        "==========================\n"
        "Generated: deterministic\n"
        "Errors: 0 | Warnings: 2 | Total: 2\n"
        "Status: VALID\n"
        "\n"
    )
    path = tmp_path / "validation_report.txt"
    path.write_text(body, encoding="utf-8")
    summary = _validation_summary(path)
    assert summary["ok"] is True
    assert summary["errors"] == 0
    assert summary["warnings"] == 2


def test_validation_summary_missing_file_returns_default(tmp_path: Path) -> None:
    summary = _validation_summary(tmp_path / "missing.txt")
    assert summary["ok"] is False


def test_create_dataset_payload_happy_path(_isolated_sandbox: Path) -> None:
    envelope = create_dataset_payload(_TINY_CONFIG, seed=1)
    assert envelope["run_id"]
    output_dir = Path(envelope["output_dir"])
    assert output_dir.is_dir()
    assert output_dir.parent.resolve() == _isolated_sandbox.resolve()
    assert any(name.endswith(".csv") for name in envelope["tables_written"])
    assert envelope["validation_summary"]["ok"] is True


def test_create_dataset_payload_honors_caller_output_dir(
    _isolated_sandbox: Path,
) -> None:
    caller_dir = _isolated_sandbox / "explicit"
    caller_dir.mkdir(parents=True, exist_ok=True)
    envelope = create_dataset_payload(
        _TINY_CONFIG, seed=2, output_dir=str(caller_dir)
    )
    assert Path(envelope["output_dir"]).resolve() == caller_dir.resolve()


def test_create_dataset_payload_rejects_path_outside_sandbox(
    _isolated_sandbox: Path, tmp_path: Path
) -> None:
    outside = tmp_path / "elsewhere"
    outside.mkdir()
    with pytest.raises(runs.PathForbidden):
        create_dataset_payload(
            _TINY_CONFIG, seed=3, output_dir=str(outside)
        )


def test_create_dataset_payload_invalid_format_raises_valueerror(
    _isolated_sandbox: Path,
) -> None:
    with pytest.raises(ValueError):
        create_dataset_payload(_TINY_CONFIG, seed=4, fmt="excel")


def test_create_dataset_payload_invalid_config_raises_validationerror(
    _isolated_sandbox: Path,
) -> None:
    with pytest.raises(ValidationError):
        create_dataset_payload({"about": "x", "unit": "u"}, seed=5)


def test_is_budget_exceeded_false_on_normal_errors() -> None:
    try:
        create_dataset_payload({"about": "x", "unit": "u"}, seed=6)
    except ValidationError as exc:
        assert _is_budget_exceeded(exc) is False
    else:
        pytest.fail("expected ValidationError")
