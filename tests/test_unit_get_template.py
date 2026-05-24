"""Unit coverage for ``get_template`` — payload shape and unknown-name path.
Reads through ``importlib.resources``, so the only mocking happens in the
unknown-name test (the real bundled set is small enough to use directly).
"""
from __future__ import annotations

import pytest

from plotsim_mcp.tools.get_template import get_template_payload


def test_payload_shape_keys() -> None:
    payload = get_template_payload("saas")
    assert set(payload.keys()) == {"name", "yaml", "parsed"}


def test_yaml_text_is_non_empty_string() -> None:
    payload = get_template_payload("saas")
    assert isinstance(payload["yaml"], str)
    assert payload["yaml"].strip()


def test_parsed_round_trips_yaml() -> None:
    import yaml as _yaml

    payload = get_template_payload("saas")
    re_parsed = _yaml.safe_load(payload["yaml"])
    assert re_parsed == payload["parsed"]


def test_unknown_template_raises_keyerror() -> None:
    with pytest.raises(KeyError):
        get_template_payload("definitely_not_a_template")
