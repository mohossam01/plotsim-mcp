"""Integration coverage for ``validate_config`` — every bundled template
must validate successfully when fed through the tool (proves the happy
path covers the published templates) and a known-invalid mutation must
surface a structured error.
"""
from __future__ import annotations

import importlib.resources as _resources

import plotsim
import pytest
import yaml
from pydantic import ValidationError

from plotsim_mcp.tools.validate_config import validate_config_payload

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
def test_every_bundled_template_validates(name: str) -> None:
    template = _read_template(name)
    payload = validate_config_payload(template)
    assert payload["valid"] is True


def test_invalid_input_raises_validation_error() -> None:
    template = _read_template("saas")
    # Replace `window` with garbage — should trip pydantic.
    broken = {**template, "window": 42}
    with pytest.raises(ValidationError):
        validate_config_payload(broken)
