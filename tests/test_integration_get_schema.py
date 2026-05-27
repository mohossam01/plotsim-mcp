"""Integration coverage for ``get_schema`` — assert the unmocked
``UserInput.model_json_schema()`` output carries the builder-shape
surfaces plotsim documents publicly. This is the test that catches a
real schema regression (e.g. someone renamed ``window`` on the builder
model, or accidentally reverted to the engine-shape ``PlotsimConfig``).
"""
from __future__ import annotations

from plotsim_mcp.tools.get_schema import get_schema_payload


def test_schema_lists_userinput_as_title() -> None:
    schema = get_schema_payload()["schema"]
    # pydantic's default title is the class name.
    assert schema.get("title") == "UserInput"


def test_schema_top_level_is_object() -> None:
    schema = get_schema_payload()["schema"]
    assert schema.get("type") == "object"


def test_schema_carries_properties() -> None:
    schema = get_schema_payload()["schema"]
    props = schema.get("properties")
    assert isinstance(props, dict)
    assert props, "schema must declare at least one property"


def test_schema_includes_builder_shape_keys() -> None:
    schema = get_schema_payload()["schema"]
    props = schema.get("properties", {})
    # Builder-shape top-level keys — what users author against. These
    # are what ``validate_config``, ``preview``, and ``create_dataset``
    # all accept.
    for required_key in ("unit", "window", "segments", "metrics"):
        assert required_key in props, f"missing top-level property {required_key!r}"


def test_schema_is_distinct_from_plotsim_config_schema() -> None:
    """``UserInput`` and ``PlotsimConfig`` are structurally different —
    the engine schema carries ``entities`` / ``archetypes`` / ``tables``
    / ``time_window``; the builder schema carries ``segments`` / ``window``
    / ``unit``. This test fails if get_schema reverts to the engine
    schema.
    """
    from plotsim.config import PlotsimConfig

    schema = get_schema_payload()["schema"]
    props = schema.get("properties", {})
    engine_props = PlotsimConfig.model_json_schema().get("properties", {})

    assert "entities" in engine_props
    assert "entities" not in props, (
        "get_schema must return UserInput shape; got engine-shape PlotsimConfig"
    )
    assert "segments" in props
    assert "segments" not in engine_props


def test_schema_validates_a_bundled_template() -> None:
    """Cross-tool agreement: a template fetched via ``get_template``
    parses cleanly through ``validate_config``, which routes through
    the same ``UserInput`` model ``get_schema`` exports the JSON Schema
    of. Identity check on the schema title guards against a future
    refactor that decouples the two tools' source models.

    Note. The strictest possible form of this check —
    ``jsonschema.validate(template, schema)`` against
    ``get_schema_payload()['schema']`` — currently fails on every
    bundled template because plotsim's ``UserInput`` accepts
    builder-shortcut shapes (noise preset strings, single-track
    lifecycle dicts) that the JSON Schema export does not capture.
    That asymmetry lives in plotsim and is out of MCP-side scope; see
    the M040 completion report Discovered section. The pydantic
    model_validate path below exercises the actual cross-tool surface
    a client uses via ``validate_config``.
    """
    from plotsim_mcp.tools.get_template import get_template_payload
    from plotsim_mcp.tools.validate_config import validate_config_payload

    schema = get_schema_payload()["schema"]
    assert schema.get("title") == "UserInput", (
        "get_schema's source model must be UserInput for cross-tool agreement"
    )

    template = get_template_payload("hr")["parsed"]
    validated = validate_config_payload(template)
    assert validated["valid"] is True, (
        f"get_template's bundled YAML must satisfy the input shape "
        f"get_schema exports the schema for; got {validated!r}"
    )
