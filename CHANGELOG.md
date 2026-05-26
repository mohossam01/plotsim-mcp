# Changelog

All notable changes to `plotsim-mcp` are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed
- `describe_run` summary now reads the manifest field names plotsim's
  pydantic classes actually emit, so three counters that previously
  collapsed against any real run produce the expected results:
  - `summary.trajectory_sampled_entities` reads `TrajectorySample.entity`
    (was the non-existent `entity_id`; count was always 0).
  - `summary.event_counts` keys come from `EventFiring.table`
    (was `event_name`; every firing bucketed under `"unknown"`).
  - `summary.bridge_association_counts` keys come from
    `BridgeAssociationRecord.bridge` (was `bridge_name`; every
    association bucketed under `"unknown"`).
  `load_run.manifest_summary` inherits the fix because it composes
  `describe_run_payload`. Unit-test fixtures that encoded the wrong
  keys were rewritten alongside the source change; a new integration
  test asserts the three counters against an end-to-end banking-template
  run so the same regression cannot recur silently.

## [0.1.0] — 2026-05-24

First public release. `pip install plotsim-mcp` resolves to PyPI; the
repository is open on GitHub; a Claude Desktop integration snippet ships
with the README.

### Added
- `trace_cell(run_id, table, row_id, column)` — reconstruct the full
  pipeline trace for one fact-table cell. Returns the archetype,
  trajectory position, distribution family, noise realization, realized
  cell value, and a `trace_source` field (`"manifest"` or
  `"rederived_from_seed"`). Re-derivation goes through the same code
  path the engine used so the reported value is bit-identical to what
  plotsim itself produces, even when the manifest only sampled a subset
  of entity trajectories. v1 supports per-entity-per-period fact tables;
  `row_id` is the zero-based integer row index.
- `load_run(run_id)` — single-call envelope combining the raw + parsed
  config, the manifest summary, the validation status, and the on-disk
  table listing. Optimized for the modify-and-rerun loop — saves three
  round-trips that would otherwise hit `get_template` / `describe_run` /
  `get_validation_report` separately.
- `.github/workflows/release.yml` — five-job release pipeline (validate
  → matrix test → build → tag-and-release → publish) with a hard
  tag-absence gate and PyPI Trusted Publishing via OIDC. Manual
  approval at the `pypi` GitHub Environment.
- `CITATION.cff` — citation metadata for academic and published use.
- `RELEASE.md` — release runbook documenting the prep PR + workflow
  dispatch flow, the first-release Trusted Publisher registration, and
  the anti-patterns to avoid (manual tag push, `twine upload` from a
  laptop, undated CHANGELOG sections).

### Verified
- All eleven wired tools pass the stdout-discipline regression
  end-to-end (`tests/test_stdout_discipline.py`).
- `trace_cell` returns lineage that matches `trace_metric_cell` on full
  sample rate runs (manifest path) and re-derives bit-identical values
  on low sample rate runs (rederived path), proven by
  `tests/test_trace_cell_sample_rate.py` against an in-memory engine
  rerun.

## [0.0.3] — 2026-05-24

### Added
- `preview(config)` — estimate what a config would generate without
  running it. Returns domain, entity / period counts, table counts by
  type, the estimated row count, the resolved cell budget, and an
  `exceeds_budget` flag. Accepts a builder-shape YAML string or dict.
- `create_dataset(template_or_config, seed, overrides?, output_dir?, format?)`
  — run the plotsim pipeline end-to-end against a template name or full
  config. Sandboxed under `$PLOTSIM_MCP_RUN_ROOT` (default
  `<system_temp>/plotsim-mcp-runs/`). Returns
  `{run_id, output_dir, tables_written, validation_summary}`. Required
  seed (for determinism). Optional dotted-path overrides
  (`{"segments.0.count": 100}`). Optional caller-supplied `output_dir`
  that must resolve inside the sandbox root, else
  `plotsim.run.path_forbidden`. Configs above plotsim's 50M cell hard
  ceiling refused with `plotsim.budget.exceeded`.
- `describe_run(run_id)` — summarize a previously created run from its
  manifest. Returns archetype assignment counts, event firing counts,
  treatment cohorts, correlation phase count, bridge sizes, plus the
  manifest path and the on-disk table listing. Raw manifest is NOT
  inlined.
- `get_validation_report(run_id)` — return the validation report text
  verbatim plus an `ok` flag parsed from the report's `Status:` line.
- `plotsim_mcp.runs` — run_id lifecycle helpers: deterministic
  `<UTC-timestamp>-<sha8>` ids, sandbox resolution honoring
  `$PLOTSIM_MCP_RUN_ROOT`, collision-safe `allocate(...)`, and
  `ensure_within_sandbox(...)` traversal refusal.
- `CONTRIBUTING.md` (with a "Tool conventions" section codifying the
  dict-wrap, `structured_output=False`, stdout-discipline, and run-id
  sandbox patterns), `CODE_OF_CONDUCT.md`, `SECURITY.md`, `SUPPORT.md`.
- `.github/PULL_REQUEST_TEMPLATE.md` — three-section template
  (*What this PR does* / *Files Modified* / *How to test*).
- `.github/ISSUE_TEMPLATE/bug_report.md` +
  `.github/ISSUE_TEMPLATE/feature_request.md`.

### Verified
- Stdout-discipline regression (`tests/test_stdout_discipline.py`)
  parametrizes over every wired tool and asserts each produces zero
  bytes on `sys.stdout`. The audit confirmed plotsim 0.7.0 library
  paths are clean — the M035 finding about a `Config summary:` banner
  was a misclassification (the emission is `sys.stderr.write(...)`).

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
