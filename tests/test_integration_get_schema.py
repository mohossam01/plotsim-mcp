"""Integration coverage for ``get_schema`` — assert the unmocked
``PlotsimConfig.model_json_schema()`` output carries the surfaces plotsim
documents publicly. This is the test that catches a real schema regression
(e.g. someone renamed ``window`` on the engine model).
"""
from __future__ import annotations

from plotsim_mcp.tools.get_schema import get_schema_payload


def test_schema_lists_plotsim_config_as_title() -> None:
    schema = get_schema_payload()["schema"]
    # pydantic's default title is the class name.
    assert schema.get("title") == "PlotsimConfig"


def test_schema_top_level_is_object() -> None:
    schema = get_schema_payload()["schema"]
    assert schema.get("type") == "object"


def test_schema_carries_properties() -> None:
    schema = get_schema_payload()["schema"]
    props = schema.get("properties")
    assert isinstance(props, dict)
    assert props, "schema must declare at least one property"


def test_schema_includes_core_keys() -> None:
    schema = get_schema_payload()["schema"]
    props = schema.get("properties", {})
    # Sanity checks against the documented plotsim surface — these are
    # top-level keys the public README and tutorials reference. If a future
    # plotsim release renames any of them, MCP clients break.
    for required_key in ("seed", "time_window", "tables"):
        assert required_key in props, f"missing top-level property {required_key!r}"
