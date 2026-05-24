# Changelog

All notable changes to `plotsim-mcp` are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.0.2] — 2026-05-24

### Added
- `get_schema` — returns the full plotsim `PlotsimConfig` JSON Schema plus
  the plotsim version it was emitted by.
- `describe_capability(area)` — enumerates the vocabulary plotsim accepts
  for a named area (`archetypes`, `curves`, `distributions`,
  `arrival_shapes`, `output_formats`, `quality_types`,
  `validation_checks`). Unknown areas return a structured
  `plotsim.capability.unknown` error.
- `get_template(name)` — fetches a bundled template's raw YAML and parsed
  dict. Unknown names return a `plotsim.template.unknown` error carrying
  the available names in `details`.
- `validate_config(config)` — structurally validates a YAML string or
  dict against the builder `UserInput` schema. Success returns
  `{valid: true, warnings: [...]}`; failure returns
  `plotsim.config.invalid` with a structured `details.errors` list (each
  entry carrying `loc`, `msg`, `type`).
- `list_templates` promoted from stub to a covered tool — no shape change.
- `.gitattributes` declaring `* text=auto eol=lf` (mirrors plotsim);
  removes the CRLF warnings observed on the scaffold commit.
- `.github/dependabot.yml` — weekly pip + github-actions update PRs so
  `mcp` SDK minor bumps surface automatically during the v1→v2 horizon.

### Verified
- FastMCP error-passthrough behavior: when a `@server.tool` returns a
  `CallToolResult(isError=True, ...)` directly, FastMCP forwards it
  intact. Tools that raise instead lose their structured payload to
  FastMCP's auto-wrap. Locked by
  `tests/test_fastmcp_error_passthrough.py`.

## [0.0.1] — 2026-05-24

### Added
- Initial scaffold of the MCP stdio server (`plotsim_mcp.server`).
- Structured error contract (`plotsim_mcp.errors`) with a `ToolError`
  dataclass, `to_tool_result()` serializer, and the namespaced code
  catalogue (`plotsim.config.invalid`, `plotsim.budget.exceeded`,
  `plotsim.template.unknown`, `plotsim.run.not_found`, …).
- First tool: `list_templates` — returns the bundled plotsim domain
  template names and descriptions.
- Test suite spanning unit (mocked plotsim), integration (real plotsim),
  protocol (MCP stdio roundtrip), and error-contract serializer coverage.
- GitHub Actions CI running pytest + mypy on Python 3.10–3.13.
