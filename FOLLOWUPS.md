# Follow-ups

A catch-all for "while we're at it" observations that surface during
development. Items here are explicitly out of scope for the mission
they were discovered under; promote them to a real mission when their
owner is ready to act on them.

## Open

- **Ruff `F401` drift in `tests/test_trace_cell_sample_rate.py:124-125`.**
  Three unused imports (`MetricSource`, `parse_source`,
  `generate_tables_with_state`) inside the test body. CI runs
  `ruff check plotsim_mcp/` only (`.github/workflows/ci.yml`), so the
  test-tree drift is invisible to current CI. Worth bundling into a
  hygiene mission that also (a) extends the CI ruff target to cover
  `tests/`, and (b) adds the `mypy` job to the branch-protection
  required-status-checks list on `main`.

## Closed

- **0.1.0 leak audit, Cluster B — `describe_run` manifest field-name
  mismatches.** Three reader keys (`entity_id` / `event_name` /
  `bridge_name`) replaced with the field names plotsim's manifest
  pydantic classes actually write (`entity` / `table` / `bridge`).
  `load_run.manifest_summary` inherits the fix via the shared
  `describe_run_payload`. Hand-built unit-test fixtures that encoded
  the wrong keys were rewritten so they no longer mask future
  regressions; a real-manifest integration test pins all three
  counters against an end-to-end banking-template run.
