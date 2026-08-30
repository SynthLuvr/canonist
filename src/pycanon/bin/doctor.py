"""Environment diagnostics: report problems early instead of mid-lint."""

from __future__ import annotations

import os
import shutil
import sys
import tomllib
from dataclasses import dataclass
from importlib import util
from pathlib import Path

from pycanon.lib import duplo, presets

REQUIRED_PYTHON = (3, 14)
BUNDLED_TOOLS = ("ruff", "pyright", "pytest", "pip_audit")
# Consumer-side conveniences: reported as advisories, never fatal.
ADVISORY_TOOLS = ("poethepoet",)


@dataclass(frozen=True)
class CheckResult:
    """One diagnostic outcome. ``ok is None`` marks an advisory (never fatal)."""

    name: str
    ok: bool | None
    detail: str


def check_python() -> CheckResult:
    current = sys.version_info[:2]
    required = ".".join(str(part) for part in REQUIRED_PYTHON)
    have = ".".join(str(part) for part in current)
    passed = current >= REQUIRED_PYTHON
    return CheckResult("python", passed, f"{have} (requires >= {required})")


def check_executable(name: str, *, advisory: bool = False) -> CheckResult:
    found = shutil.which(name)
    if found is not None:
        return CheckResult(name, True, f"found at {found}")
    return CheckResult(name, None if advisory else False, "not found on PATH")


def check_module(module: str, *, advisory: bool = False) -> CheckResult:
    spec = util.find_spec(module)
    if spec is not None:
        return CheckResult(module, True, "importable via python -m")
    return CheckResult(module, None if advisory else False, "not installed in this environment")


def check_presets() -> CheckResult:
    try:
        presets.load_ruff_preset()
        presets.load_pyright_preset()
        presets.load_pytest_preset()
    except (OSError, ValueError) as exc:  # TOML/JSON decode errors are ValueError subclasses
        return CheckResult("presets", False, f"bundled preset failed to load: {exc}")
    return CheckResult("presets", True, "ruff.toml, pyright.base.json, pytest.toml load cleanly")


def check_overrides(project: Path) -> CheckResult:
    pyproject = project / "pyproject.toml"
    if not pyproject.is_file():
        return CheckResult("overrides", None, "no pyproject.toml (overrides are optional)")
    try:
        presets.load_overrides(project)
    except tomllib.TOMLDecodeError as exc:
        return CheckResult("overrides", False, f"pyproject.toml is not valid TOML: {exc}")
    return CheckResult("overrides", True, "[tool.pycanon] overrides load cleanly")


def check_duplo() -> CheckResult:
    env_path = os.environ.get("LUCIDSHARK_DUPLO")
    cached = cached_binary().is_file()
    if env_path is not None or shutil.which("lucidshark-duplo") is not None or cached:
        return CheckResult("duplo", True, "binary available (no download needed)")
    return CheckResult(
        "duplo",
        None,
        "not downloaded yet; the first `pycanon lint` fetches it "
        "(if the download or exec is blocked: SKIPPED locally, fatal in CI)",
    )


def cached_binary() -> Path:
    return duplo.cache_dir() / f"v{duplo.DUPLO_VERSION}" / duplo.binary_name()


def run_doctor() -> int:
    """Run all checks; return 1 if any required check failed, else 0."""
    project = Path.cwd()
    results = [
        check_python(),
        check_executable("uv"),
        *(check_module(module) for module in BUNDLED_TOOLS),
        *(check_module(module, advisory=True) for module in ADVISORY_TOOLS),
        check_presets(),
        check_overrides(project),
        check_duplo(),
        check_executable("pandoc", advisory=True),
    ]
    for result in results:
        mark = "ok" if result.ok is True else ("warn" if result.ok is None else "FAIL")
        print(f"[{mark:>4}] {result.name}: {result.detail}")
    failed = [result for result in results if result.ok is False]
    if failed:
        names = ", ".join(result.name for result in failed)
        print(f"doctor: {len(failed)} required check(s) failed: {names}", file=sys.stderr)
        return 1
    return 0
