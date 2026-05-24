"""``list_templates`` — return bundled plotsim domain templates with descriptions.

Names come from :func:`plotsim.list_templates`. Descriptions come from the
``about`` field of each template's YAML, read directly through
``importlib.resources`` so we avoid instantiating ``PlotsimConfig`` (whose
constructor currently emits a stdout summary that would corrupt the MCP
stdio frame). The stdout-discipline audit on the plotsim side is tracked
separately; once it lands this module can switch to ``load_template``.
"""
from __future__ import annotations

import importlib.resources as _resources

import plotsim
import yaml
from mcp.server.fastmcp import FastMCP

_TEMPLATE_PACKAGE = "plotsim.configs.templates"

TOOL_NAME = "list_templates"
TOOL_DESCRIPTION = (
    "List the bundled plotsim domain templates. Each entry carries the "
    "template name (the value passed to plotsim.load_template) and the "
    "one-line domain description declared in the template's YAML."
)


def _template_about(name: str) -> str:
    root = _resources.files(_TEMPLATE_PACKAGE)
    for candidate in (f"{name}.yaml", f"{name}_template.yaml"):
        entry = root / candidate
        if entry.is_file():
            data = yaml.safe_load(entry.read_text(encoding="utf-8")) or {}
            value = data.get("about", "")
            return str(value).strip()
    return ""


def list_templates_payload() -> list[dict[str, str]]:
    """Return ``[{"name", "description"}, ...]`` for each bundled template."""
    return [
        {"name": name, "description": _template_about(name)}
        for name in plotsim.list_templates()
    ]


def register(server: FastMCP) -> None:
    @server.tool(name=TOOL_NAME, description=TOOL_DESCRIPTION)
    def list_templates() -> dict[str, list[dict[str, str]]]:
        # Wrap the list in a dict so FastMCP serializes the whole response
        # as a single TextContent block (it splits bare list returns into
        # one block per element). The wrapper key also leaves room for
        # future metadata (counts, schema_version, …) without breaking
        # downstream clients.
        return {"templates": list_templates_payload()}
