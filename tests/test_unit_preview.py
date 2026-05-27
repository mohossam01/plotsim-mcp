"""Unit coverage for ``preview`` — happy path against a minimal valid
config, failure paths raise the typed exceptions the wrapper translates
into structured errors.
"""
from __future__ import annotations

import pytest
import yaml
from pydantic import ValidationError

from plotsim_mcp.tools.preview import (
    _CELL_SOFT_BUDGET_DEFAULT,
    _is_budget_exceeded,
    preview_payload,
)


_MINIMAL_VALID: dict = {
    "about": "preview unit fixture",
    "unit": "customer",
    "window": {"start": "2024-01", "end": "2024-06", "every": "monthly"},
    "segments": [{"name": "cohort_a", "count": 10, "archetype": "growth"}],
    "metrics": [
        {"name": "engagement", "type": "score", "polarity": "positive"}
    ],
}


def test_minimal_valid_returns_envelope() -> None:
    payload = preview_payload(_MINIMAL_VALID)
    assert payload["entities"] == 10
    assert payload["periods"] == 6  # Jan-Jun monthly
    assert payload["domain"]  # interpreter fills the domain name
    assert payload["tables"]["total"] >= 1
    assert payload["exceeds_budget"] is False
    assert payload["headroom"] > 0
    assert payload["cell_count"] == 60  # 10 entities × 6 periods
    assert payload["cell_budget"] == _CELL_SOFT_BUDGET_DEFAULT


def test_yaml_string_input_supported() -> None:
    payload = preview_payload(yaml.safe_dump(_MINIMAL_VALID))
    assert payload["entities"] == 10


def test_archetypes_in_use_reports_builder_shape_words() -> None:
    """``archetypes_in_use`` surfaces the user-authored archetype words,
    not the post-interpret per-segment instance names. Two segments
    sharing the same archetype dedupe to a single value.
    """
    cfg = {
        **_MINIMAL_VALID,
        "segments": [
            {"name": "alpha_cohort", "count": 5, "archetype": "growth"},
            {"name": "beta_cohort", "count": 5, "archetype": "growth"},
        ],
    }
    payload = preview_payload(cfg)
    assert payload["archetypes_in_use"] == ["growth"]


def test_archetypes_in_use_preserves_distinct_words() -> None:
    cfg = {
        **_MINIMAL_VALID,
        "segments": [
            {"name": "alpha_cohort", "count": 5, "archetype": "growth"},
            {"name": "beta_cohort", "count": 5, "archetype": "decline"},
        ],
    }
    payload = preview_payload(cfg)
    assert payload["archetypes_in_use"] == ["decline", "growth"]


def test_non_dict_yaml_raises_typeerror() -> None:
    with pytest.raises(TypeError):
        preview_payload("just a string, not a mapping")


def test_invalid_config_raises_validationerror() -> None:
    bogus: dict = {**_MINIMAL_VALID, "totally_unknown_key": 42}
    with pytest.raises(ValidationError):
        preview_payload(bogus)


def test_is_budget_exceeded_detects_message_signature() -> None:
    """Synthesize a ValidationError carrying the gate's wording."""
    try:
        from pydantic import BaseModel, model_validator

        class _Probe(BaseModel):
            n: int

            @model_validator(mode="after")
            def _gate(self) -> "_Probe":
                raise ValueError("Config produces 99,999,999 cells (entities × periods)")

        _Probe(n=1)
    except ValidationError as exc:
        assert _is_budget_exceeded(exc) is True
    else:
        pytest.fail("expected ValidationError from synthetic gate")


def test_is_budget_exceeded_false_on_other_errors() -> None:
    try:
        preview_payload({"about": "x", "unit": "u"})
    except ValidationError as exc:
        assert _is_budget_exceeded(exc) is False
    else:
        pytest.fail("expected ValidationError for incomplete config")
