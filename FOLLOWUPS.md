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

- **`runs.py::_utc_timestamp` second-granularity race — structural fix
  deferred.** `test_integration_create_dataset.py::test_same_seed_and_config_same_run_id`
  currently asserts content-hash-suffix equality only
  (`.split("-")[1] ==`), which absorbs the timing flake when two
  consecutive `create_dataset_payload` calls straddle a wall-clock-second
  boundary on slow runners. The underlying race lives in
  `runs.py::_utc_timestamp` — second-granularity timestamps mean
  collision-free `run_id`s require either sub-second precision or a
  refactor of the `<UTC-timestamp>-<sha8>` contract. The
  deterministic-within-second contract is intentional per the runs
  module docstring; revisiting it is a contract change, not a bug fix.

- **Plotsim-side `UserInput` JSON Schema vs builder-shortcut
  asymmetry.** `get_schema()` returns `UserInput.model_json_schema()`,
  which describes the strict typed surface of the builder model.
  `UserInput.model_validate(...)` accepts more — pydantic field
  validators absorb builder shortcuts like `noise: "slightly_messy"`
  (a string preset coerced to `NoiseInput`) and single-track
  `lifecycle: {track, stages}` dicts (coerced to `LifecycleInput`
  with `tracks: [...]`). Net effect: strict `jsonschema.validate`
  against `get_schema()` rejects all six bundled plotsim templates
  even though `validate_config` accepts them. The same engine-vs-builder
  asymmetry class as Cluster C but pointed at builder-vs-schema rather
  than engine-vs-builder. Fix lives in plotsim — either expand
  `UserInput.model_json_schema()` to capture the shortcut shapes via
  `anyOf` branches, or ship two schemas (strict + shortcut-tolerant).
  Discovered during the Cluster C closure work; the integration test
  in `tests/test_integration_get_schema.py::test_schema_validates_a_bundled_template`
  exercises the cross-tool agreement at the pydantic model layer via
  `validate_config` instead, with a docstring documenting the gap.

## Closed

- **0.1.0 leak audit, Cluster A — archetype interpreter rename across
  three tools.** `preview.archetypes_in_use`,
  `describe_run.summary.archetype_counts`, and
  `trace_cell.trace.archetype` previously surfaced
  `config.entities[].archetype` (which plotsim's interpreter sets to
  the source segment name). `create_dataset` now persists a builder-shape
  `config.userinput.yaml` sidecar alongside `config.yaml`; the three
  inspection tools translate the manifest's per-segment instance names
  back to the user-authored archetype words via the sidecar's
  `segments[].name → segments[].archetype` mapping. Legacy runs without
  a sidecar fall through unchanged. `preview` reads archetypes directly
  off the input `segments` list before `create()` runs, since it has
  the input dict in hand.

- **0.1.0 leak audit, Cluster C — engine-vs-builder shape asymmetry on
  `get_schema` and `load_run`.** `get_schema` now returns
  `UserInput.model_json_schema()` (builder shape) instead of
  `PlotsimConfig.model_json_schema()` (engine shape) — the exported
  schema matches the input shape `validate_config`, `preview`, and
  `create_dataset` accept. `load_run.config_yaml` /
  `load_run.config_parsed` read the `config.userinput.yaml` sidecar
  and surface the builder shape, so the modify-and-rerun loop
  round-trips: the returned YAML feeds back into `validate_config` and
  `create_dataset` without coercion. Legacy runs without a sidecar
  fall back to the engine-shape `config.yaml` (won't round-trip
  through the builder tools but stays loadable). See Open above for
  the residual plotsim-side `UserInput`-schema-vs-shortcut asymmetry.

- **0.1.0 leak audit, Cluster D —
  `describe_capability("archetypes")` returned template-derived
  values instead of the canonical vocabulary.** Now sources from
  `plotsim.builder.recipes.VALID_SHAPE_WORDS` (the six atomic shape
  words plotsim's archetype DSL accepts at any position). Six values
  returned in a stable sorted order. Composite DSL specs (e.g.
  `"growth then plateau"`) remain valid input, with only the atomic
  vocabulary enumerated.

- **0.1.0 leak audit, Cluster F — sandbox-root discoverability gap
  for `create_dataset.output_dir`.** New `get_sandbox_root()` tool
  returns `{sandbox_root, env_var: "PLOTSIM_MCP_RUN_ROOT"}`. Callers
  can fetch the sandbox path and construct an explicit `output_dir`
  inside it without prior knowledge of either the env var name or the
  platform-default temp path the server falls back to. Round-trip with
  `create_dataset.output_dir` covered by
  `tests/test_integration_get_sandbox_root.py`.

- **0.1.0 leak audit, Cluster B — `describe_run` manifest field-name
  mismatches.** Three reader keys (`entity_id` / `event_name` /
  `bridge_name`) replaced with the field names plotsim's manifest
  pydantic classes actually write (`entity` / `table` / `bridge`).
  `load_run.manifest_summary` inherits the fix via the shared
  `describe_run_payload`. Hand-built unit-test fixtures that encoded
  the wrong keys were rewritten so they no longer mask future
  regressions; a real-manifest integration test pins all three
  counters against an end-to-end banking-template run.
