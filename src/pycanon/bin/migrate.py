"""Convert an existing python-template-style repository to consume py-canon.

Rewrites ``pyproject.toml`` (bundled tool dev-dependencies → ``py-canon``,
Poe tasks collapsed to ``python -m pycanon …``, tool config blocks ported to
``[tool.pycanon.*]`` preset overrides), deletes the ported ``scripts/``
helpers, and appends ``.pycanon/`` to ``.gitignore``.

Non-registry sources (``git``, ``file:``, ``path``, ``workspace`` entries)
survive untouched: only the six known tool dependencies are removed by name.
Comments and formatting of ``pyproject.toml`` are **not** preserved (TOML
round-trip) — review the diff. ``--dry-run`` prints the unified diff and the
planned deletions without changing anything. Reverting the migration commit
is the rollback.
"""

from __future__ import annotations

import difflib
import re
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from pycanon.lib import presets
from pycanon.lib.presets import as_table
from pycanon.lib.toml_write import TomlValue
from pycanon.lib.toml_write import dumps as toml_dumps

if TYPE_CHECKING:
    from collections.abc import Sequence

PORTED_SCRIPTS = ("scripts/audit_deps.py", "scripts/check_duplicates.py")
BUNDLED_TOOL_DEPS = frozenset({"ruff", "pyright", "pytest", "pytest-cov", "pip-audit"})
PY_CANON_REQUIREMENT = "py-canon>=0.1.0"
_NAME_SPLIT = re.compile(r"[<>=!~;\[\s]")
_MISSING = object()


@dataclass(frozen=True)
class MigrationPlan:
    old_pyproject: str
    new_pyproject: str
    delete_files: tuple[Path, ...]


def dependency_name(requirement: str) -> str:
    """The bare distribution name of a PEP 508 requirement string."""
    return _NAME_SPLIT.split(requirement.strip(), maxsplit=1)[0].strip().lower()


def swap_dev_dependencies(dependencies: Sequence[str]) -> list[str]:
    """Drop the bundled tools, keep everything else, ensure py-canon is present."""
    kept = [dep for dep in dependencies if dependency_name(dep) not in BUNDLED_TOOL_DEPS]
    if all(dependency_name(dep) != "py-canon" for dep in kept):
        kept.append(PY_CANON_REQUIREMENT)
    return kept


def _dev_dependencies(document: dict[str, Any]) -> list[str] | None:
    """The dev dependency list, wherever the repo declares it (extras or groups)."""
    optional = as_table(as_table(document.get("project")).get("optional-dependencies"))
    groups = as_table(document.get("dependency-groups"))
    for container in (optional, groups):
        dev = container.get("dev")
        if isinstance(dev, list):
            return cast("list[str]", dev)
    return None


def _migrate_dependencies(document: dict[str, Any]) -> None:
    dev = _dev_dependencies(document)
    if dev is not None:
        dev[:] = swap_dev_dependencies(dev)
        return
    project = as_table(document.get("project"))
    optional = as_table(project.get("optional-dependencies"))
    optional["dev"] = [PY_CANON_REQUIREMENT]
    project["optional-dependencies"] = optional
    document["project"] = project


def canonical_poe_tasks() -> dict[str, Any]:
    """The collapsed consumer task block every migrated repo gets."""
    return {
        "lint": {"help": "Full static pipeline via py-canon", "cmd": "python -m pycanon lint"},
        "format": {
            "help": "Auto-format and auto-fix lint issues",
            "cmd": "python -m pycanon format",
        },
        "test": {"help": "Test suite with the coverage gate", "cmd": "python -m pycanon test"},
        "doctor": {"help": "Diagnose the environment", "cmd": "python -m pycanon doctor"},
        "check": {"help": "Everything: lint plus tests", "sequence": ["lint", "test"]},
    }


