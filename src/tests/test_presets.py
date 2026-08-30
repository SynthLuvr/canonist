from __future__ import annotations

import json
import shutil
import tomllib
from pathlib import Path

from pycanon.lib import presets
from tests.fixturelib import BASE_PYPROJECT, make_project


def test_bundled_presets_load() -> None:
    ruff = presets.load_ruff_preset()
    assert ruff["target-version"] == "py314"
    assert ruff["line-length"] == 100
    assert ruff["lint"]["per-file-ignores"] == {"src/tests/*": ["S101"]}
    assert presets.load_pyright_preset()["typeCheckingMode"] == "strict"
    pytest_preset = presets.load_pytest_preset()
    assert pytest_preset["pytest"]["testpaths"] == ["src/tests"]
    assert pytest_preset["coverage"]["run"]["omit"] == ["src/tests/*"]


def test_deep_merge_tables_and_list_replacement() -> None:
    base = {"a": 1, "nested": {"x": 1, "y": 2}, "list": [1, 2]}
    override = {"nested": {"y": 3}, "list": [9], "b": 4}
    assert presets.deep_merge(base, override) == {
        "a": 1,
        "nested": {"x": 1, "y": 3},
        "list": [9],
        "b": 4,
    }


def test_load_overrides(tmp_path: Path) -> None:
    project = make_project(
        tmp_path,
        pyproject_extra='[tool.pycanon.ruff.lint.per-file-ignores]\n"scripts/*" = ["S"]\n',
    )
    overrides = presets.load_overrides(project)
    assert overrides["ruff"]["lint"]["per-file-ignores"]["scripts/*"] == ["S"]
    # Absent pyproject / absent [tool.pycanon] both yield no overrides.
    assert presets.load_overrides(tmp_path / "nowhere") == {}
    bare = tmp_path / "bare"
    bare.mkdir()
    (bare / "pyproject.toml").write_text(BASE_PYPROJECT, encoding="utf-8")
    assert presets.load_overrides(bare) == {}


def test_generated_configs_contents(tmp_path: Path) -> None:
    project = make_project(tmp_path)
    with presets.generated_configs(project, targets=["src"], keep=False) as config:
        merged_ruff = tomllib.loads(config.ruff.read_text(encoding="utf-8"))
        assert merged_ruff["line-length"] == 100
        pyright = json.loads(config.pyright.read_text(encoding="utf-8"))
        assert pyright["extends"] == "pyright.base.json"
        assert pyright["include"] == ["../src"]
        assert pyright["executionEnvironments"] == [{"root": "..", "extraPaths": ["../src"]}]
        # The running venv is pinned (unactivated-venv pyright resolution):
        # config-dir-relative venvPath + venv must resolve to the real venv.
        venv = presets.running_venv()
        assert venv is not None, "tests always run inside a venv"
        assert pyright["venv"] == venv.name
        pinned = config.root / Path(str(pyright["venvPath"])) / str(pyright["venv"])
        assert pinned.resolve() == venv.resolve()
        assert config.pyright_preset.is_file()
        ini = config.pytest.read_text(encoding="utf-8")
        assert "[pytest]" in ini
        assert "[coverage:run]" in ini  # colon spelling: coverage ignores [coverage.run] in ini
        assert "src/tests/*" in ini
        assert "cov-fail-under=80" in ini


def test_generated_configs_removed_unless_kept(tmp_path: Path) -> None:
    project = make_project(tmp_path)
    with presets.generated_configs(project, targets=["src"], keep=False):
        assert (project / ".pycanon").is_dir()
    assert not (project / ".pycanon").exists()

    with presets.generated_configs(project, targets=["src"], keep=True):
        pass
    assert (project / ".pycanon" / "ruff.toml").is_file()
    shutil.rmtree(project / ".pycanon")


def test_overrides_flow_into_generated_ruff_config(tmp_path: Path) -> None:
    project = make_project(
        tmp_path,
        pyproject_extra='[tool.pycanon.ruff.lint.isort]\nknown-first-party = ["pycanon"]\n',
    )
    with presets.generated_configs(project, targets=["src"], keep=False) as config:
        merged = tomllib.loads(config.ruff.read_text(encoding="utf-8"))
    # The override replaced the list...
    assert merged["lint"]["isort"]["known-first-party"] == ["pycanon"]
    # ...while preset keys survive.
    assert merged["lint"]["isort"]["required-imports"] == ["from __future__ import annotations"]
    assert merged["lint"]["select"] == ["E", "F", "W", "I", "UP", "B", "C4", "SIM", "TCH", "S"]
    # ...and per-file-ignores keys merge key-by-key (lists replace per key).
    assert merged["lint"]["per-file-ignores"] == {"src/tests/*": ["S101"]}


def test_pytest_overrides_replace_addopts(tmp_path: Path) -> None:
    project = make_project(
        tmp_path,
        pyproject_extra=(
            "[tool.pycanon.pytest]\n"
            'addopts = "--cov=src --cov-report=term-missing --cov-fail-under=101"\n'
        ),
    )
    with presets.generated_configs(project, targets=["src"], keep=False) as config:
        ini = config.pytest.read_text(encoding="utf-8")
    assert "cov-fail-under=101" in ini
    assert "cov-fail-under=80" not in ini


def test_test_paths_default_and_explicit(tmp_path: Path) -> None:
    project = make_project(tmp_path)
    assert presets.test_paths(project, []) == ["src/tests"]
    assert presets.test_paths(project, ["somewhere/else"]) == ["somewhere/else"]
