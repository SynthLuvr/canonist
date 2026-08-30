from __future__ import annotations

from typing import TYPE_CHECKING

from pycanon.bin import format as format_cmd
from tests.fixturelib import GOOD_MODULE, UNFIXABLE_MODULE, UNFORMATTED_MODULE, make_project

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


def test_format_fixes_unformatted_code(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project = make_project(tmp_path, module=UNFORMATTED_MODULE)
    monkeypatch.chdir(project)
    assert format_cmd.run_format([], keep=False) == 0
    formatted = (project / "src" / "pkg" / "__init__.py").read_text(encoding="utf-8")
    assert "def add(a: int, b: int) -> int:" in formatted
    assert "a+b" not in formatted


def test_format_is_idempotent_on_clean_code(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = make_project(tmp_path, module=GOOD_MODULE)
    monkeypatch.chdir(project)
    before = (project / "src" / "pkg" / "__init__.py").read_text(encoding="utf-8")
    assert format_cmd.run_format([], keep=False) == 0
    after = (project / "src" / "pkg" / "__init__.py").read_text(encoding="utf-8")
    assert before == after


def test_format_reports_unfixable_lint_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = make_project(tmp_path, extra_module=UNFIXABLE_MODULE)
    monkeypatch.chdir(project)
    assert format_cmd.run_format([], keep=False) != 0
