# plotsim-mcp

Model Context Protocol server for [plotsim](https://github.com/mohossam01/plotsim) — generate, validate, and inspect synthetic multi-table datasets from any MCP client.

## Status

`0.0.1` — scaffold and a single proof-of-wire tool (`list_templates`). Full tool surface lands in subsequent releases.

## Install

```bash
pip install plotsim-mcp
```

This pulls `plotsim>=0.7.0` and the MCP Python SDK (`mcp>=1.25,<2`) as transitive dependencies.

## Launch

The server speaks the MCP stdio transport:

```bash
python -m plotsim_mcp
```

It exits when the client closes the stream.

## Claude Desktop configuration

Add an entry under the `mcpServers` key of your `claude_desktop_config.json` (location: `%APPDATA%\Claude\` on Windows, `~/Library/Application Support/Claude/` on macOS):

```json
{
  "mcpServers": {
    "plotsim": {
      "command": "python",
      "args": ["-m", "plotsim_mcp"]
    }
  }
}
```

Restart Claude Desktop. The `plotsim` server should appear in the MCP tool inspector.

## Available tools (0.0.1)

| Tool | Returns |
|---|---|
| `list_templates` | Names and descriptions of the bundled plotsim domain templates. |

Subsequent releases add discovery, validation, generation, inspection, and trace tools — see `CHANGELOG.md`.

## Error contract

Every tool returns a `CallToolResult`. On structured failure the result carries `isError=true` and a JSON payload of shape:

```json
{
  "code": "plotsim.template.unknown",
  "message": "human-readable summary",
  "details": {},
  "traceback_id": "optional server-side log key"
}
```

Codes are namespaced under `plotsim.*`. The current set is enumerated in `plotsim_mcp/errors.py`.

## License

Apache-2.0. See `LICENSE`.
