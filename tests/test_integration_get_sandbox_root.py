"""Integration coverage for ``get_sandbox_root`` — assert the returned
path round-trips with ``create_dataset.output_dir`` (the gap-closing
acceptance the tool exists for).
"""
from __future__ import annotations

from pathlib import Path

import pytest

from plotsim_mcp import runs
from plotsim_mcp.tools.create_dataset import create_dataset_payload
from plotsim_mcp.tools.get_sandbox_root import get_sandbox_root_payload


_TINY_CONFIG: dict = {
    "about": "get_sandbox_root integration fixture",
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


def test_returned_path_accepts_create_dataset_output_dir() -> None:
    """The discoverability gap the tool closes — a caller fetches the
    sandbox root and uses it to construct an explicit ``output_dir``
    that ``create_dataset`` won't refuse.
    """
    root_payload = get_sandbox_root_payload()
    target = Path(root_payload["sandbox_root"]) / "caller-allocated"
    envelope = create_dataset_payload(
        _TINY_CONFIG, seed=173, output_dir=str(target)
    )
    assert Path(envelope["output_dir"]).resolve() == target.resolve()
    assert (target / "config.yaml").is_file()
