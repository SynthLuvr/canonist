from __future__ import annotations

from typing import TYPE_CHECKING

from pycanon.bin import run_tests
from tests.fixturelib import make_project

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


def test_test_command_passes_with_coverage_gate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = make_project(tmp_path)
    monkeypatch.chdir(project)
    assert run_tests.run_tests([], keep=False) == 0
    assert not (project / ".pycanon").exists()


def test_coverage_gate_failure_fails_the_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = make_project(
        tmp_path,
        pyproject_extra=(
            "[tool.pycanon.pytest]\n"
            'addopts = "--cov=src --cov-report=term-missing --cov-fail-under=101"\n'
        ),
    )
    monkeypatch.chdir(project)
    assert run_tests.run_tests([], keep=False) != 0


def test_failing_tests_fail_the_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project = make_project(
        tmp_path,
        test="from __future__ import annotations\n\n\ndef test_broken() -> None:\n"
        "    assert 1 == 2\n",
    )
    monkeypatch.chdir(project)
    assert run_tests.run_tests([], keep=False) != 0


def test_keep_config_leaves_generated_ini(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project = make_project(tmp_path)
    monkeypatch.chdir(project)
    assert run_tests.run_tests([], keep=True) == 0
    assert (project / ".pycanon" / "pytest.ini").is_file()
