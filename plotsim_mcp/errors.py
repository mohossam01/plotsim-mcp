"""Structured error contract shared by every plotsim-mcp tool.

Tool failures serialize into ``CallToolResult.content`` with ``isError=True``
and a JSON payload of shape ``{code, message, details, traceback_id?}``.
Protocol-level errors (transport, schema) are surfaced by the SDK through
the JSON-RPC ``error`` field and are out of scope for this module.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from mcp.types import CallToolResult, TextContent


# --- Namespaced error codes ---------------------------------------------------
#
# Codes live in the ``plotsim.*`` namespace so future MCP servers in the same
# client session don't collide. The catalogue grows as new tool families land;
# every new code is added here rather than inlined at the raise site so the
# wire vocabulary stays auditable.

CODE_CONFIG_INVALID = "plotsim.config.invalid"
CODE_BUDGET_EXCEEDED = "plotsim.budget.exceeded"
CODE_TEMPLATE_UNKNOWN = "plotsim.template.unknown"
CODE_RUN_NOT_FOUND = "plotsim.run.not_found"
CODE_VALIDATION_FAILED = "plotsim.validation.failed"
CODE_INTERNAL = "plotsim.internal"


@dataclass
class ToolError:
    """Structured failure envelope returned by tools as ``CallToolResult``.

    The dataclass is the in-process representation; ``to_tool_result()``
    is the wire serializer. Tests round-trip the JSON payload to lock the
    contract independently of the SDK shape.
    """

    code: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)
    traceback_id: str | None = None

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "code": self.code,
            "message": self.message,
            "details": dict(self.details),
        }
        if self.traceback_id is not None:
            payload["traceback_id"] = self.traceback_id
        return payload

    def to_tool_result(self) -> CallToolResult:
        text = json.dumps(self.to_payload(), sort_keys=True)
        return CallToolResult(
            isError=True,
            content=[TextContent(type="text", text=text)],
        )

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "ToolError":
        return cls(
            code=payload["code"],
            message=payload["message"],
            details=dict(payload.get("details") or {}),
            traceback_id=payload.get("traceback_id"),
        )
