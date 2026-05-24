"""Integration test — calls the unmocked payload function against real plotsim.

Asserts the bundled six domain templates surface with non-empty
descriptions. If plotsim ships a new bundled template, this test
will fail loudly so the catalogue stays in sync.
"""
from __future__ import annotations

from plotsim_mcp.tools.list_templates import list_templates_payload

EXPECTED_TEMPLATES = {"banking", "health", "hr", "marketing", "retail", "saas"}


def test_returns_bundled_six_templates() -> None:
    out = list_templates_payload()
    names = {item["name"] for item in out}
    assert names == EXPECTED_TEMPLATES


def test_every_template_has_non_empty_description() -> None:
    for item in list_templates_payload():
        assert item["description"], (
            f"template {item['name']!r} has empty description; "
            "check the template YAML's `about:` field"
        )


def test_payload_entries_have_exactly_two_keys() -> None:
    for item in list_templates_payload():
        assert set(item.keys()) == {"name", "description"}
