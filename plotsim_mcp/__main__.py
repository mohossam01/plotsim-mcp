"""Entrypoint for ``python -m plotsim_mcp``.

Delegates to :func:`plotsim_mcp.server.main`, which constructs the
FastMCP server and runs it over the stdio transport. Exit codes match
whatever the SDK surfaces — typically ``0`` on a clean client close.
"""
from plotsim_mcp.server import main

if __name__ == "__main__":
    main()
