"""``create_dataset`` — run the plotsim pipeline end-to-end against a config
and return a handle to the resulting on-disk run.

The tool takes either a bundled template name or a full builder-shape
config (YAML or dict), applies optional dotted-path overrides, injects
the required ``seed`` (and optional ``format``), allocates a sandbox dir
under the run-id convention, and calls ``plotsim.run``. The returned
envelope carries the ``run_id`` (the handle every inspection tool keys
off), the resolved output directory, the list of files written, and a
one-shot validation summary.

Error surface mirrors the cross-mission error contract:

* ``plotsim.budget.exceeded`` — the config's entity × period count
  crosses plotsim's hard ceiling (50M cells).
* ``plotsim.config.invalid`` — pydantic / YAML / type errors building
  the ``UserInput``.
* ``plotsim.run.path_forbidden`` — caller-supplied ``output_dir``
  resolves outside the sandbox root.
* ``plotsim.run.failed`` — the generation pipeline itself raised; the
  envelope carries the exception type + message + a ``traceback_id``
  pointing at the server log.
* ``plotsim.template.unknown`` — string ``template_or_config`` looked
  like a template name but no bundled template matched it.
"""
from __future__ import annotations

import copy
import logging
import traceback
import uuid
import warnings
from pathlib import Path
from typing import Any

import yaml
from mcp.server.fastmcp import FastMCP
from pydantic import ValidationError

from plotsim_mcp import runs
from plotsim_mcp.errors import (
    CODE_BUDGET_EXCEEDED,
    CODE_CONFIG_INVALID,
    CODE_TEMPLATE_UNKNOWN,
    ToolError,
)
from plotsim_mcp.tools.get_template import get_template_payload


_log = logging.getLogger("plotsim_mcp.create_dataset")

CODE_RUN_FAILED = "plotsim.run.failed"
CODE_PATH_FORBIDDEN = "plotsim.run.path_forbidden"

TOOL_NAME = "create_dataset"
TOOL_DESCRIPTION = (
    "Generate a dataset from a template name or full config. Required: "
    "seed (for determinism). Optional: overrides (dotted-path dict like "
    "{'entities.0.size': 100}), output_dir (must be under the sandbox "
    "root), format (csv/parquet/jsonl/sql). Returns {run_id, output_dir, "
    "tables_written, validation_summary}."
)

_VALID_FORMATS = ("csv", "parquet", "jsonl", "sql")


def _looks_like_template_name(value: str) -> bool:
    """Heuristic: bare identifier (no newline / colon / brace) is a name."""
    return ("\n" not in value) and (":" not in value) and ("{" not in value)


def _resolve_template_or_config(payload: str | dict[str, Any]) -> dict[str, Any]:
    """Materialize ``payload`` into a builder-shape dict.

    Three input shapes:
        * dict          — used directly (deep-copied so overrides don't
                          mutate caller state).
        * str + name    — looked up via the M036 ``get_template`` reader.
        * str + YAML    — parsed via ``yaml.safe_load``.

    ``KeyError`` is raised when the string looked like a name but no
    bundled template matched it; the wrapper translates that into the
    ``plotsim.template.unknown`` envelope.
    """
    if isinstance(payload, dict):
        return copy.deepcopy(payload)
    if not isinstance(payload, str):
        raise TypeError(
            f"create_dataset expects a template name, YAML string, or dict; "
            f"got {type(payload).__name__}"
        )
    if _looks_like_template_name(payload):
        try:
            return copy.deepcopy(get_template_payload(payload)["parsed"])
        except KeyError:
            raise
    parsed = yaml.safe_load(payload)
    if not isinstance(parsed, dict):
        raise TypeError(
            f"YAML must parse to a mapping; got {type(parsed).__name__}"
        )
    return parsed


def _apply_overrides(data: dict[str, Any], overrides: dict[str, Any]) -> None:
    """Walk dotted-path keys and set leaves in-place.

    Integer path segments index lists; non-integer segments index dicts.
    Missing dict keys are created; out-of-range list indices raise
    ``IndexError`` so the caller hears about the mismatch rather than
    silently growing the list.
    """
    for path, value in overrides.items():
        parts = path.split(".")
        cursor: Any = data
        for part in parts[:-1]:
            if part.isdigit() and isinstance(cursor, list):
                cursor = cursor[int(part)]
            elif isinstance(cursor, dict):
                cursor = cursor.setdefault(part, {})
            else:
                raise TypeError(
                    f"override path {path!r} cannot traverse {type(cursor).__name__}"
                )
        leaf = parts[-1]
        if leaf.isdigit() and isinstance(cursor, list):
            cursor[int(leaf)] = value
        elif isinstance(cursor, dict):
            cursor[leaf] = value
        else:
            raise TypeError(
                f"override path {path!r} cannot set on {type(cursor).__name__}"
            )


def _is_budget_exceeded(exc: ValidationError) -> bool:
    for err in exc.errors():
        msg = str(err.get("msg", ""))
        if "Config produces" in msg and "cells" in msg:
            return True
    return False


def _format_pydantic_errors(exc: ValidationError) -> list[dict[str, Any]]:
    return [
        {
            "loc": ".".join(str(p) for p in err.get("loc", ())),
            "msg": err.get("msg", ""),
            "type": err.get("type", ""),
        }
        for err in exc.errors()
    ]


