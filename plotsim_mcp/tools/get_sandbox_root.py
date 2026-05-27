"""``get_sandbox_root`` — report the directory every run lives under.

Returns the filesystem path the MCP server allocates run directories
inside, along with the environment variable name that controls it
(``PLOTSIM_MCP_RUN_ROOT``). Callers that want to pass an explicit
``output_dir`` to ``create_dataset`` need this surface — without it,
they'd have to either know the env var by name or guess the
platform-default temp path the server falls back to.

The returned path is the same one ``runs.sandbox_root()`` resolves at
call time, including the side-effect that the directory is created on
read.
"""
from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from plotsim_mcp import runs


TOOL_NAME = "get_sandbox_root"
TOOL_DESCRIPTION = (
    "Return the directory every dataset run lives under, plus the "
    "environment variable name that controls it. Returns "
    "{sandbox_root: <path>, env_var: 'PLOTSIM_MCP_RUN_ROOT'}. Useful "
    "when calling create_dataset with an explicit output_dir — the "
    "path must resolve inside the sandbox root."
)


def get_sandbox_root_payload() -> dict[str, Any]:
    """Return ``{sandbox_root, env_var}`` for the current server process."""
    return {
        "sandbox_root": str(runs.sandbox_root()),
        "env_var": runs.ENV_VAR,
    }


def register(server: FastMCP) -> None:
    @server.tool(name=TOOL_NAME, description=TOOL_DESCRIPTION)
    def get_sandbox_root() -> dict[str, Any]:
        return get_sandbox_root_payload()
