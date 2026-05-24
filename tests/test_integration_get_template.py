"""Integration coverage for ``get_template`` — every bundled template must
read back through the tool, and the parsed dict must carry the documented
top-level keys (``about``, ``segments``, etc.).
"""
from __future__ import annotations

import plotsim
import pytest

from plotsim_mcp.tools.get_template import get_template_payload


@pytest.mark.parametrize("name", plotsim.list_templates())
def test_every_bundled_template_loads(name: str) -> None:
    payload = get_template_payload(name)
    assert payload["name"] == name
    assert payload["yaml"].strip()
    assert isinstance(payload["parsed"], dict)


@pytest.mark.parametrize("name", plotsim.list_templates())
def test_each_template_carries_about_and_segments(name: str) -> None:
    payload = get_template_payload(name)
    parsed = payload["parsed"]
    assert "about" in parsed, f"template {name!r} missing 'about' field"
    assert isinstance(parsed.get("segments"), list)
    assert parsed["segments"], f"template {name!r} has no segments"
