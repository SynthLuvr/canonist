"""Resolve CLI path arguments against the repository layout conventions."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path


# The python-template layout: package under src/, optional helper scripts.
DEFAULT_LINT_TARGETS = ("src", "scripts")


def lint_targets(project: Path, paths: Sequence[str]) -> list[str]:
    """Explicit paths win; otherwise the conventional targets that exist."""
    if paths:
        return list(paths)
    return [name for name in DEFAULT_LINT_TARGETS if (project / name).is_dir()]
