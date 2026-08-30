"""The lint pipeline: fail-fast, each step's exit code propagates.

Steps: ruff format --check + ruff check; pyright (strict); uv lock --check;
pip-audit (SCA); lucidshark-duplo (duplication gate). ``--fast`` skips the
two slow steps (audit, duplication gate). The audit service
(``[tool.canonist.audit] service``) and the duplication threshold
(``[tool.canonist.duplo] threshold``) are configurable per consumer.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING

from canonist.lib import audit_deps, duplo, presets, runner, source_glob

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

SLOW_STEPS = {"pip-audit", "duplo"}


def lock_check(project: Path) -> int:
    """Check lockfile freshness; a missing lock skips locally but fails in CI."""
    if not (project / "uv.lock").is_file():
        if duplo.in_ci():
            print(
                "error: uv.lock not found; lockfile freshness cannot be checked in CI.",
                file=sys.stderr,
            )
            return 1
        print(
            "warning: no uv.lock; skipping lockfile freshness check (fatal in CI).",
            file=sys.stderr,
        )
        return 0
    return runner.run_command(["uv", "lock", "--check"], cwd=project)


def run_lint(paths: Sequence[str], *, fast: bool, keep: bool) -> int:
    """Run the full static pipeline over ``paths`` (default src/ and scripts/)."""
    project = Path.cwd()
    targets = source_glob.lint_targets(project, paths)
    if not targets:
        print(
            "error: no lint targets found (expected src/ or scripts/, or pass paths explicitly).",
            file=sys.stderr,
        )
        return 2
    with presets.generated_configs(project, targets=targets, keep=keep) as config:
        try:
            service = audit_deps.audit_service(project)
            threshold = duplo.configured_threshold(project)
        except ValueError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        steps: list[tuple[str, Callable[[], int]]] = [
            (
                "ruff format --check",
                lambda: runner.run_module(
                    "ruff", ["format", "--check", "--config", str(config.ruff), *targets]
                ),
            ),
            (
                "ruff check",
                lambda: runner.run_module(
                    "ruff", ["check", "--config", str(config.ruff), *targets]
                ),
            ),
            ("pyright", lambda: runner.run_module("pyright", ["-p", str(config.pyright.parent)])),
            ("uv lock --check", lambda: lock_check(project)),
            ("pip-audit", lambda: audit_deps.run_audit(project, service=service)),
            ("duplo", lambda: duplo.gate(threshold=threshold)),
        ]
        total = len(steps)
        for index, (name, step) in enumerate(steps, start=1):
            if fast and name in SLOW_STEPS:
                print(f"canonist: [{index}/{total}] {name} SKIPPED (--fast)", file=sys.stderr)
                continue
            print(f"canonist: [{index}/{total}] {name}", file=sys.stderr)
            code = step()
            if code != 0:
                print(f"canonist: step '{name}' failed with exit code {code}", file=sys.stderr)
                return code
        return 0
