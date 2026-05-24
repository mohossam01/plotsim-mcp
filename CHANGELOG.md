# Changelog

All notable changes to `plotsim-mcp` are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
