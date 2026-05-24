"""Error contract serializer round-trip.

Locks the wire shape of ``ToolError.to_tool_result()`` so future tools
serialize identically across SDK minor versions.
"""
from __future__ import annotations

import json

from mcp.types import TextContent

from plotsim_mcp.errors import (
    CODE_BUDGET_EXCEEDED,
    CODE_CONFIG_INVALID,
    CODE_TEMPLATE_UNKNOWN,
    ToolError,
)


def test_to_tool_result_marks_is_error() -> None:
    err = ToolError(code=CODE_TEMPLATE_UNKNOWN, message="no such template")
    result = err.to_tool_result()

    assert result.isError is True
    assert len(result.content) == 1
    assert isinstance(result.content[0], TextContent)


def test_payload_round_trip_preserves_all_fields() -> None:
    err = ToolError(
        code=CODE_BUDGET_EXCEEDED,
        message="cell budget exceeded",
        details={"requested": 1_000_000, "limit": 500_000},
        traceback_id="tb-2026-05-24-001",
    )
    result = err.to_tool_result()

    text = result.content[0].text
    parsed = json.loads(text)
    assert parsed == {
        "code": CODE_BUDGET_EXCEEDED,
        "message": "cell budget exceeded",
        "details": {"requested": 1_000_000, "limit": 500_000},
        "traceback_id": "tb-2026-05-24-001",
    }

    reconstituted = ToolError.from_payload(parsed)
    assert reconstituted == err


def test_traceback_id_omitted_when_none() -> None:
    err = ToolError(code=CODE_CONFIG_INVALID, message="bad config")
    result = err.to_tool_result()

    parsed = json.loads(result.content[0].text)
    assert "traceback_id" not in parsed
    assert parsed["code"] == CODE_CONFIG_INVALID
    assert parsed["details"] == {}


def test_details_default_is_independent_per_instance() -> None:
    a = ToolError(code=CODE_CONFIG_INVALID, message="a")
    b = ToolError(code=CODE_CONFIG_INVALID, message="b")
    a.details["x"] = 1
    assert b.details == {}
