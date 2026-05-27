"""``describe_capability`` — enumerate the vocabulary plotsim accepts for a
named capability area.

Source-of-truth introspection: read directly from
``plotsim.curves.CURVE_REGISTRY``, the ``Literal`` types in
``plotsim.builder.input``, the validation check constants in
``plotsim.validation``, and the canonical shape-word set in
``plotsim.builder.recipes``. A future ``plotsim.capabilities`` accessor
module is anticipated so MCP doesn't have to follow internal renames.

Areas:
    archetypes         — canonical atomic shape words the archetype DSL
                         accepts at any position (composites like
                         "growth then plateau" are valid input but the
                         atoms are the vocabulary).
    curves             — registered curve types (CURVE_REGISTRY keys).
    distributions      — metric distribution families.
    arrival_shapes     — segment arrival distribution kinds.
    output_formats     — output writer formats.
    quality_types      — quality-issue ``issue`` types.
    validation_checks  — validation check names.
"""
from __future__ import annotations

from typing import Any, get_args

from mcp.server.fastmcp import FastMCP

from plotsim_mcp.errors import ToolError

TOOL_NAME = "describe_capability"
TOOL_DESCRIPTION = (
    "Enumerate the vocabulary plotsim accepts for a named capability area. "
    "Useful for clients building UIs over plotsim — dropdown options, "
    "autocomplete, LLM-side prompt grounding. Returns a dict-wrapped list "
    "of strings keyed by area."
)

VALID_AREAS = (
    "archetypes",
    "curves",
    "distributions",
    "arrival_shapes",
    "output_formats",
    "quality_types",
    "validation_checks",
)

CODE_CAPABILITY_UNKNOWN = "plotsim.capability.unknown"


def _curves() -> list[str]:
    from plotsim.curves import CURVE_REGISTRY

    return sorted(CURVE_REGISTRY.keys())


def _distributions() -> list[str]:
    # ``plotsim._types.Distribution`` is the public Literal alias the engine
    # and the builder both depend on. ``typing.get_args`` is the stable
    # cross-version introspection path for Literal aliases (mypy refuses
    # ``__args__`` on a ``<typing special form>``).
    from plotsim._types import Distribution

    return sorted(str(arg) for arg in get_args(Distribution))


def _arrival_shapes() -> list[str]:
    # The arrival distribution kinds live on four discriminated-union
    # classes in ``plotsim.builder.input``. Importing them indirectly and
    # reading the ``kind`` field's Literal stays robust across new arrival
    # types (the loop adds whichever are exported).
    from plotsim.builder import input as _input

    found: set[str] = set()
    for name in dir(_input):
        cls = getattr(_input, name)
        if not isinstance(cls, type):
            continue
        if not name.endswith("Arrival"):
            continue
        kind_field = getattr(cls, "model_fields", {}).get("kind")
        if kind_field is None:
            continue
        annotation = kind_field.annotation
        for arg in get_args(annotation):
            if isinstance(arg, str):
                found.add(arg)
    return sorted(found)


def _output_formats() -> list[str]:
    from plotsim.builder.input import OutputInput

    fmt_field = OutputInput.model_fields.get("format")
    if fmt_field is None:
        return []
    return sorted(str(arg) for arg in get_args(fmt_field.annotation) if isinstance(arg, str))


def _quality_types() -> list[str]:
    from plotsim.builder.input import QualityIssueInput

    issue_field = QualityIssueInput.model_fields.get("issue")
    if issue_field is None:
        return []
    return sorted(str(arg) for arg in get_args(issue_field.annotation) if isinstance(arg, str))


def _validation_checks() -> list[str]:
    from plotsim import validation as _validation

    return sorted(
        value
        for name, value in vars(_validation).items()
        if name.startswith("CHECK_") and isinstance(value, str)
    )


def _archetypes() -> list[str]:
    # Canonical atomic shape vocabulary, not the subset of words that
    # happens to appear in bundled templates. Users compose these via the
    # archetype DSL (e.g., ``"growth then plateau"``); only the atoms are
    # enumerated here — composites are open-ended.
    from plotsim.builder.recipes import VALID_SHAPE_WORDS

    return sorted(VALID_SHAPE_WORDS)


_AREA_DISPATCH = {
    "archetypes": _archetypes,
    "curves": _curves,
    "distributions": _distributions,
    "arrival_shapes": _arrival_shapes,
    "output_formats": _output_formats,
    "quality_types": _quality_types,
    "validation_checks": _validation_checks,
}


def describe_capability_payload(area: str) -> dict[str, Any]:
    """Return ``{area, values}`` for a known area; raise ``KeyError`` otherwise."""
    fn = _AREA_DISPATCH.get(area)
    if fn is None:
        raise KeyError(area)
    return {"area": area, "values": fn()}


def register(server: FastMCP) -> None:
    @server.tool(name=TOOL_NAME, description=TOOL_DESCRIPTION, structured_output=False)
    def describe_capability(area: str) -> Any:
        try:
            return describe_capability_payload(area)
        except KeyError:
            return ToolError(
                code=CODE_CAPABILITY_UNKNOWN,
                message=f"unknown capability area {area!r}",
                details={"valid_areas": list(VALID_AREAS)},
            ).to_tool_result()
