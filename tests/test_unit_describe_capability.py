"""Unit coverage for ``describe_capability`` — happy path returns a
dict-wrapped values list; unknown area surfaces ``KeyError`` (which the
register-time wrapper translates into a ``plotsim.capability.unknown``
``ToolError``).
"""
from __future__ import annotations

import pytest

from plotsim_mcp.tools.describe_capability import (
    VALID_AREAS,
    describe_capability_payload,
)


def test_payload_shape_for_curves() -> None:
    payload = describe_capability_payload("curves")
    assert set(payload.keys()) == {"area", "values"}
    assert payload["area"] == "curves"
    assert isinstance(payload["values"], list)
    assert all(isinstance(v, str) for v in payload["values"])


def test_unknown_area_raises_keyerror() -> None:
    with pytest.raises(KeyError):
        describe_capability_payload("not_a_real_area")


@pytest.mark.parametrize("area", VALID_AREAS)
def test_every_valid_area_returns_a_list(area: str) -> None:
    payload = describe_capability_payload(area)
    assert payload["area"] == area
    assert isinstance(payload["values"], list)


def test_values_sorted_for_curves() -> None:
    """Sorted output is part of the contract — clients shouldn't have to
    re-sort. Curves is the easiest to lock because the registry is stable."""
    payload = describe_capability_payload("curves")
    assert payload["values"] == sorted(payload["values"])
