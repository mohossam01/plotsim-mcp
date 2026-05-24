---
name: Bug report
about: Report a defect in plotsim-mcp
title: "[BUG] "
labels: bug
assignees: ''
---

## Description

A clear, concise description of the bug.

## Steps to reproduce

1.
2.
3.

The tool you called, the arguments you passed, and the envelope you got
back (or, if the call failed at the transport layer, the error from the
MCP client):

```python
# paste reproducer here — e.g. the call_tool args and the returned
# CallToolResult body
```

## Expected behavior

What you expected the tool to return.

## Actual behavior

What the tool actually returned (envelope, error code, or transport-level
failure).

```
# paste payload or traceback here
```

## Environment

- **plotsim-mcp version:** (e.g. `0.0.3` — `pip show plotsim-mcp`)
- **plotsim version:** (e.g. `0.7.0` — `pip show plotsim`)
- **mcp SDK version:** (e.g. `1.27.1` — `pip show mcp`)
- **Python version:** (e.g. `3.11.7` — `python --version`)
- **OS:** (e.g. macOS 14.4, Windows 11, Ubuntu 22.04)
- **MCP client:** (e.g. Claude Desktop 0.7.5, in-process test, custom)

## Additional context

Anything else relevant — config snippet, run_id, related issues.
