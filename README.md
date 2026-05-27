# plotsim-mcp

Model Context Protocol server for [plotsim](https://github.com/mohossam01/plotsim) — generate, validate, inspect, and trace synthetic multi-table datasets from any MCP client.

## Status

`0.1.0` is live on PyPI; `main` is on the `0.2.0` track. Thirteen tools wired across discovery, sandbox, authoring, generation, inspection, and trace. The authoring surface and the inspection surface share one vocabulary — `validate_config`, `preview`, and `create_dataset` accept the same input shape `get_schema` exports, and `load_run` returns config in that shape so the modify-and-rerun loop round-trips without coercion.

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

### Smoke test from Claude Desktop

To confirm the server is wired correctly after installing, paste the following prompt into a Claude Desktop chat (with the `plotsim` MCP server enabled):

> List the bundled plotsim templates. Then preview the `saas` template and tell me how many entities, periods, and tables it would generate. Finally, generate a small variant with 50 customers (override `segments.0.count` to 50) using seed 7 and report the validation status.

Expected behavior on success — Claude calls `list_templates`, then `preview` with the `saas` template content, then `create_dataset` with `template_or_config="saas"`, `seed=7`, and `overrides={"segments.0.count": 50}`. The reply names the six bundled templates, reports the preview numbers (around 200 entities × 24 periods), and ends with the run's validation status (`ok=true` on a clean run).

Expected behavior on failure — if any tool call fails, Claude surfaces the structured error envelope (e.g. `plotsim.config.invalid` with the offending field, `plotsim.budget.exceeded` if a typo blows the cell ceiling) rather than silently hallucinating a result. Re-running the same prompt after restarting Claude Desktop should produce the same shape of response since `create_dataset` is deterministic on `(config, seed)`.

## Available tools

### Discovery

| Tool | Returns |
|---|---|
| `list_templates` | Names and descriptions of the bundled plotsim domain templates. |
| `get_schema` | The builder-shape `UserInput` JSON Schema (the same input shape `validate_config`, `preview`, and `create_dataset` accept) plus the plotsim version it was emitted by. |
| `describe_capability` | Vocabulary for a named area (`archetypes`, `curves`, `distributions`, `arrival_shapes`, `output_formats`, `quality_types`, `validation_checks`). `archetypes` returns plotsim's canonical six-word atomic vocabulary. |
| `get_sandbox_root` | Filesystem path every run lives under plus the environment variable that controls it (`PLOTSIM_MCP_RUN_ROOT`). Use when constructing an explicit `create_dataset.output_dir`. |

### Authoring

| Tool | Returns |
|---|---|
| `get_template` | Raw YAML text and parsed dict for a bundled template. |
| `validate_config` | Structural validation of a YAML or dict against the builder `UserInput` schema; structured pydantic errors on failure. |
| `preview` | Estimates what a config would generate (entities × periods, table counts, row estimate, cell-budget headroom, `exceeds_budget` flag) without running the pipeline. `archetypes_in_use` reports the archetype words the caller authored on `segments`. |

### Generation and inspection

| Tool | Returns |
|---|---|
| `create_dataset` | Runs the plotsim pipeline end-to-end against a template name or full config. Returns `{run_id, output_dir, tables_written, validation_summary}`. Persists a builder-shape `config.userinput.yaml` sidecar alongside plotsim's engine-shape `config.yaml` so the modify-and-rerun loop round-trips. |
| `list_runs` | Enumerates every run under the sandbox root, sorted most-recent first. Each entry carries `run_id`, `output_dir`, `modified_at` (ISO 8601 UTC), and `validation_ok` (`true`/`false`/`null` when no report). |
| `describe_run` | Summarizes a previously generated run from its manifest (archetype counts, event firings, treatment cohorts, correlation phases, bridge sizes). `archetype_counts` keys are the user-authored archetype words from the sidecar. |
| `get_validation_report` | Returns the validation report text verbatim plus an `ok` flag parsed from the `Status:` line. |
| `load_run` | Single-call envelope combining raw + parsed config (builder-shape, from the sidecar), manifest summary, validation status, and on-disk table listing. Optimized for the modify-and-rerun loop — `config_yaml` feeds back into `validate_config` and `create_dataset` without coercion. |

### Trace

| Tool | Returns |
|---|---|
| `trace_cell` | Reconstructs the full pipeline trace for one fact-table cell — archetype (the user-authored word from the sidecar), trajectory position, distribution family, noise realization, realized value, and a `trace_source` field (`"manifest"` for sampled entities, `"rederived_from_seed"` otherwise). Bit-identical to the engine's in-memory output regardless of source. |

## Tool input semantics

Compact reference for the inputs that aren't self-evident from the catalogue. Sufficient for an AI client to call each tool correctly without reading source.

- **`create_dataset.template_or_config`** — accepts three shapes: a bundled template name (a bare identifier — no newlines, no colons, no braces); a YAML string of a full builder-shape config; or a parsed dict of the same. The dispatch is heuristic on string contents; pass a dict to bypass the heuristic.
- **`create_dataset.overrides`** — a flat dict whose keys are dotted paths into the parsed config. Integer segments index lists, all other segments index dicts. Example: `{"segments.0.count": 100, "metrics.2.range": [0, 1000]}`. Out-of-range list indices raise rather than silently growing the list.
- **`validate_config.config`** — accepts either a YAML string or a parsed dict. Routed through the builder `UserInput` model. Returns `{valid, warnings}` on success or a `plotsim.config.invalid` envelope whose `details.errors` carry pydantic-style `{loc, msg, type}` records.
- **`preview.config`** — same input shape as `validate_config`. A YAML string parses through `yaml.safe_load`; a dict is used directly.
- **`describe_capability.area`** — one of `archetypes`, `curves`, `distributions`, `arrival_shapes`, `output_formats`, `quality_types`, `validation_checks`. Unknown areas return a `plotsim.capability.unknown` envelope listing the valid set.
- **`trace_cell.row_id`** — a zero-based integer (passed as a string) addressing a flat row in the named fact table. Fact tables are written in entity-major, period-minor order, so `row_id = entity_index * n_periods + period_index`. Only `per_entity_per_period` fact tables are supported in v1; other grains, non-fact tables, and non-metric columns all refuse with `plotsim.trace.column_not_metric`.

## End-to-end usage scenario

A worked session against the bundled `saas` template, showing the full discover → preview → generate → inspect → trace → modify-and-rerun loop. Each step is one MCP tool call; the responses below are abbreviated.

**1. Discover what's available.** `list_templates()` returns the six bundled domains:

```json
{"templates": [
  {"name": "banking",   "description": "Retail banking — accounts, loans, transactions, credit risk"},
  {"name": "health",    "description": "Clinical and patient analytics — encounters, labs, prescriptions, outcomes"},
  {"name": "hr",        "description": "HR talent, performance, compensation and attrition analytics"},
  {"name": "marketing", "description": "Marketing campaign performance — spend, reach, conversion, revenue"},
  {"name": "retail",    "description": "Omnichannel retail — customers, orders, returns, loyalty"},
  {"name": "saas",      "description": "B2B SaaS customer success, engagement and revenue"}
]}
```

**2. Fetch the template for inspection.** `get_template(name="saas")` returns the raw YAML and the parsed dict. The dict is in builder shape — the same vocabulary every authoring tool accepts.

**3. Size the run before paying for it.** `preview(config=<the parsed dict>)` returns entity / period counts, table counts, row estimate, and cell-budget headroom:

```json
{"domain": "Customers", "entities": 200, "periods": 24,
 "tables": {"total": 9, "dim": 4, "fact": 3, "event": 2},
 "archetypes_in_use": ["accelerating", "decline", "growth", "seasonal"],
 "estimated_rows": 14820, "cell_count": 4800,
 "cell_budget": 2000000, "exceeds_budget": false}
```

**4. Generate the dataset.** `create_dataset(template_or_config="saas", seed=42)` runs plotsim end-to-end:

```json
{"run_id": "20260527T172300Z-a1b2c3d4",
 "output_dir": "/tmp/plotsim-mcp-runs/20260527T172300Z-a1b2c3d4",
 "tables_written": ["config.userinput.yaml", "config.yaml", "dim_customer.csv",
                    "fct_engagement.csv", "manifest.json", "validation_report.txt", ...],
 "validation_summary": {"ok": true, "errors": 0, "warnings": 0}}
```

**5. Summarize the run.** `describe_run(run_id=<the run_id>)` returns archetype counts keyed by the user-authored archetype words, event firing counts, treatment cohorts, bridge sizes, correlation phases.

**6. Trace one cell to its source.** `trace_cell(run_id=<run_id>, table="fct_engagement", row_id="120", column="engagement_score")` returns the archetype, trajectory position, distribution family, noise realization, and the realized value the engine computed — bit-identical to the value in the CSV.

**7. Modify and rerun.** Pull the run's full config in builder shape via `load_run(run_id=<run_id>)`. The returned `config_yaml` round-trips: modify a `segments[].count`, feed the modified YAML back to `create_dataset(template_or_config=<modified yaml>, seed=43)`, and a second run lands with the new shape. No conversion between engine and builder representations required.

**8. List what you've built.** `list_runs()` returns every run under the sandbox, sorted most-recent first, each with its validation status. Use `get_sandbox_root()` if you want to allocate runs to an explicit path inside the sandbox via `create_dataset.output_dir`.

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
