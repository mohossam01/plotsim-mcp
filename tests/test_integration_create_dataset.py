"""Integration coverage for ``create_dataset`` — happy path against a
bundled template name, and overrides path against the tiny synthetic
fixture. Sandbox redirected to ``tmp_path`` so each test runs in
isolation.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from plotsim_mcp import runs
from plotsim_mcp.tools.create_dataset import create_dataset_payload


@pytest.fixture(autouse=True)
def _isolated_sandbox(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    monkeypatch.setenv(runs.ENV_VAR, str(tmp_path / "runs"))
    return tmp_path / "runs"


_TINY_CONFIG: dict = {
    "about": "create_dataset integration fixture",
    "unit": "customer",
    "window": {"start": "2024-01", "end": "2024-03", "every": "monthly"},
    "segments": [{"name": "cohort_a", "count": 4, "archetype": "growth"}],
    "metrics": [
        {"name": "engagement", "type": "score", "polarity": "positive"}
    ],
}


def test_template_name_input_produces_valid_run(_isolated_sandbox: Path) -> None:
    # ``hr`` is one of the smaller bundled templates; using a real template
    # name exercises the get_template branch end-to-end.
    envelope = create_dataset_payload("hr", seed=7)
    assert envelope["run_id"]
    out = Path(envelope["output_dir"])
    assert out.is_dir()
    files = {p.name for p in out.iterdir() if p.is_file()}
    assert "config.yaml" in files
    assert "validation_report.txt" in files


def test_overrides_are_applied(_isolated_sandbox: Path) -> None:
    envelope = create_dataset_payload(
        _TINY_CONFIG,
        seed=11,
        overrides={"segments.0.count": 6},
    )
    out = Path(envelope["output_dir"])
    # Re-read the persisted config.yaml — it reflects what plotsim actually
    # ran against, which is the post-override state.
    import yaml as _yaml

    persisted = _yaml.safe_load((out / "config.yaml").read_text(encoding="utf-8"))
    # plotsim writes the engine-interpreted config, where segment counts
    # surface under ``entities[].size``. Reading the dim_<entity> CSV row
    # count is the load-bearing assertion the count was honored.
    import pandas as pd

    dim_customer = pd.read_csv(out / "dim_customer.csv")
    assert len(dim_customer) == 6
    # config.yaml is structurally valid even if we don't dig into its
    # interpreted shape; the deep-equality is too brittle to assert here.
    assert isinstance(persisted, dict)


def test_format_override_honored(_isolated_sandbox: Path) -> None:
    envelope = create_dataset_payload(_TINY_CONFIG, seed=13, fmt="jsonl")
    out = Path(envelope["output_dir"])
    files = {p.suffix for p in out.iterdir() if p.is_file()}
    assert ".jsonl" in files


def test_same_seed_and_config_same_run_id(_isolated_sandbox: Path) -> None:
    envelope_a = create_dataset_payload(_TINY_CONFIG, seed=17)
    envelope_b = create_dataset_payload(_TINY_CONFIG, seed=17)
    # Same logical inputs land at the SAME run_id; the on-disk dir gets a
    # collision suffix (the second call uses runs.allocate, which appends).
    assert envelope_a["run_id"] == envelope_b["run_id"]
    assert envelope_a["output_dir"] != envelope_b["output_dir"]
