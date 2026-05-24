"""Integration coverage for ``preview`` — runs unmocked against the
bundled ``saas`` template and asserts:

  * Every bundled template passes the estimate path cleanly.
  * The estimated_rows figure agrees with plotsim's own ``_estimate_rows``
    helper to within ±1% (the mission-spec parity target).
"""
from __future__ import annotations

import importlib.resources as _resources

import plotsim
import pytest
import yaml

from plotsim_mcp.tools.preview import preview_payload

_TEMPLATE_PACKAGE = "plotsim.configs.templates"


def _read_template(name: str) -> dict:
    root = _resources.files(_TEMPLATE_PACKAGE)
    for candidate in (f"{name}.yaml", f"{name}_template.yaml"):
        entry = root / candidate
        if entry.is_file():
            parsed = yaml.safe_load(entry.read_text(encoding="utf-8"))
            assert isinstance(parsed, dict)
            return parsed
    raise FileNotFoundError(name)


@pytest.mark.parametrize("name", plotsim.list_templates())
def test_every_bundled_template_previews(name: str) -> None:
    payload = preview_payload(_read_template(name))
    assert payload["entities"] > 0
    assert payload["periods"] > 0
    assert payload["estimated_rows"] > 0
    assert payload["cell_count"] == payload["entities"] * payload["periods"]


def test_saas_estimated_rows_matches_plotsim_cli_within_1pct() -> None:
    from plotsim.cli import _estimate_periods, _estimate_rows

    template = _read_template("saas")
    payload = preview_payload(template)

    cfg = plotsim.create(**template)
    expected_periods = _estimate_periods(cfg)
    expected_rows = _estimate_rows(cfg, expected_periods)

    assert payload["periods"] == expected_periods
    assert abs(payload["estimated_rows"] - expected_rows) <= max(
        1, int(0.01 * expected_rows)
    )
