"""Unit test for ``list_templates`` payload assembly with plotsim mocked.

Verifies the shape of the returned payload and that the description
lookup is invoked once per template name returned by plotsim.
"""
from __future__ import annotations

from unittest.mock import patch

from plotsim_mcp.tools import list_templates as mod


def test_payload_combines_names_with_about_text() -> None:
    fake_names = ["alpha", "beta"]
    fake_about = {"alpha": "first domain", "beta": "second domain"}

    with (
        patch.object(mod.plotsim, "list_templates", return_value=fake_names),
        patch.object(mod, "_template_about", side_effect=lambda n: fake_about[n]),
    ):
        out = mod.list_templates_payload()

    assert out == [
        {"name": "alpha", "description": "first domain"},
        {"name": "beta", "description": "second domain"},
    ]


def test_payload_preserves_plotsim_ordering() -> None:
    fake_names = ["zeta", "alpha", "mu"]

    with (
        patch.object(mod.plotsim, "list_templates", return_value=fake_names),
        patch.object(mod, "_template_about", return_value="desc"),
    ):
        out = mod.list_templates_payload()

    assert [item["name"] for item in out] == ["zeta", "alpha", "mu"]


def test_empty_template_list_returns_empty_payload() -> None:
    with patch.object(mod.plotsim, "list_templates", return_value=[]):
        out = mod.list_templates_payload()
    assert out == []
