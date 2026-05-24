"""``validate_config`` — structurally validate a plotsim config blob.

Accepts either a YAML string or an already-parsed dict and routes it through
``plotsim.builder.input.UserInput`` — pydantic's ``ValidationError`` already
carries a structured ``errors()`` list (with ``loc``, ``msg``, ``type`` per
entry) so the contract is direct.

Success path returns ``{"valid": true, "warnings": [...]}`` (warnings come
from pydantic ``UserWarning`` emissions captured during construction).
Failure returns a ``plotsim.config.invalid`` ``ToolError`` with the full
error list in ``details.errors``.

Note: this is structural validation only. Semantic concerns the interpreter
might raise (causal coherence beyond the structural cycle check, etc.) ride
along with the actual generation step — they're not in this tool's scope.
"""
from __future__ import annotations

import warnings
from typing import Any

import yaml
from mcp.server.fastmcp import FastMCP
from pydantic import ValidationError

from plotsim_mcp.errors import CODE_CONFIG_INVALID, ToolError

TOOL_NAME = "validate_config"
TOOL_DESCRIPTION = (
    "Validate a plotsim config (YAML text or parsed dict) against the "
    "builder UserInput schema. Returns {valid: true, warnings: [...]} on "
    "success, or a plotsim.config.invalid error with a structured errors "
    "list on failure."
)


def _coerce_to_dict(payload: str | dict[str, Any]) -> dict[str, Any]:
    if isinstance(payload, dict):
        return payload
    if isinstance(payload, str):
        parsed = yaml.safe_load(payload)
        if parsed is None:
            return {}
        if not isinstance(parsed, dict):
            raise TypeError(
                f"YAML must parse to a mapping; got {type(parsed).__name__}"
            )
        return parsed
    raise TypeError(
        f"validate_config expects a YAML string or dict; got {type(payload).__name__}"
    )


def validate_config_payload(payload: str | dict[str, Any]) -> dict[str, Any]:
    """Return ``{"valid": True, "warnings": [...]}`` on success.

    Raises ``ValidationError`` (pydantic) or ``TypeError`` on failure;
    callers translate those into the ``plotsim.config.invalid`` envelope.
    """
    from plotsim.builder.input import UserInput

    data = _coerce_to_dict(payload)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        UserInput(**data)
        warning_messages = [str(w.message) for w in caught]
    return {"valid": True, "warnings": warning_messages}


def _format_pydantic_errors(exc: ValidationError) -> list[dict[str, Any]]:
    formatted: list[dict[str, Any]] = []
    for err in exc.errors():
        loc = err.get("loc", ())
        formatted.append(
            {
                "loc": ".".join(str(part) for part in loc),
                "msg": err.get("msg", ""),
                "type": err.get("type", ""),
            }
        )
    return formatted


def register(server: FastMCP) -> None:
    @server.tool(name=TOOL_NAME, description=TOOL_DESCRIPTION, structured_output=False)
    def validate_config(config: str | dict[str, Any]) -> Any:
        try:
            return validate_config_payload(config)
        except ValidationError as exc:
            return ToolError(
                code=CODE_CONFIG_INVALID,
                message=f"{len(exc.errors())} validation error(s)",
                details={"errors": _format_pydantic_errors(exc)},
            ).to_tool_result()
        except (TypeError, yaml.YAMLError) as exc:
            return ToolError(
                code=CODE_CONFIG_INVALID,
                message=str(exc),
                details={"errors": []},
            ).to_tool_result()
