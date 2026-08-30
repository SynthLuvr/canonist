"""The format pipeline: ``ruff format`` then ``ruff check --fix``.

Unlike ts-canon (which pipes convert-to-arrow → ast-grep → biome), ruff *is*
the canonical Python formatter, so no extra chain is needed.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING

from canonist.lib import presets, runner, source_glob

if TYPE_CHECKING:
    from collections.abc import Sequence


def run_format(paths: Sequence[str], *, keep: bool) -> int:
    """Format and auto-fix ``paths`` (default src/ and scripts/); writes changes."""
    project = Path.cwd()
    targets = source_glob.lint_targets(project, paths)
    if not targets:
        print(
            "error: no format targets found (expected src/ or scripts/, or pass paths explicitly).",
            file=sys.stderr,
        )
        return 2
    with presets.generated_configs(project, targets=targets, keep=keep) as config:
        for args in (
            ["format", "--config", str(config.ruff), *targets],
            ["check", "--fix", "--config", str(config.ruff), *targets],
        ):
            code = runner.run_module("ruff", args)
            if code != 0:
                return code
    return 0
