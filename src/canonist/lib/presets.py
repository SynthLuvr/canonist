"""Bundled presets and per-invocation config generation.

canonist ships canonical ruff, pyright, and pytest/coverage presets inside the
wheel. Python has no version-independent ``node_modules``-style path (a literal
``extends`` pointing into site-packages breaks on every minor Python bump),
and ruff rejects more than one ``--config`` file — so at invocation time
canonist writes the *effective* config: preset deep-merged with the consumer's
``[tool.canonist.*]`` overrides in ``pyproject.toml``.

Merge semantics: later keys win, lists replace, tables merge recursively.

The generated files land in ``<project>/.canonist/`` and are removed after the
run unless ``--keep-config`` is passed. The pyright config lives *inside* the
project because pyright resolves ``include`` paths relative to the config
file's directory and rejects absolute paths — ``../src`` stays portable.

Coverage sections use ``[coverage:run]`` (colon) spelling in the generated
ini; coverage.py silently ignores ``[coverage.run]`` there.
"""

from __future__ import annotations

import json
import shutil
import sys
import tomllib
from dataclasses import dataclass
from importlib import resources
from os.path import relpath
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from canonist.lib.toml_write import dumps as toml_dumps

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

CONFIG_DIR_NAME = ".canonist"


@dataclass(frozen=True)
class GeneratedConfigs:
    """Paths of the effective configs written for one invocation."""

    root: Path
    ruff: Path
    pyright: Path
    pyright_preset: Path
    pytest: Path


def as_table(value: Any) -> dict[str, Any]:
    """Validate that a ``tomllib``-sourced value is a table, keeping ``Any`` values.

    Narrowing ``Any`` with ``isinstance`` would leak ``dict[Unknown, Unknown]``
    into every downstream use under pyright strict; this helper erases the
    unknowns at the boundary. tomllib only ever emits str-keyed tables.
    """
    if isinstance(value, dict):
        return cast("dict[str, Any]", value)
    return {}


def load_ruff_preset() -> dict[str, Any]:
    """The canonical ruff configuration (python-template's ``[tool.ruff]``)."""
    return tomllib.loads(_preset_text("ruff.toml"))


def load_pyright_preset() -> dict[str, Any]:
    """The canonical pyright configuration (strict mode, Python 3.14)."""
    return cast("dict[str, Any]", json.loads(_preset_text("pyright.base.json")))


def load_pytest_preset() -> dict[str, Any]:
    """The canonical pytest + coverage gate configuration."""
    return tomllib.loads(_preset_text("pytest.toml"))


def load_overrides(project: Path) -> dict[str, Any]:
    """Read ``[tool.canonist]`` from the consumer's pyproject.toml (``{}`` if absent)."""
    pyproject = project / "pyproject.toml"
    if not pyproject.is_file():
        return {}
    with pyproject.open("rb") as handle:
        document = tomllib.load(handle)
    tool = as_table(document.get("tool"))
    return as_table(tool.get("canonist"))


def deep_merge(base: Mapping[str, Any], override: Mapping[str, Any]) -> dict[str, Any]:
    """Deep-merge tables; scalars and lists in ``override`` replace the base."""
    merged: dict[str, Any] = dict(base)
    for key, value in override.items():
        existing = merged.get(key)
        if isinstance(value, dict) and isinstance(existing, dict):
            merged[key] = deep_merge(
                cast("dict[str, Any]", existing), cast("dict[str, Any]", value)
            )
        else:
            merged[key] = value
    return merged


def merged_pytest_config(project: Path) -> dict[str, Any]:
    """The effective pytest/coverage config: preset plus consumer overrides."""
    overrides = load_overrides(project)
    return deep_merge(
        load_pytest_preset(),
        {
            "pytest": as_table(overrides.get("pytest")),
            "coverage": as_table(overrides.get("coverage")),
        },
    )


def test_paths(project: Path, paths: Sequence[str]) -> list[str]:
    """Explicit paths win; otherwise the merged config's ``testpaths``."""
    if paths:
        return list(paths)
    section = as_table(merged_pytest_config(project).get("pytest"))
    configured = section.get("testpaths", [])
    if not isinstance(configured, list):
        return []
    return [str(item) for item in cast("list[Any]", configured)]


class generated_configs:
    """Context manager yielding the effective configs for one invocation.

    Writes ``<project>/.canonist/`` on construction and removes it on exit
    unless ``keep`` is set. Implemented as a class (not ``@contextmanager``,
    which typeshed marks deprecated) so the bundle is available immediately.
    """

    def __init__(self, project: Path, *, targets: Sequence[str], keep: bool) -> None:
        root = project / CONFIG_DIR_NAME
        if root.exists():
            shutil.rmtree(root)
        root.mkdir(parents=True)
        self._bundle = _build(project, root, targets)
        self._keep = keep
        suffix = " (kept: --keep-config)" if keep else ""
        print(f"canonist: generated configs in {root}{suffix}", file=sys.stderr)

    def __enter__(self) -> GeneratedConfigs:
        return self._bundle

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        if not self._keep:
            shutil.rmtree(self._bundle.root, ignore_errors=True)


