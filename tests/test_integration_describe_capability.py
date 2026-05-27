"""Integration coverage for ``describe_capability`` — assert each area
surfaces the plotsim vocabulary by content, not by exact equality (so
adding a new curve / output format doesn't regress this file).
"""
from __future__ import annotations

from plotsim_mcp.tools.describe_capability import describe_capability_payload


def test_curves_contains_known_registry_entries() -> None:
    values = describe_capability_payload("curves")["values"]
    # Sanity sample — these have shipped since plotsim 0.x and ought to
    # outlive any single release.
    for known in ("sigmoid", "exp_decay", "logistic", "step"):
        assert known in values, f"expected {known!r} in curves vocabulary"


def test_distributions_lists_pydantic_distributions() -> None:
    values = describe_capability_payload("distributions")["values"]
    for known in ("lognorm", "gamma", "normal", "beta"):
        assert known in values


def test_output_formats_includes_csv_and_parquet() -> None:
    values = describe_capability_payload("output_formats")["values"]
    assert "csv" in values
    assert "parquet" in values


def test_quality_types_includes_documented_issues() -> None:
    values = describe_capability_payload("quality_types")["values"]
    for known in ("null_injection", "duplicate_rows", "type_mismatch"):
        assert known in values


def test_arrival_shapes_include_known_kinds() -> None:
    values = describe_capability_payload("arrival_shapes")["values"]
    for known in ("uniform", "linear", "step", "explicit"):
        assert known in values


def test_validation_checks_include_pk_and_fk() -> None:
    values = describe_capability_payload("validation_checks")["values"]
    for known in ("pk_uniqueness", "fk_integrity"):
        assert known in values


def test_archetypes_returns_canonical_shape_vocabulary() -> None:
    """``archetypes`` enumerates the canonical atomic shape vocabulary —
    the six words plotsim's archetype DSL accepts at any position — not
    the subset that happens to appear in bundled templates.
    """
    from plotsim.builder.recipes import VALID_SHAPE_WORDS

    values = describe_capability_payload("archetypes")["values"]
    assert values == sorted(VALID_SHAPE_WORDS)
    # Stable, deterministic order across calls.
    assert values == sorted(values)
