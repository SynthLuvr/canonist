from __future__ import annotations

from typing import TYPE_CHECKING

from pycanon.bin import cli
from tests.fixturelib import (
    LINT_ERROR_MODULE,
    UNFORMATTED_MODULE,
    UNTYPED_MODULE,
    make_project,
)

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


def test_lint_fast_on_clean_project(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    project = make_project(tmp_path)
    monkeypatch.chdir(project)
    monkeypatch.delenv("CI", raising=False)
    assert cli.main(["lint", "--fast"]) == 0
    assert "SKIPPED (--fast)" in capsys.readouterr().err


def test_lint_detects_lint_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    project = make_project(tmp_path, extra_module=LINT_ERROR_MODULE)
    monkeypatch.chdir(project)
    monkeypatch.delenv("CI", raising=False)
    assert cli.main(["lint", "--fast"]) != 0
    assert "step 'ruff check' failed" in capsys.readouterr().err


def test_lint_enforces_pyright_strict_from_preset(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    project = make_project(tmp_path, module=UNTYPED_MODULE, test=None)
    monkeypatch.chdir(project)
    monkeypatch.delenv("CI", raising=False)
    assert cli.main(["lint", "--fast"]) != 0
    assert "step 'pyright' failed" in capsys.readouterr().err


def test_format_via_cli(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project = make_project(tmp_path, module=UNFORMATTED_MODULE)
    monkeypatch.chdir(project)
    assert cli.main(["format"]) == 0
    content = (project / "src" / "pkg" / "__init__.py").read_text(encoding="utf-8")
    assert "def add(a: int, b: int) -> int:" in content


def test_test_via_cli_with_coverage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project = make_project(tmp_path)
    monkeypatch.chdir(project)
    assert cli.main(["test"]) == 0


def test_test_via_cli_fails_on_broken_tests(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = make_project(
        tmp_path,
        test="from __future__ import annotations\n\n\ndef test_broken() -> None:\n"
        "    assert 1 == 2\n",
    )
    monkeypatch.chdir(project)
    assert cli.main(["test"]) != 0


def test_doctor_via_cli_on_fixture(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    project = make_project(tmp_path)
    monkeypatch.chdir(project)
    assert cli.main(["doctor"]) == 0
    assert "[  ok]" in capsys.readouterr().out


def test_migrate_dry_run_via_cli(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    project = make_project(tmp_path)
    monkeypatch.chdir(project)
    assert cli.main(["migrate", "--dry-run"]) == 0
    assert (project / "pyproject.toml").read_text(encoding="utf-8").startswith("[project]")
