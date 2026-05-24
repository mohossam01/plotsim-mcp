"""Run-id lifecycle and sandbox resolution for generated datasets.

A ``run_id`` is the opaque handle a client receives from ``create_dataset``
and passes back to every inspection tool (``describe_run``,
``get_validation_report``, and the M038 ``trace_cell`` / ``load_run``). The
shape is ``<UTC-timestamp>-<sha8>`` where:

* ``<UTC-timestamp>`` is ``YYYYMMDDTHHMMSSZ`` so a directory listing sorts
  chronologically.
* ``<sha8>`` is the first eight characters of the SHA-256 of the canonical
  config text concatenated with the seed. Same (config, seed) within the
  same second yields the same id; collisions inside one second are resolved
  by suffixing ``-1``, ``-2``, ... at allocation time.

All run artifacts land under a single sandbox root so the MCP server has a
well-defined surface to clean up and so the path-traversal refusal in
``ensure_within_sandbox`` has one parent to compare against. The root path
comes from the ``PLOTSIM_MCP_RUN_ROOT`` environment variable, falling back
to ``<system_temp>/plotsim-mcp-runs/`` when unset.
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import os
import tempfile
from pathlib import Path


ENV_VAR = "PLOTSIM_MCP_RUN_ROOT"
_DEFAULT_SUBDIR = "plotsim-mcp-runs"


class RunNotFound(KeyError):
    """Raised by :func:`resolve` when ``run_id`` does not match a stored run.

    Tool wrappers translate this into the ``plotsim.run.not_found`` ToolError
    envelope; the exception itself stays Python-side so unit tests can assert
    against it without parsing wire payloads.
    """


class PathForbidden(ValueError):
    """Raised by :func:`ensure_within_sandbox` when a caller-supplied path
    escapes the sandbox root.

    Translates to ``plotsim.run.path_forbidden`` at the wire boundary. We
    raise rather than coerce because silently rewriting a caller's path
    would mask the misuse instead of surfacing it.
    """


def sandbox_root() -> Path:
    """Return the directory every run lives under, creating it if needed.

    Honors ``$PLOTSIM_MCP_RUN_ROOT`` so tests (and operators) can pin the
    root to a controlled location. Defaults to a subdirectory of the system
    temp dir; ``Path.mkdir(parents=True, exist_ok=True)`` keeps the call
    idempotent across concurrent ``create_dataset`` invocations.
    """
    override = os.environ.get(ENV_VAR)
    if override:
        root = Path(override).expanduser()
    else:
        root = Path(tempfile.gettempdir()) / _DEFAULT_SUBDIR
    root.mkdir(parents=True, exist_ok=True)
    return root


def _utc_timestamp(moment: _dt.datetime | None = None) -> str:
    when = moment if moment is not None else _dt.datetime.now(tz=_dt.timezone.utc)
    if when.tzinfo is None:
        when = when.replace(tzinfo=_dt.timezone.utc)
    return when.astimezone(_dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _config_seed_hash(config_text: str, seed: int) -> str:
    digest = hashlib.sha256()
    digest.update(config_text.encode("utf-8"))
    digest.update(b"\x00")
    digest.update(str(seed).encode("utf-8"))
    return digest.hexdigest()[:8]


def generate_run_id(
    config_text: str,
    seed: int,
    *,
    moment: _dt.datetime | None = None,
) -> str:
    """Return ``<timestamp>-<sha8>`` for ``(config_text, seed)``.

    ``moment`` is exposed for tests; production callers omit it so the wall
    clock is read. ``config_text`` should be the canonical serialization
    the caller actually persists (``yaml.safe_dump(sort_keys=True)`` is the
    convention `create_dataset` uses) so the same logical config always
    produces the same hash regardless of input form.
    """
    return f"{_utc_timestamp(moment)}-{_config_seed_hash(config_text, seed)}"


def allocate(run_id: str) -> Path:
    """Create ``<sandbox_root>/<run_id>/`` and return it.

    Resolves single-second collisions by appending ``-1``, ``-2``, ... to
    the run_id directory name until the first unused slot — the on-disk
    directory wins (we never reuse an existing one). The returned path is
    always a fresh, empty directory.
    """
    root = sandbox_root()
    candidate = root / run_id
    suffix = 0
    while candidate.exists():
        suffix += 1
        candidate = root / f"{run_id}-{suffix}"
    candidate.mkdir(parents=True, exist_ok=False)
    return candidate


def resolve(run_id: str) -> Path:
    """Return the directory for ``run_id``, raising :class:`RunNotFound`."""
    path = sandbox_root() / run_id
    if not path.is_dir():
        raise RunNotFound(run_id)
    return path


def ensure_within_sandbox(caller_path: str | Path) -> Path:
    """Validate ``caller_path`` is inside the sandbox; raise otherwise.

    Resolves both sides to absolute paths first so ``..`` segments,
    symlinks, and relative inputs all collapse to a comparable form. The
    sandbox root is itself an allowed value (``ensure_within_sandbox(root)``
    returns the root) — callers that want a strict subpath should compare
    the return against ``sandbox_root()`` themselves.
    """
    root = sandbox_root().resolve()
    candidate = Path(caller_path).expanduser().resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise PathForbidden(
            f"{caller_path!r} resolves outside the sandbox root {str(root)!r}"
        ) from exc
    return candidate


__all__ = [
    "ENV_VAR",
    "PathForbidden",
    "RunNotFound",
    "allocate",
    "ensure_within_sandbox",
    "generate_run_id",
    "resolve",
    "sandbox_root",
]
