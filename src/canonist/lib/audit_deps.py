"""Dependency vulnerability (SCA) audit for production dependencies.

Ported from python-template's ``scripts/audit_deps.py``: export the production
dependency set with ``uv export`` into a temporary requirements file, then
audit it with ``pip-audit --strict``. Implemented in Python (not a Poe
``shell`` task) so it runs identically on Linux, macOS, and Windows.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from canonist.lib import runner


def build_export_command(requirements: Path) -> list[str]:
    """The ``uv export`` invocation that produces the auditable requirements file."""
    return [
        "uv",
        "export",
        "--no-dev",
        "--no-emit-project",
        "--format",
        "requirements-txt",
        "-o",
        str(requirements),
    ]


def run_audit(project: Path) -> int:
    """Export and audit the project's production dependencies; return the exit code."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        requirements = Path(tmp_dir) / "requirements.txt"
        code = runner.run_command(build_export_command(requirements), cwd=project)
        if code != 0:
            return code
        # The importable module is pip_audit (underscore); the console script is pip-audit.
        return runner.run_module("pip_audit", ["-r", str(requirements), "--strict"])
