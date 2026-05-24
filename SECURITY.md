# Security Policy

## Supported Versions

| Version | Supported          |
| :------ | :----------------- |
| 0.0.x   | :white_check_mark: |

plotsim-mcp is in early development. Until 1.0, only the latest release
is supported.

## Reporting a Vulnerability

If you think you have found a security vulnerability — even if you are
not sure — please report it privately:

- **Email:** `mail@mohossam.com`
- **GitHub Security Advisory:**
  [Report here](https://github.com/mohossam01/plotsim-mcp/security/advisories/new)

Please do **not** open public GitHub issues for security concerns.
Reports will be acknowledged within 48 hours, and a remediation timeline
will be provided.

## Threat model

plotsim-mcp is a Model Context Protocol server that runs the plotsim
data-generation library on behalf of an MCP client (Claude Desktop and
similar). Notable security-relevant surfaces:

- **Sandbox root for generated runs.** Every dataset lands under the
  directory pointed at by `$PLOTSIM_MCP_RUN_ROOT` (default:
  `<system_temp>/plotsim-mcp-runs/`). The `create_dataset` tool refuses
  caller-supplied `output_dir` values that resolve outside this root —
  see `plotsim_mcp/runs.py:ensure_within_sandbox`.
- **No network I/O.** plotsim itself is offline. plotsim-mcp does not
  open sockets or contact remote services; the only I/O is local disk
  for generated tables and stdio for the MCP transport.
- **YAML deserialization.** `validate_config`, `preview`, and
  `create_dataset` accept YAML strings from the client. Parsing uses
  `yaml.safe_load`, which is the documented safe subset (no arbitrary
  Python object construction).

If you find a way to escape the sandbox, force a network call, or
trigger arbitrary code execution through a config value, please report
it through the channels above.
