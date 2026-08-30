"""Command dispatch, usage, and exit codes.

Exit codes follow ts-canon: ``0`` for success/help, ``2`` for usage errors,
otherwise the failing step's code propagates.
"""

from __future__ import annotations

import sys
from importlib import metadata
from typing import TYPE_CHECKING

from canonist import __version__
from canonist.bin import doctor, lint, migrate, run_tests
from canonist.bin import format as format_cmd

if TYPE_CHECKING:
    from collections.abc import Sequence

USAGE = """\
canonist - the SynthLuvr Python toolchain (lint | format | test | doctor | migrate)

usage: python -m canonist <command> [paths...] [options]

commands:
  lint      fail-fast static pipeline: ruff format --check, ruff check,
            pyright (strict), uv lock --check, pip-audit, duplication gate
  format    ruff format, then ruff check --fix (writes changes)
  test      pytest with the canonical coverage gate
  doctor    diagnose the environment, bundled tools, and generated configs
  migrate   convert an existing repo to consume canonist

options:
  --fast          (lint) skip pip-audit and the duplication gate
  --keep-config   keep the generated configs in .canonist/ for inspection
  --dry-run       (migrate) print the planned changes without applying them
  -h, --help      show this help
  -V, --version   show the version

paths default to src/ and scripts/ (whichever exist); test paths default to
the merged preset's testpaths. Exit codes: 0 success/help, 2 usage error,
otherwise the failing step's code propagates.
"""

ALLOWED_FLAGS: dict[str, frozenset[str]] = {
    "lint": frozenset({"--fast", "--keep-config"}),
    "format": frozenset({"--keep-config"}),
    "test": frozenset({"--keep-config"}),
    "doctor": frozenset(),
    "migrate": frozenset({"--dry-run"}),
}
KNOWN_FLAGS: frozenset[str] = frozenset[str]().union(*ALLOWED_FLAGS.values())


def tool_version() -> str:
    """The installed distribution version, falling back to the package constant."""
    try:
        return metadata.version("canonist")
    except metadata.PackageNotFoundError:
        return __version__


def _usage_error(message: str) -> None:
    print(f"error: {message}\n", file=sys.stderr)
    print(USAGE, file=sys.stderr)


def _split_arguments(rest: Sequence[str]) -> tuple[set[str], list[str]] | None:
    """Split arguments into known flags and paths; ``None`` on an unknown option."""
    flags: set[str] = set()
    paths: list[str] = []
    for arg in rest:
        if arg in KNOWN_FLAGS:
            flags.add(arg)
        elif arg.startswith("-") and arg != "-":
            _usage_error(f"unknown option {arg!r}")
            return None
        else:
            paths.append(arg)
    return flags, paths


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        print(USAGE, file=sys.stderr)
        return 2
    command, rest = args[0], args[1:]
    if command in {"-h", "--help", "help"}:
        print(USAGE)
        return 0
    if command in {"-V", "--version"}:
        print(f"canonist {tool_version()}")
        return 0

    split = _split_arguments(rest)
    if split is None:
        return 2
    flags, paths = split
    allowed = ALLOWED_FLAGS.get(command)
    if allowed is None:
        _usage_error(f"unknown command {command!r}")
        return 2
    unexpected = flags - allowed
    if unexpected:
        names = ", ".join(sorted(unexpected))
        print(f"error: {names} not valid for '{command}'\n", file=sys.stderr)
        return 2

    if command == "lint":
        return lint.run_lint(paths, fast="--fast" in flags, keep="--keep-config" in flags)
    if command == "format":
        return format_cmd.run_format(paths, keep="--keep-config" in flags)
    if command == "test":
        return run_tests.run_tests(paths, keep="--keep-config" in flags)
    if command == "doctor":
        return doctor.run_doctor()
    return migrate.run_migrate(paths, dry_run="--dry-run" in flags)
