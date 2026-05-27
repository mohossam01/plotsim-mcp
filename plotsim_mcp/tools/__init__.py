"""Tool registry — every MCP tool exposed by plotsim-mcp lives under this package.

Each tool module exposes a ``register(server: FastMCP) -> None`` function
that attaches its tools to the server. :func:`register_all` invokes every
registrar in declaration order so :mod:`plotsim_mcp.server` does not have
to know the individual tool modules.
"""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from plotsim_mcp.tools import create_dataset as _create_dataset
from plotsim_mcp.tools import describe_capability as _describe_capability
from plotsim_mcp.tools import describe_run as _describe_run
from plotsim_mcp.tools import get_sandbox_root as _get_sandbox_root
from plotsim_mcp.tools import get_schema as _get_schema
from plotsim_mcp.tools import get_template as _get_template
from plotsim_mcp.tools import get_validation_report as _get_validation_report
from plotsim_mcp.tools import list_runs as _list_runs
from plotsim_mcp.tools import list_templates as _list_templates
from plotsim_mcp.tools import load_run as _load_run
from plotsim_mcp.tools import preview as _preview
from plotsim_mcp.tools import trace_cell as _trace_cell
from plotsim_mcp.tools import validate_config as _validate_config


def register_all(server: FastMCP) -> None:
    _list_templates.register(server)
    _get_schema.register(server)
    _describe_capability.register(server)
    _get_template.register(server)
    _validate_config.register(server)
    _preview.register(server)
    _create_dataset.register(server)
    _describe_run.register(server)
    _get_validation_report.register(server)
    _trace_cell.register(server)
    _load_run.register(server)
    _list_runs.register(server)
    _get_sandbox_root.register(server)
