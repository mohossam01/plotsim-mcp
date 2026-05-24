# Contributing to plotsim-mcp

## Sign your work — Developer Certificate of Origin (DCO)

All contributions to plotsim-mcp are accepted under the project's
Apache-2.0 license. By adding a `Signed-off-by` line to your commits, you
certify the [Developer Certificate of Origin
1.1](https://developercertificate.org/) — in short, that you wrote the
change yourself (or have the right to submit it) and that you are
submitting it under the project license.

Add the sign-off automatically by passing `-s` (or `--signoff`) to commit:

```
git commit -s -m "feat: your message"
```

This appends a trailing line to your commit message:

```
Signed-off-by: Your Name <you@example.com>
```

The name and email must match your `git config user.name` and
`git config user.email`. Pull requests whose commits are missing a valid
`Signed-off-by` trailer cannot be merged.

If you forgot to sign off, amend the most recent commit with
`git commit --amend -s --no-edit`, or rewrite the branch with
`git rebase --signoff main` before pushing.

## Dev setup

```
git clone https://github.com/mohossam01/plotsim-mcp
cd plotsim-mcp
pip install -e .[dev]
pytest
```

`pytest` with no arguments runs the full unit + integration + protocol
suite.

## Running tests

```
pytest                            # full suite
pytest tests/test_unit_*.py       # unit tests only (mocked plotsim)
pytest tests/test_integration_*.py  # integration (real plotsim, no MCP wire)
pytest tests/test_protocol_*.py   # MCP protocol roundtrip (in-process client)
pytest -x                         # stop on first failure
pytest tests/test_runs.py         # a single module
```

Tests come in three named categories per the cross-mission standard. New
tools must ship one file from each:

| Category | Filename pattern | Scope |
|---|---|---|
| unit | `test_unit_<tool>.py` | Mocked plotsim — pure logic of the tool wrapper |
| integration | `test_integration_<tool>.py` | Real plotsim end-to-end, no MCP transport |
| protocol | `test_protocol_<tool>.py` | In-process MCP client → server roundtrip; asserts wire format |

## Tool conventions

Adding a new MCP tool? Mirror the established patterns — they exist
because earlier missions paid for the lessons.

1. **Dict-wrap every collection return.** FastMCP serializes a bare
   `list` return as one `TextContent` block per element, which breaks
   downstream clients that `json.loads` the first block. Always return
   a dict like `{"items": [...]}` or `{"templates": [...]}`. The
   regression test `tests/test_collection_envelope.py` asserts every
   registered tool produces exactly one `TextContent` block; a new tool
   that forgets the wrapper fails the suite without needing manual
   coverage.

2. **Fail-able tools use `(structured_output=False, -> Any)`.** FastMCP
   refuses to register a `-> Union[..., CallToolResult]` annotation, and
   defaults to synthesizing an output schema that rejects the actual
   `CallToolResult` value at call time. The workable pattern is:

   ```python
   @server.tool(name=..., description=..., structured_output=False)
   def my_tool(...) -> Any:
       try:
           return my_payload(...)
       except SomeError as exc:
           return ToolError(code="...", message=str(exc), details=...).to_tool_result()
   ```

   This preserves `isError=True` on the wire and keeps the structured
   payload intact. Tools whose happy path can never fail (e.g.
   `list_templates`, `get_schema`) can omit `structured_output=False`,
   but every tool that catches an exception must use it.

3. **Stdout discipline.** Tools must produce zero bytes on
   `sys.stdout` — the MCP stdio transport interleaves JSON-RPC frames
   there, and a stray write corrupts the session. Library calls into
   plotsim are clean as of plotsim 0.7.0; use `sys.stderr` or `logging`
   for any diagnostic emission from your tool. The regression test
   `tests/test_stdout_discipline.py` parametrizes over every registered
   tool and asserts the captured stdout is empty.

4. **Run-id sandbox for any tool that writes files.** New generation /
   inspection tools key off `run_id` and write under the
   `plotsim_mcp.runs.sandbox_root()` directory. Caller-supplied paths
   route through `runs.ensure_within_sandbox` to refuse traversal. Tools
   never write outside the sandbox root.

5. **Error contract.** Failures serialize through
   `plotsim_mcp.errors.ToolError`. Codes live under the `plotsim.*`
   namespace and are declared as module-level constants in
   `plotsim_mcp/errors.py` rather than inlined at the raise site, so
   the wire vocabulary stays auditable.

## Code style

```
ruff check .
ruff format .
```

Line length is 100. Target Python version is 3.10.

## Branch strategy

`main` is protected. All work happens on branches off `main` and lands
through a pull request — direct pushes and force-pushes to `main` are
blocked by branch protection.

## Branch naming

Use a short prefix matching the commit type, a slash, then a concise
scope.

| Prefix          | Use for                                                  |
|-----------------|----------------------------------------------------------|
| `feat/…`        | New feature work (new tool, new capability)              |
| `fix/…`         | Bug fix                                                  |
| `docs/…`        | Documentation only                                       |
| `chore/…`       | Maintenance, gitignore, dependency bumps                 |
| `ci/…`          | CI / workflow changes                                    |
| `refactor/…`    | Code restructure with no behavior change                 |
| `test/…`        | Test-only change                                         |
| `release/X.Y.Z` | Release prep PR (version bump + CHANGELOG date)          |

## Commit grammar

Conventional Commits. Subject is lowercase, no trailing period, ≤72
chars:

```
<type>(<optional scope>): <imperative summary>
```

| Type       | Use for                                                       |
|------------|---------------------------------------------------------------|
| `feat`     | New user-visible behavior                                     |
| `fix`      | Bug fix                                                       |
| `docs`     | Documentation only                                            |
| `chore`    | Maintenance, gitignore, dependency bumps, no behavior change  |
| `ci`       | CI / workflow changes                                         |
| `refactor` | Code restructure, no behavior change                          |
| `perf`     | Performance improvement                                       |
| `test`     | Test-only change                                              |

Small, focused commits. Body wraps at ~72 chars and explains *why* —
the diff already shows *what*.

## Pull request flow

```
git checkout main
git pull --ff-only origin main
git checkout -b <prefix>/<scope>
# … atomic commits …
git push -u origin <prefix>/<scope>
gh pr create
```

`.github/PULL_REQUEST_TEMPLATE.md` populates a three-section template
(*What this PR does*, *Files Modified*, *How to test*). Fill all three
sections. Flag breaking changes in the *What this PR does* section.

CI runs the 3.10–3.13 matrix on every push to the PR. All four legs
must pass to merge.

## Anti-patterns

- **Direct push to `main`.** Open a PR.
- **Force-push to `main`.** If history must be rewritten, do it from a
  backup branch and route through a PR.
- **Tool that returns a bare list.** Will silently drop client payloads
  on the floor (M035 finding); the envelope regression catches this.
- **Tool that raises on a known failure mode instead of returning
  `ToolError(...).to_tool_result()`.** FastMCP's auto-wrap loses the
  structured payload (M036 spike outcome).
- **Tool that writes to `sys.stdout`.** Corrupts the MCP stdio frame.
  Use `sys.stderr` or `logging`. M037 stdout-discipline test catches
  this.