def _validation_summary(report_path: Path) -> dict[str, Any]:
    """Parse the validation_report.txt header into ``{ok, errors, warnings}``.

    Header shape (see ``plotsim.output._format_report``):
        Plotsim Validation Report
        ==========================
        Generated: <stamp>
        Errors: <N> | Warnings: <N> | Total: <N>
        Status: VALID|INVALID
    """
    summary: dict[str, Any] = {"ok": False, "errors": 0, "warnings": 0}
    if not report_path.is_file():
        return summary
    for line in report_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("Errors:"):
            parts = [p.strip() for p in line.split("|")]
            for part in parts:
                key, _, val = part.partition(":")
                key_norm = key.strip().lower()
                val_norm = val.strip()
                if key_norm == "errors":
                    summary["errors"] = int(val_norm) if val_norm.isdigit() else 0
                elif key_norm == "warnings":
                    summary["warnings"] = int(val_norm) if val_norm.isdigit() else 0
        elif line.startswith("Status:"):
            summary["ok"] = "VALID" in line.upper() and "INVALID" not in line.upper()
    return summary


def create_dataset_payload(
    template_or_config: str | dict[str, Any],
    seed: int,
    *,
    overrides: dict[str, Any] | None = None,
    output_dir: str | None = None,
    fmt: str | None = None,
) -> dict[str, Any]:
    """Run the pipeline end-to-end; return the structured envelope.

    Raises typed exceptions on failure; the ``register`` wrapper translates
    each into the appropriate ToolError envelope. Splitting payload-shaping
    from wire-error formatting keeps the function callable directly from
    unit tests without going through MCP framing.
    """
    from plotsim import create, run as plotsim_run

    data = _resolve_template_or_config(template_or_config)
    if overrides:
        _apply_overrides(data, overrides)
    data["seed"] = seed
    if fmt is not None:
        if fmt not in _VALID_FORMATS:
            raise ValueError(
                f"format must be one of {_VALID_FORMATS}; got {fmt!r}"
            )
        data.setdefault("output", {})
        data["output"]["format"] = fmt

    # Compute the run_id BEFORE allocating so the sandbox path mirrors the
    # canonical config bytes the engine will eventually persist alongside.
    canonical = yaml.safe_dump(data, sort_keys=True)
    run_id = runs.generate_run_id(canonical, seed)

    if output_dir is not None:
        target = runs.ensure_within_sandbox(output_dir)
        target.mkdir(parents=True, exist_ok=True)
    else:
        target = runs.allocate(run_id)

    data.setdefault("output", {})
    data["output"]["directory"] = str(target)

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        config = create(**data)
        resolved = plotsim_run(config, target, seed=seed)

    tables_written = sorted(
        p.name for p in Path(resolved).iterdir() if p.is_file()
    )
    summary = _validation_summary(Path(resolved) / "validation_report.txt")
    return {
        "run_id": run_id,
        "output_dir": str(resolved),
        "tables_written": tables_written,
        "validation_summary": summary,
    }


def register(server: FastMCP) -> None:
    @server.tool(name=TOOL_NAME, description=TOOL_DESCRIPTION, structured_output=False)
    def create_dataset(
        template_or_config: str | dict[str, Any],
        seed: int,
        overrides: dict[str, Any] | None = None,
        output_dir: str | None = None,
        format: str | None = None,
    ) -> Any:
        try:
            return create_dataset_payload(
                template_or_config,
                seed,
                overrides=overrides,
                output_dir=output_dir,
                fmt=format,
            )
        except KeyError as exc:
            import plotsim

            return ToolError(
                code=CODE_TEMPLATE_UNKNOWN,
                message=f"unknown template {exc.args[0]!r}",
                details={"available": plotsim.list_templates()},
            ).to_tool_result()
        except runs.PathForbidden as exc:
            return ToolError(
                code=CODE_PATH_FORBIDDEN,
                message=str(exc),
                details={"sandbox_root": str(runs.sandbox_root())},
            ).to_tool_result()
        except ValidationError as exc:
            if _is_budget_exceeded(exc):
                return ToolError(
                    code=CODE_BUDGET_EXCEEDED,
                    message="config exceeds plotsim's cell ceiling",
                    details={"errors": _format_pydantic_errors(exc)},
                ).to_tool_result()
            return ToolError(
                code=CODE_CONFIG_INVALID,
                message=f"{len(exc.errors())} validation error(s)",
                details={"errors": _format_pydantic_errors(exc)},
            ).to_tool_result()
        except (TypeError, ValueError, yaml.YAMLError) as exc:
            return ToolError(
                code=CODE_CONFIG_INVALID,
                message=str(exc),
                details={"errors": []},
            ).to_tool_result()
        except Exception as exc:
            traceback_id = uuid.uuid4().hex[:12]
            _log.exception(
                "create_dataset failed (traceback_id=%s)", traceback_id
            )
            return ToolError(
                code=CODE_RUN_FAILED,
                message=str(exc),
                details={
                    "exception_type": type(exc).__name__,
                    "traceback_id": traceback_id,
                    "traceback": traceback.format_exc(),
                },
                traceback_id=traceback_id,
            ).to_tool_result()