def delta(consumer: dict[str, Any], preset: dict[str, Any]) -> dict[str, Any]:
    """Leaves of ``consumer`` that differ from (or are absent in) ``preset``."""
    result: dict[str, Any] = {}
    for key, value in consumer.items():
        base = preset.get(key, _MISSING)
        if isinstance(value, dict) and isinstance(base, dict):
            nested = delta(cast("dict[str, Any]", value), cast("dict[str, Any]", base))
            if nested:
                result[key] = nested
        elif base is not _MISSING and base == value:
            continue
        else:
            result[key] = value
    return result


def _migrate_tool_config(tool: dict[str, Any]) -> dict[str, Any]:
    """Move [tool.ruff]/[tool.pyright]/[tool.pytest]/[tool.coverage] to overrides."""
    pytest_preset = presets.load_pytest_preset()
    # ported block -> (sub-table holding its config when only part counts, preset to diff against)
    ported = {
        "ruff": (None, presets.load_ruff_preset()),
        "pyright": (None, presets.load_pyright_preset()),
        "pytest": ("ini_options", as_table(pytest_preset.get("pytest"))),
        "coverage": (None, as_table(pytest_preset.get("coverage"))),
    }
    overrides: dict[str, Any] = {}
    for name, (sub_key, preset) in ported.items():
        section = as_table(tool.pop(name, None))
        if sub_key is not None:
            section = as_table(section.get(sub_key))
        differing = delta(section, preset)
        if differing:
            overrides[name] = differing
    return overrides


def plan_migration(project: Path) -> MigrationPlan:
    """Compute the migration without touching the filesystem."""
    pyproject = project / "pyproject.toml"
    if not pyproject.is_file():
        raise FileNotFoundError(f"no pyproject.toml found in {project}")
    old_text = pyproject.read_text(encoding="utf-8")
    document = tomllib.loads(old_text)
    _migrate_dependencies(document)
    tool = as_table(document.get("tool"))
    tool["poe"] = {"tasks": canonical_poe_tasks()}
    overrides = _migrate_tool_config(tool)
    if overrides:
        tool["pycanon"] = overrides
    document["tool"] = tool
    new_text = toml_dumps(cast("dict[str, TomlValue]", document))
    deletions = tuple(
        path for path in (project / name for name in PORTED_SCRIPTS) if path.is_file()
    )
    return MigrationPlan(old_pyproject=old_text, new_pyproject=new_text, delete_files=deletions)


def run_migrate(paths: Sequence[str], *, dry_run: bool) -> int:
    """Migrate the project at ``paths[0]`` (default: cwd) to consume py-canon."""
    project = Path(paths[0]).resolve() if paths else Path.cwd()
    try:
        plan = plan_migration(project)
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    _print_diff(plan.old_pyproject, plan.new_pyproject)
    for file in plan.delete_files:
        print(f"pycanon: {'would delete' if dry_run else 'deleting'} {file}", file=sys.stderr)
    if dry_run:
        print("pycanon: dry run; nothing changed.", file=sys.stderr)
        return 0

    (project / "pyproject.toml").write_text(plan.new_pyproject, encoding="utf-8")
    for file in plan.delete_files:
        file.unlink()
    _ensure_gitignore(project)
    print(
        "pycanon: migration applied. Next: run `uv sync --all-extras` to refresh uv.lock, "
        "update README/AGENTS to point at py-canon, and review the diff before merging "
        "(reverting this commit is the rollback).",
        file=sys.stderr,
    )
    return 0


def _print_diff(old_text: str, new_text: str) -> None:
    diff = difflib.unified_diff(
        old_text.splitlines(keepends=False),
        new_text.splitlines(keepends=False),
        fromfile="pyproject.toml (current)",
        tofile="pyproject.toml (migrated)",
        lineterm="",
    )
    for line in diff:
        print(line)


def _ensure_gitignore(project: Path) -> None:
    gitignore = project / ".gitignore"
    existing = gitignore.read_text(encoding="utf-8") if gitignore.is_file() else ""
    if ".pycanon/" in existing:
        return
    addition = "# py-canon generated configs (kept only with --keep-config)\n.pycanon/\n"
    gitignore.write_text(
        existing + ("" if existing.endswith("\n") or not existing else "\n") + addition,
        encoding="utf-8",
    )
