"""``describe_run`` — summarize the manifest of a previously created run.

Resolves ``run_id`` through the sandbox convention, opens
``manifest.json``, and returns a compact summary keyed off the most
commonly inspected sections (archetype assignment counts, event firing
counts, treatment cohorts, bridge sizes, correlation phase count). The
raw manifest itself is NOT inlined — it can be megabytes on large runs;
the caller can fetch it directly from ``manifest_path`` when needed.

Archetype-count vocabulary. The manifest records each entity's
post-interpret archetype value, which plotsim's builder interpreter sets
to the entity's source segment name (``plotsim.builder.interpreter``
``Entity.archetype = segment.name``). ``archetype_counts`` translates
those segment names back to the user's authored archetype word via the
``config.userinput.yaml`` sidecar ``create_dataset`` writes alongside the
manifest. Legacy runs without a sidecar fall through unchanged — counts
key by the segment name the manifest recorded.

Runs whose configs disabled the manifest (``config.manifest.include =
False``) still resolve; the summary's ``manifest_path`` is ``None`` and
manifest-derived counts are zero. The ``tables`` field always reflects
the actual on-disk listing.
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

import yaml
from mcp.server.fastmcp import FastMCP

from plotsim_mcp import runs
from plotsim_mcp.errors import CODE_RUN_NOT_FOUND, ToolError


TOOL_NAME = "describe_run"
TOOL_DESCRIPTION = (
    "Summarize the manifest of a previously created run. Returns "
    "{run_id, summary, manifest_path, tables}. Use list_templates / "
    "create_dataset to produce a run_id."
)

_MANIFEST_FILENAME = "manifest.json"
_SIDECAR_FILENAME = "config.userinput.yaml"


def _segment_to_archetype(run_dir: Path) -> dict[str, str]:
    """Map each segment name to its user-authored archetype word.

    Reads the ``config.userinput.yaml`` sidecar. Returns an empty mapping
    on a missing / malformed sidecar; callers treat that as "leave the
    segment-name passthrough alone." The interpreter sets
    ``Entity.archetype = segment.name``, so the keys here recover the
    builder vocabulary the user authored.
    """
    sidecar = run_dir / _SIDECAR_FILENAME
    if not sidecar.is_file():
        return {}
    try:
        data = yaml.safe_load(sidecar.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return {}
    if not isinstance(data, dict):
        return {}
    aliases: dict[str, str] = {}
    for segment in data.get("segments", []) or []:
        if not isinstance(segment, dict):
            continue
        name = segment.get("name")
        archetype = segment.get("archetype")
        if isinstance(name, str) and isinstance(archetype, str):
            aliases[name] = archetype
    return aliases


def _summarize_manifest(
    manifest: dict[str, Any],
    archetype_aliases: dict[str, str],
) -> dict[str, Any]:
    """Reduce a parsed manifest dict to its inspection-friendly numbers.

    Defensive against missing keys — earlier manifest schemas (and
    manifest=False runs) drop fields. Every count falls back to 0 / [].
    ``archetype_aliases`` translates each manifest assignment's
    post-interpret ``archetype`` (a segment name) back to the user's
    authored archetype word; unknown keys pass through unchanged so the
    tool still produces useful output against legacy runs.
    """
    assignments = manifest.get("archetype_assignments", []) or []
    archetype_counts: Counter[str] = Counter()
    for assignment in assignments:
        if not isinstance(assignment, dict):
            continue
        raw = assignment.get("archetype")
        if not isinstance(raw, str):
            continue
        archetype_counts[archetype_aliases.get(raw, raw)] += 1

    # Field names mirror the pydantic classes plotsim writes:
    # ``TrajectorySample.entity``, ``EventFiring.table``,
    # ``BridgeAssociationRecord.bridge`` (``plotsim/manifest.py``).
    trajectory_samples = manifest.get("trajectory_samples", []) or []
    sampled_entities = {
        s.get("entity") for s in trajectory_samples if isinstance(s, dict)
    }
    sampled_entities.discard(None)

    event_firings = manifest.get("event_firings", []) or []
    event_counts: Counter[str] = Counter()
    for firing in event_firings:
        if isinstance(firing, dict):
            event_counts[str(firing.get("table", "unknown"))] += 1

    treatment_cohorts = manifest.get("treatment_cohorts", []) or []
    correlation_phases = manifest.get("correlation_phases", []) or []
    bridges = manifest.get("bridges", []) or []
    bridge_associations = manifest.get("bridge_associations", []) or []
    bridge_counts: Counter[str] = Counter()
    for record in bridge_associations:
        if isinstance(record, dict):
            bridge_counts[str(record.get("bridge", "unknown"))] += 1

    return {
        "schema_version": manifest.get("schema_version"),
        "seed": manifest.get("seed"),
        "config_sha256": manifest.get("config_sha256"),
        "archetype_assignments_total": len(assignments),
        "archetype_counts": dict(archetype_counts),
        "trajectory_sampled_entities": len(sampled_entities),
        "event_firings_total": len(event_firings),
        "event_counts": dict(event_counts),
        "treatment_cohorts": [
            c.get("label") for c in treatment_cohorts if isinstance(c, dict)
        ],
        "correlation_phase_count": len(correlation_phases),
        "bridges": [b.get("name") for b in bridges if isinstance(b, dict)],
        "bridge_association_counts": dict(bridge_counts),
    }


def describe_run_payload(run_id: str) -> dict[str, Any]:
    """Resolve ``run_id`` and return ``{run_id, summary, manifest_path, tables}``.

    Raises :class:`plotsim_mcp.runs.RunNotFound` when the run_id has no
    matching directory; the wrapper translates that into
    ``plotsim.run.not_found``.
    """
    run_dir = runs.resolve(run_id)
    aliases = _segment_to_archetype(run_dir)
    manifest_path = run_dir / _MANIFEST_FILENAME
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        summary = _summarize_manifest(manifest, aliases)
        manifest_str: str | None = str(manifest_path)
    else:
        summary = _summarize_manifest({}, aliases)
        manifest_str = None

    tables = sorted(p.name for p in run_dir.iterdir() if p.is_file())
    return {
        "run_id": run_id,
        "summary": summary,
        "manifest_path": manifest_str,
        "tables": tables,
    }


def register(server: FastMCP) -> None:
    @server.tool(name=TOOL_NAME, description=TOOL_DESCRIPTION, structured_output=False)
    def describe_run(run_id: str) -> Any:
        try:
            return describe_run_payload(run_id)
        except runs.RunNotFound as exc:
            return ToolError(
                code=CODE_RUN_NOT_FOUND,
                message=f"no run with id {exc.args[0]!r}",
                details={"sandbox_root": str(runs.sandbox_root())},
            ).to_tool_result()
