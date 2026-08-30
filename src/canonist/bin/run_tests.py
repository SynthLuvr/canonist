"""The test command: pytest wrapped with the canonical coverage gate.

ts-canon delegates ``test`` to vitest directly; canonist wraps pytest because
the coverage-gate configuration is exactly the kind of thing that drifts.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING

from canonist.lib import presets, runner, source_glob

if TYPE_CHECKING:
    from collections.abc import Sequence


def run_tests(paths: Sequence[str], *, keep: bool) -> int:
    """Run pytest over ``paths`` (default the merged config's testpaths)."""
    project = Path.cwd()
    # targets only feed the (unused-here) pyright config; keep the call uniform.
    with presets.generated_configs(
        project, targets=source_glob.lint_targets(project, []), keep=keep
    ) as config:
        args = presets.test_paths(project, paths)
        if not args:
            print(
                "error: no test paths found (expected src/tests/, or pass paths explicitly).",
                file=sys.stderr,
            )
            return 2
        return runner.run_module(
            "pytest",
            [
                "-c",
                str(config.pytest),
                "--rootdir",
                str(project),
                "--cov-config",
                str(config.pytest),
                *args,
            ],
        )
