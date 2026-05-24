# plotsim-mcp

Model Context Protocol server for [plotsim](https://github.com/mohossam01/plotsim) — generate, validate, inspect, and trace synthetic multi-table datasets from any MCP client.

## Status

`0.1.0` — first public release. Eleven tools wired (discovery, templates, authoring, generation, inspection, trace), structured error contract, run-id sandbox, full stdout-discipline coverage.

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

## Available tools

### Discovery

| Tool | Returns |
|---|---|
| `list_templates` | Names and descriptions of the bundled plotsim domain templates. |
| `get_schema` | The full `PlotsimConfig` JSON Schema plus the plotsim version it was emitted by. |
| `describe_capability` | Vocabulary for a named area (`archetypes`, `curves`, `distributions`, `arrival_shapes`, `output_formats`, `quality_types`, `validation_checks`). |

### Authoring

| Tool | Returns |
|---|---|
| `get_template` | Raw YAML text and parsed dict for a bundled template. |
| `validate_config` | Structural validation of a YAML or dict against the builder `UserInput` schema; structured pydantic errors on failure. |
| `preview` | Estimates what a config would generate (entities × periods, table counts, row estimate, cell-budget headroom, `exceeds_budget` flag) without running the pipeline. |

### Generation and inspection

| Tool | Returns |
|---|---|
| `create_dataset` | Runs the plotsim pipeline end-to-end against a template name or full config. Returns `{run_id, output_dir, tables_written, validation_summary}`. |
| `describe_run` | Summarizes a previously generated run from its manifest (archetype counts, event firings, treatment cohorts, correlation phases, bridge sizes). |
| `get_validation_report` | Returns the validation report text verbatim plus an `ok` flag parsed from the `Status:` line. |
| `load_run` | Single-call envelope combining raw + parsed config, manifest summary, validation status, and on-disk table listing. Optimized for the modify-and-rerun loop. |

### Trace

| Tool | Returns |
|---|---|
| `trace_cell` | Reconstructs the full pipeline trace for one fact-table cell — archetype, trajectory position, distribution family, noise realization, realized value, and a `trace_source` field (`"manifest"` for sampled entities, `"rederived_from_seed"` otherwise). Bit-identical to the engine's in-memory output regardless of source. |

## Run sandbox

`create_dataset` writes every dataset under a single sandbox root.
The location is controlled by the `PLOTSIM_MCP_RUN_ROOT` environment
variable; if unset, runs land at
`<system_temp>/plotsim-mcp-runs/<run_id>/`. The `run_id` is a stable
`<UTC-timestamp>-<sha8>` handle that round-trips through `describe_run`,
`get_validation_report`, `load_run`, and `trace_cell`. Caller-supplied
`output_dir` values are refused when they resolve outside the sandbox
root (`plotsim.run.path_forbidden`).

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

Codes are namespaced under `plotsim.*`. The current set is enumerated in `plotsim_mcp/errors.py` and `plotsim_mcp/tools/trace_cell.py`.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for the tool conventions
(dict-wrap, `structured_output=False`, stdout discipline, run-id
sandbox, error contract) and the test layout. The
[Code of Conduct](CODE_OF_CONDUCT.md), [Security policy](SECURITY.md),
and [Support](SUPPORT.md) docs round out the contributor surface.

## License

Apache-2.0. See [LICENSE](LICENSE).
