from __future__ import annotations

import sys
from typing import TYPE_CHECKING

from pycanon.lib import runner

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


def test_run_command_success() -> None:
    assert runner.run_command([sys.executable, "-c", "pass"]) == 0


def test_run_command_propagates_exit_code() -> None:
    assert runner.run_command([sys.executable, "-c", "import sys; sys.exit(3)"]) == 3


def test_run_command_echoes_the_command(capsys: pytest.CaptureFixture[str]) -> None:
    assert runner.run_command([sys.executable, "-c", "pass"]) == 0
    assert capsys.readouterr().err.startswith("$ ")


def test_missing_executable_reports_error_and_returns_one(
    capsys: pytest.CaptureFixture[str],
) -> None:
    code = runner.run_command(["pycanon-definitely-not-a-real-binary"])
    assert code == 1
    assert "could not run" in capsys.readouterr().err


def test_run_module_invokes_python_dash_m() -> None:
    assert runner.run_module("pycanon", ["--version"]) == 0


def test_run_command_runs_in_cwd(tmp_path: Path) -> None:
    marker = tmp_path / "cwd-proof.txt"
    script = f"import pathlib; pathlib.Path({str(marker)!r}).write_text('ok', encoding='utf-8')"
    assert runner.run_command([sys.executable, "-c", script], cwd=tmp_path) == 0
    assert marker.read_text(encoding="utf-8") == "ok"
