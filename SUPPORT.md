# Support

Thanks for using plotsim-mcp. Here's where to go depending on what you
need.

## I have a usage question

Open a [GitHub issue](https://github.com/mohossam01/plotsim-mcp/issues/new?template=feature_request.md)
tagged `question`, or post in the upstream plotsim
[Discussions](https://github.com/mohossam01/plotsim/discussions). Search
existing threads first — your question may already have an answer.

Before posting, please:

- Check the [README](README.md) — install steps, Claude Desktop config,
  and the tool catalogue live there.
- Verify the MCP server starts cleanly:
  `python -m plotsim_mcp` (it exits when the client closes the stream).
- Confirm your `plotsim` install is `>=0.7.0`:
  `python -c "import plotsim; print(plotsim.__version__)"`.

## I found a bug

Open a [bug report](https://github.com/mohossam01/plotsim-mcp/issues/new?template=bug_report.md).
Include:

- plotsim-mcp version (`pip show plotsim-mcp`)
- plotsim version (`pip show plotsim`)
- mcp SDK version (`pip show mcp`)
- Python version and OS
- The tool you called, the arguments you passed, and the envelope you
  got back
- Expected vs. actual behavior

## I have a feature idea

For early-stage ideas, the upstream [plotsim Discussions](https://github.com/mohossam01/plotsim/discussions)
is a good place to talk shape. For concrete, well-scoped requests
specific to the MCP surface, open a
[feature request issue](https://github.com/mohossam01/plotsim-mcp/issues/new?template=feature_request.md).

## I want to contribute

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for dev setup, test commands,
the tool-conventions checklist, and the branch / commit conventions.
All contributions are accepted under the project's Apache-2.0 license;
commits must be signed off per the Developer Certificate of Origin.

## I think I found a security vulnerability

Please do not open a public issue. Report privately via the channels
listed in [`SECURITY.md`](SECURITY.md) — GitHub Security Advisories or
`mail@mohossam.com`.
