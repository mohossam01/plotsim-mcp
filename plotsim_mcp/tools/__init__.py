"""Tool registry — every MCP tool exposed by plotsim-mcp lives under this package.

Each tool module exposes a ``register(server: FastMCP) -> None`` function
that attaches its tools to the server. :func:`register_all` invokes every
registrar in declaration order so :mod:`plotsim_mcp.server` does not have
to know the individual tool modules.
"""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from plotsim_mcp.tools import describe_capability as _describe_capability
from plotsim_mcp.tools import get_schema as _get_schema
from plotsim_mcp.tools import get_template as _get_template
from plotsim_mcp.tools import list_templates as _list_templates
from plotsim_mcp.tools import validate_config as _validate_config


def register_all(server: FastMCP) -> None:
    _list_templates.register(server)
    _get_schema.register(server)
    _describe_capability.register(server)
    _get_template.register(server)
    _validate_config.register(server)
