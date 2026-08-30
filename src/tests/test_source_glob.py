from __future__ import annotations

from typing import TYPE_CHECKING

from pycanon.lib import source_glob
from tests.fixturelib import make_project

if TYPE_CHECKING:
    from pathlib import Path


def test_defaults_pick_existing_directories(tmp_path: Path) -> None:
    project = make_project(tmp_path)
    assert source_glob.lint_targets(project, []) == ["src"]
    (project / "scripts").mkdir()
    assert source_glob.lint_targets(project, []) == ["src", "scripts"]


def test_explicit_paths_win(tmp_path: Path) -> None:
    project = make_project(tmp_path)
    assert source_glob.lint_targets(project, ["custom/dir", "other"]) == ["custom/dir", "other"]


def test_empty_project_yields_no_targets(tmp_path: Path) -> None:
    assert source_glob.lint_targets(tmp_path, []) == []
