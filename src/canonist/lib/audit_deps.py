"""Dependency vulnerability (SCA) audit for production dependencies.

Ported from python-template's ``scripts/audit_deps.py``: export the production
dependency set with ``uv export`` into a temporary requirements file, then
audit it with ``pip-audit --strict``. Implemented in Python (not a Poe
``shell`` task) so it runs identically on Linux, macOS, and Windows.

The vulnerability service is configurable per consumer via
``[tool.canonist.audit] service`` (default ``pypi``). The PyPI-JSON service
cannot audit local-version builds (e.g. ``torch==2.13.0+cu126`` from a CUDA
index — PEP 440 local versions never appear on PyPI); the OSV service
(``service = "osv"``) accepts them.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from canonist.lib import presets, runner

SERVICES = frozenset({"pypi", "osv", "esms"})
"""The vulnerability services pip-audit supports (its ``-s`` choices)."""

DEFAULT_SERVICE = "pypi"


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


def audit_service(project: Path) -> str:
    """The configured vulnerability service: ``[tool.canonist.audit] service``.

    Raises ``ValueError`` for an unknown service so misconfiguration fails
    loudly at pipeline start instead of deep inside pip-audit.
    """
    section = presets.as_table(presets.load_overrides(project).get("audit"))
    service = section.get("service", DEFAULT_SERVICE)
    if not isinstance(service, str) or service not in SERVICES:
        expected = ", ".join(sorted(SERVICES))
        raise ValueError(
            f"invalid [tool.canonist.audit] service: {service!r} (expected one of {expected})"
        )
    return service


def run_audit(project: Path, *, service: str = DEFAULT_SERVICE) -> int:
    """Export and audit the project's production dependencies; return the exit code."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        requirements = Path(tmp_dir) / "requirements.txt"
        code = runner.run_command(build_export_command(requirements), cwd=project)
        if code != 0:
            return code
        # The importable module is pip_audit (underscore); the console script is pip-audit.
        return runner.run_module("pip_audit", ["-r", str(requirements), "--strict", "-s", service])
