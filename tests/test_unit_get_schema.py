"""Unit coverage for ``get_schema`` — verify the payload shape with the
underlying ``PlotsimConfig`` introspection mocked out, so this test fails on
contract drift rather than on schema content changes.
"""
from __future__ import annotations

from unittest.mock import patch

import plotsim

from plotsim_mcp.tools.get_schema import get_schema_payload


def test_payload_shape_keys() -> None:
    payload = get_schema_payload()
    assert set(payload.keys()) == {"schema", "schema_version"}


def test_schema_version_matches_plotsim_version() -> None:
    payload = get_schema_payload()
    assert payload["schema_version"] == plotsim.__version__


def test_schema_is_a_dict() -> None:
    payload = get_schema_payload()
    assert isinstance(payload["schema"], dict)


def test_schema_pulls_from_pydantic_model_json_schema() -> None:
    """Lock the introspection source — if someone swaps in a subprocess
    call to ``plotsim schema``, this test fails."""
    fake_schema = {"title": "FakePlotsimConfig", "type": "object"}
    with patch("plotsim.config.PlotsimConfig.model_json_schema", return_value=fake_schema):
        payload = get_schema_payload()
    assert payload["schema"] == fake_schema
