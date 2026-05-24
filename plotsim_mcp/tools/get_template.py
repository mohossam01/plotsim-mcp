"""``get_template`` — fetch a bundled plotsim template YAML by name.

Returns the raw YAML string plus the parsed dict so clients can either show
the source verbatim or operate on the structure. Read through
``importlib.resources`` rather than ``plotsim.load_template`` because the
latter instantiates ``PlotsimConfig``, which emits a stdout banner that
corrupts the MCP stdio frame (see the [m35/...stdout] finding deferred to
M037's stdout-discipline audit).
"""
from __future__ import annotations

import importlib.resources as _resources
from typing import Any

import plotsim
import yaml
from mcp.server.fastmcp import FastMCP

from plotsim_mcp.errors import CODE_TEMPLATE_UNKNOWN, ToolError

TOOL_NAME = "get_template"
TOOL_DESCRIPTION = (
    "Fetch a bundled plotsim template by name. Returns the raw YAML text "
    "(so clients can display source) plus the parsed dictionary (so clients "
    "can operate on the structure). Use list_templates to discover names."
)

_TEMPLATE_PACKAGE = "plotsim.configs.templates"


def _read_template_text(name: str) -> str | None:
    """Return raw YAML text for ``name`` if a bundled file matches, else ``None``."""
    root = _resources.files(_TEMPLATE_PACKAGE)
    for candidate in (f"{name}.yaml", f"{name}_template.yaml"):
        entry = root / candidate
        if entry.is_file():
            return entry.read_text(encoding="utf-8")
    return None


def get_template_payload(name: str) -> dict[str, Any]:
    """Return ``{name, yaml, parsed}`` for a bundled template; raise ``KeyError`` otherwise."""
    text = _read_template_text(name)
    if text is None:
        raise KeyError(name)
    parsed = yaml.safe_load(text) or {}
    return {"name": name, "yaml": text, "parsed": parsed}


def register(server: FastMCP) -> None:
    @server.tool(name=TOOL_NAME, description=TOOL_DESCRIPTION, structured_output=False)
    def get_template(name: str) -> Any:
        try:
            return get_template_payload(name)
        except KeyError:
            return ToolError(
                code=CODE_TEMPLATE_UNKNOWN,
                message=f"unknown template {name!r}",
                details={"available": plotsim.list_templates()},
            ).to_tool_result()
