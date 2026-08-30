from __future__ import annotations

import tomllib
from typing import TYPE_CHECKING

from pycanon.bin import migrate

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

TEMPLATE_PYPROJECT = """\
[project]
name = "consumer"
version = "0.2.0"
requires-python = ">=3.14"
dependencies = ["httpx>=0.28.0"]

[project.optional-dependencies]
dev = [
    "pip-audit>=2.10.1",
    "pytest>=9.1.1",
    "pytest-cov>=7.1.0",
    "pyright>=1.1.411",
    "ruff>=0.16.3",
    "poethepoet>=0.48.0",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src"]

[tool.uv.sources]
httpx = { workspace = true }

[tool.pytest.ini_options]
testpaths = ["src/tests"]
python_files = ["test_*.py"]
addopts = "--cov=src --cov-report=term-missing --cov-fail-under=80"

[tool.coverage.run]
omit = ["src/tests/*"]

[tool.ruff]
target-version = "py314"
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "W", "I", "UP", "B", "C4", "SIM", "TCH", "S"]

[tool.ruff.lint.per-file-ignores]
"src/tests/*" = ["S101"]
"scripts/*" = ["S"]

[tool.ruff.lint.isort]
known-first-party = ["src"]
required-imports = ["from __future__ import annotations"]

[tool.pyright]
pythonVersion = "3.14"
typeCheckingMode = "strict"

[tool.poe.tasks.typecheck]
cmd = "python -m pyright src/ scripts/"

[tool.poe.tasks.lint]
sequence = ["typecheck", "lint-check"]
"""

# The blocks identical to the presets must vanish entirely; only the
# per-file-ignores delta (the repo-specific scripts/* path) survives as an
# override — the preset already covers src/tests/*.
EXPECTED_PYCANON_OVERRIDES = {
    "ruff": {"lint": {"per-file-ignores": {"scripts/*": ["S"]}}},
}


def make_template_project(root: Path) -> Path:
    scripts = root / "scripts"
    scripts.mkdir(parents=True)
    (scripts / "audit_deps.py").write_text("# ported into pycanon\n", encoding="utf-8")
    (scripts / "check_duplicates.py").write_text("# ported into pycanon\n", encoding="utf-8")
    (root / "pyproject.toml").write_text(TEMPLATE_PYPROJECT, encoding="utf-8")
    return root


def test_dependency_name() -> None:
    assert migrate.dependency_name("ruff>=0.16.3") == "ruff"
    assert migrate.dependency_name("pip-audit>=2.10.1") == "pip-audit"
    assert migrate.dependency_name("pytest[colors]>=9.1.1") == "pytest"
    assert migrate.dependency_name("poethepoet") == "poethepoet"
    assert migrate.dependency_name("py-canon @ git+https://example.invalid/x.git") == "py-canon"


def test_swap_dev_dependencies() -> None:
    swapped = migrate.swap_dev_dependencies(["ruff>=0.16.3", "poethepoet>=0.48.0", "pytest>=9.1.1"])
    assert swapped == ["poethepoet>=0.48.0", "py-canon>=0.1.0"]


def test_plan_swaps_dependencies_and_collapses_tasks(tmp_path: Path) -> None:
    project = make_template_project(tmp_path)
    plan = migrate.plan_migration(project)
    document = tomllib.loads(plan.new_pyproject)

    dev = document["project"]["optional-dependencies"]["dev"]
    assert dev == ["poethepoet>=0.48.0", "py-canon>=0.1.0"]

    tasks = document["tool"]["poe"]["tasks"]
    assert tasks["lint"]["cmd"] == "python -m pycanon lint"
    assert tasks["check"]["sequence"] == ["lint", "test"]
    assert "typecheck" not in tasks

    # Non-registry sources survive untouched.
    assert document["tool"]["uv"]["sources"]["httpx"] == {"workspace": True}
    # Runtime deps and build config survive untouched.
    assert document["project"]["dependencies"] == ["httpx>=0.28.0"]
    assert document["build-system"]["build-backend"] == "hatchling.build"


def test_plan_ports_config_deltas_to_overrides(tmp_path: Path) -> None:
    project = make_template_project(tmp_path)
    document = tomllib.loads(migrate.plan_migration(project).new_pyproject)
    tool = document["tool"]

    assert tool["pycanon"] == EXPECTED_PYCANON_OVERRIDES
    # The originals are gone (including the pyright block, identical to preset).
    for section in ("ruff", "pyright", "pytest", "coverage"):
        assert section not in tool


def test_plan_lists_ported_scripts_for_deletion(tmp_path: Path) -> None:
    project = make_template_project(tmp_path)
    plan = migrate.plan_migration(project)
    assert [path.name for path in plan.delete_files] == ["audit_deps.py", "check_duplicates.py"]


def test_dry_run_changes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    project = make_template_project(tmp_path)
    monkeypatch.chdir(project)
    assert migrate.run_migrate([], dry_run=True) == 0
    assert (project / "pyproject.toml").read_text(encoding="utf-8") == TEMPLATE_PYPROJECT
    assert (project / "scripts" / "audit_deps.py").is_file()
    assert "dry run; nothing changed" in capsys.readouterr().err


def test_apply_rewrites_and_deletes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project = make_template_project(tmp_path)
    monkeypatch.chdir(project)
    assert migrate.run_migrate([], dry_run=False) == 0

    document = tomllib.loads((project / "pyproject.toml").read_text(encoding="utf-8"))
    assert document["project"]["optional-dependencies"]["dev"] == [
        "poethepoet>=0.48.0",
        "py-canon>=0.1.0",
    ]
    assert not (project / "scripts" / "audit_deps.py").exists()
    assert not (project / "scripts" / "check_duplicates.py").exists()
    assert ".pycanon/" in (project / ".gitignore").read_text(encoding="utf-8")


def test_missing_pyproject_is_a_usage_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)
    assert migrate.run_migrate([], dry_run=False) == 2
    assert "no pyproject.toml" in capsys.readouterr().err
