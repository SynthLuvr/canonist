"""Subprocess helpers.

Nothing runs through a shell, and bundled tools run as
``[sys.executable, "-m", tool]`` so no generated console-script launchers are
needed — the Python twin of ts-canon's runner rationale ("no shells, no
``.CMD`` shims"). This keeps the toolchain usable on managed Windows endpoints
that block low-prevalence executables.
"""

from __future__ import annotations

import subprocess
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path


def run_module(module: str, args: Sequence[str] = (), *, cwd: Path | None = None) -> int:
    """Run ``python -m <module> <args...>``; return the exit code."""
    return run_command([sys.executable, "-m", module, *args], cwd=cwd)


def run_command(command: Sequence[str], *, cwd: Path | None = None) -> int:
    """Echo and run ``command`` without a shell; return the exit code.

    A missing or unrunnable executable is an environment problem: report it
    and return 1 rather than raising, so pipelines fail with a clear message.
    """
    print(f"$ {' '.join(command)}", file=sys.stderr)
    try:
        result = subprocess.run(command, cwd=None if cwd is None else str(cwd), check=False)
    except OSError as exc:
        print(f"error: could not run {command[0]!r}: {exc}", file=sys.stderr)
        return 1
    return result.returncode
