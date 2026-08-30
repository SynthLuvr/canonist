from __future__ import annotations

from typing import TYPE_CHECKING

from canonist.bin import cli
from canonist.bin import doctor as doctor_mod
from canonist.bin import lint as lint_mod
from canonist.bin import migrate as migrate_mod

if TYPE_CHECKING:
    from collections.abc import Sequence

    import pytest


def test_no_args_is_a_usage_error(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main([]) == 2
    assert "usage:" in capsys.readouterr().err


def test_help_exits_zero(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["--help"]) == 0
    assert "commands:" in capsys.readouterr().out
    assert cli.main(["help"]) == 0


def test_version_exits_zero(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["--version"]) == 0
    assert capsys.readouterr().out.startswith("canonist ")


def test_unknown_command_is_a_usage_error(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["bogus"]) == 2
    assert "unknown command" in capsys.readouterr().err


def test_unknown_option_is_a_usage_error(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["lint", "--wat"]) == 2
    assert "unknown option" in capsys.readouterr().err


def test_option_invalid_for_command(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["doctor", "--fast"]) == 2
    assert "--fast" in capsys.readouterr().err


def test_dispatches_lint_with_flags(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, object] = {}

    def fake_lint(paths: Sequence[str], *, fast: bool, keep: bool) -> int:
        seen["paths"] = list(paths)
        seen["fast"] = fast
        seen["keep"] = keep
        return 0

    monkeypatch.setattr(lint_mod, "run_lint", fake_lint)
    assert cli.main(["lint", "--fast", "--keep-config", "src"]) == 0
    assert seen == {"paths": ["src"], "fast": True, "keep": True}


def test_dispatches_doctor(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(doctor_mod, "run_doctor", lambda: 0)
    assert cli.main(["doctor"]) == 0


def test_dispatches_migrate_dry_run(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, object] = {}

    def fake_migrate(paths: Sequence[str], *, dry_run: bool) -> int:
        seen["paths"] = list(paths)
        seen["dry_run"] = dry_run
        return 0

    monkeypatch.setattr(migrate_mod, "run_migrate", fake_migrate)
    assert cli.main(["migrate", "--dry-run"]) == 0
    assert seen == {"paths": [], "dry_run": True}
