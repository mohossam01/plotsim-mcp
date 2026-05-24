"""Tool registry — every MCP tool exposed by plotsim-mcp lives under this package.

Each tool module exposes a ``register(server: FastMCP) -> None`` function
that attaches its tools to the server. :func:`register_all` invokes every
registrar in declaration order so :mod:`plotsim_mcp.server` does not have
to know the individual tool modules.
"""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from plotsim_mcp.tools import list_templates as _list_templates


def register_all(server: FastMCP) -> None:
    _list_templates.register(server)
