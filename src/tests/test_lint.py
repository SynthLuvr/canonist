from __future__ import annotations

from typing import TYPE_CHECKING

from canonist.bin import lint as lint_cmd
from tests.fixturelib import make_project

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

    import pytest


def test_pipeline_order_and_fail_fast(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    project = make_project(tmp_path)
    (project / "uv.lock").write_text("", encoding="utf-8")
    monkeypatch.chdir(project)
    monkeypatch.delenv("CI", raising=False)

    order: list[str] = []

    def fake_run_module(module: str, args: Sequence[str] = (), *, cwd: Path | None = None) -> int:
        order.append(f"{module} {args[0]}")
        return 1 if module == "pyright" else 0

    def fake_run_command(command: Sequence[str], *, cwd: Path | None = None) -> int:
        order.append(" ".join(command))
        return 0

    def fake_gate() -> int:
        order.append("duplo")
        return 0

    def fake_audit(project_arg: Path) -> int:
        order.append("audit")
        return 0

    monkeypatch.setattr(lint_cmd.runner, "run_module", fake_run_module)
    monkeypatch.setattr(lint_cmd.runner, "run_command", fake_run_command)
    monkeypatch.setattr(lint_cmd.duplo, "gate", fake_gate)
    monkeypatch.setattr(lint_cmd.audit_deps, "run_audit", fake_audit)

    assert lint_cmd.run_lint([], fast=False, keep=False) == 1
    assert order == ["ruff format", "ruff check", "pyright -p"]
    assert "step 'pyright' failed" in capsys.readouterr().err
    # The steps after the failure never ran.
    assert "uv lock --check" not in order
    assert "audit" not in order
    assert "duplo" not in order


def test_fast_skips_audit_and_duplo(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    project = make_project(tmp_path)
    monkeypatch.chdir(project)
    monkeypatch.delenv("CI", raising=False)

    order: list[str] = []

    def fake_run_module(module: str, args: Sequence[str] = (), *, cwd: Path | None = None) -> int:
        order.append(module)
        return 0

    monkeypatch.setattr(lint_cmd.runner, "run_module", fake_run_module)

    def fake_gate() -> int:
        order.append("duplo")
        return 0

    def fake_audit(project_arg: Path) -> int:
        order.append("audit")
        return 0

    monkeypatch.setattr(lint_cmd.duplo, "gate", fake_gate)
    monkeypatch.setattr(lint_cmd.audit_deps, "run_audit", fake_audit)

    assert lint_cmd.run_lint([], fast=True, keep=False) == 0
    assert order == ["ruff", "ruff", "pyright"]
    captured = capsys.readouterr().err
    assert "SKIPPED (--fast)" in captured
    assert "pip-audit" in captured and "duplo" in captured


def test_lock_check_missing_lock_skips_locally(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.delenv("CI", raising=False)
    assert lint_cmd.lock_check(tmp_path) == 0
    assert "skipping lockfile freshness" in capsys.readouterr().err


def test_lock_check_missing_lock_fails_in_ci(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("CI", "true")
    assert lint_cmd.lock_check(tmp_path) == 1
    assert "uv.lock not found" in capsys.readouterr().err


def test_lock_check_runs_uv_when_lock_exists(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / "uv.lock").write_text("", encoding="utf-8")
    seen: list[list[str]] = []

    def fake_run_command(command: Sequence[str], *, cwd: Path | None = None) -> int:
        seen.append(list(command))
        return 42

    monkeypatch.setattr(lint_cmd.runner, "run_command", fake_run_command)
    assert lint_cmd.lock_check(tmp_path) == 42
    assert seen == [["uv", "lock", "--check"]]


def test_no_targets_is_a_usage_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)
    assert lint_cmd.run_lint([], fast=False, keep=False) == 2
    assert "no lint targets" in capsys.readouterr().err
