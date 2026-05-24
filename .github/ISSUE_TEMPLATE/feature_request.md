---
name: Feature request
about: Propose a new capability or enhancement
title: "[FEATURE] "
labels: enhancement
assignees: ''
---

## Description

A clear, concise description of the feature you'd like to see.

## Use case

What problem does this solve from an MCP client's perspective? Concrete
examples (a Claude Desktop workflow, an LLM prompt that fails today) are
stronger than abstract motivation.

## Proposed solution

How you'd see this working — tool name, arguments, return envelope.
A sketch is welcome:

```python
# proposed tool surface
result = await session.call_tool("new_tool_name", {"arg": ...})
# expected envelope
```

## Alternatives considered

Other approaches you weighed and why they fall short. If an existing
tool *almost* does what you need, name it and describe the gap.

## Additional context

Related issues, prior art in other MCP servers, or links to the
underlying problem domain.
