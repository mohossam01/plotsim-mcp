"""Unit coverage for ``validate_config`` — happy path returns
``{"valid": True, "warnings": [...]}`` for a minimal valid dict; failure
paths raise the typed exceptions the register-time wrapper turns into a
``plotsim.config.invalid`` ``ToolError``.
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from plotsim_mcp.tools.validate_config import (
    _format_pydantic_errors,
    validate_config_payload,
)

# A minimum-viable UserInput dict: about + unit + window + one segment + one
# metric. The builder considers this acceptable structurally; whether the
# resulting config is semantically interesting is the user's call.
_MINIMAL_VALID: dict = {
    "about": "minimal validation fixture",
    "unit": "customer",
    "window": {"start": "2024-01", "end": "2024-06", "every": "monthly"},
    "segments": [{"name": "cohort_a", "count": 10, "archetype": "growth"}],
    "metrics": [
        {"name": "engagement", "type": "score", "polarity": "positive"}
    ],
}


def test_minimal_valid_input_returns_valid_true() -> None:
    payload = validate_config_payload(_MINIMAL_VALID)
    assert payload["valid"] is True
    assert isinstance(payload["warnings"], list)


def test_yaml_string_input_is_supported() -> None:
    import yaml as _yaml

    payload = validate_config_payload(_yaml.safe_dump(_MINIMAL_VALID))
    assert payload["valid"] is True


def test_structural_error_raises_validationerror() -> None:
    # ``entities`` requires at least one entry; passing an unknown top-level
    # key trips pydantic's ``extra=forbid``.
    bogus: dict = {**_MINIMAL_VALID, "totally_unknown_key": 42}
    with pytest.raises(ValidationError):
        validate_config_payload(bogus)


def test_non_dict_yaml_raises_typeerror() -> None:
    with pytest.raises(TypeError):
        validate_config_payload("just a string, not a mapping")


def test_format_pydantic_errors_shape() -> None:
    try:
        validate_config_payload({"window": "not a dict"})
    except ValidationError as exc:
        formatted = _format_pydantic_errors(exc)
        assert formatted, "expected at least one formatted error entry"
        for entry in formatted:
            assert set(entry.keys()) == {"loc", "msg", "type"}
    else:
        pytest.fail("expected ValidationError")
