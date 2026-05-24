"""FastMCP stdio server for plotsim.

The module exposes :func:`build_server` (used by tests for in-process
client/server sessions) and :func:`main` (the CLI / ``python -m`` entry
point that runs the server over stdio).
"""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from plotsim_mcp.tools import register_all

SERVER_NAME = "plotsim-mcp"


def build_server() -> FastMCP:
    """Construct a fully wired FastMCP server with every tool registered."""
    server = FastMCP(SERVER_NAME)
    register_all(server)
    return server


def main() -> None:
    """Run the stdio server until the client closes the stream."""
    build_server().run()


if __name__ == "__main__":
    main()