def _build(project: Path, root: Path, targets: Sequence[str]) -> GeneratedConfigs:
    overrides = load_overrides(project)

    ruff_path = root / "ruff.toml"
    ruff_path.write_text(
        toml_dumps(deep_merge(load_ruff_preset(), as_table(overrides.get("ruff")))),
        encoding="utf-8",
    )

    preset_copy = root / "pyright.base.json"
    preset_copy.write_text(_preset_text("pyright.base.json"), encoding="utf-8")
    pyright_path = root / "pyrightconfig.json"
    pyright_path.write_text(
        json.dumps(_pyright_config(project, root, targets, overrides), indent=2) + "\n",
        encoding="utf-8",
    )

    pytest_path = root / "pytest.ini"
    pytest_path.write_text(_render_ini(merged_pytest_config(project)), encoding="utf-8")

    return GeneratedConfigs(
        root=root,
        ruff=ruff_path,
        pyright=pyright_path,
        pyright_preset=preset_copy,
        pytest=pytest_path,
    )


def _pyright_config(
    project: Path,
    root: Path,
    targets: Sequence[str],
    overrides: Mapping[str, Any],
) -> dict[str, Any]:
    """The effective pyright config: consumer overrides plus paths relative to ``root``."""
    config: dict[str, Any] = dict(as_table(overrides.get("pyright")))
    config["extends"] = "pyright.base.json"
    include = [_posix_relpath((project / target).resolve(), root) for target in targets]
    config["include"] = include
    # The config lives in .canonist/, but imports resolve from the project root;
    # point the execution environment back at the project and put the src-layout
    # roots on the import path (both `pkg` and `src.pkg` consumer styles).
    config["executionEnvironments"] = [
        {"root": _posix_relpath(project, root), "extraPaths": include}
    ]
    # Pin the interpreter canonist itself is running under: without an activated
    # venv, pyright falls back to the PATH interpreter and cannot resolve the
    # project's imports (bitten for real by the CI self-host job).
    venv = running_venv()
    if venv is not None:
        config["venvPath"] = _posix_relpath(venv.parent, root)
        config["venv"] = venv.name
    return config


def running_venv() -> Path | None:
    """The venv directory of the current interpreter, if any (``pyvenv.cfg`` marker).

    Deliberately does **not** resolve symlinks: a venv's ``bin/python`` is a
    symlink to the base interpreter, and resolving it would point pyright at
    the base environment instead of the venv.
    """
    executable = Path(sys.executable)
    if not executable.is_absolute():
        return None
    candidate = executable.parent.parent
    return candidate if (candidate / "pyvenv.cfg").is_file() else None


def _posix_relpath(path: Path, start: Path) -> str:
    """``relpath(path, start)`` in posix form, absolute fallback across drives.

    ``os.path.relpath`` raises ``ValueError`` on Windows when the paths sit on
    different drives — e.g. a consumer project under the temp dir on ``C:`` while
    the running interpreter's venv lives on ``D:`` (exactly the CI matrix's
    Windows leg). ``include``/``executionEnvironments.root`` are always under the
    project, so only ``venvPath`` can actually cross drives; an absolute
    ``venvPath`` is still valid for pyright (only ``include`` must remain
    config-relative), so fall back to the absolute posix path instead of
    crashing.
    """
    try:
        return Path(relpath(path, start)).as_posix()
    except ValueError:
        return path.as_posix()


def _render_ini(merged: Mapping[str, Any]) -> str:
    lines: list[str] = []
    _emit_ini_section("pytest", as_table(merged.get("pytest")), lines)
    coverage = as_table(merged.get("coverage"))
    _emit_ini_section("coverage:run", as_table(coverage.get("run")), lines)
    _emit_ini_section("coverage:report", as_table(coverage.get("report")), lines)
    return "\n".join(lines) + ("\n" if lines else "")


def _emit_ini_section(name: str, section: Mapping[str, Any], lines: list[str]) -> None:
    if not section:
        return
    lines.append(f"[{name}]")
    for key, value in section.items():
        if isinstance(value, list):
            lines.append(f"{key} =")
            lines.extend(f"    {item}" for item in cast("list[Any]", value))
        else:
            lines.append(f"{key} = {value}")
    lines.append("")


def _preset_text(name: str) -> str:
    source = resources.files("canonist.presets").joinpath(name)
    with resources.as_file(source) as path:
        return path.read_text(encoding="utf-8")
