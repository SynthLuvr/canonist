from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from canonist.lib import audit_deps
from tests.fixturelib import make_project

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path


def test_build_export_command_shape(tmp_path: Path) -> None:
    requirements = tmp_path / "requirements.txt"
    command = audit_deps.build_export_command(requirements)
    assert command[:7] == [
        "uv",
        "export",
        "--no-dev",
        "--no-emit-project",
        "--format",
        "requirements-txt",
        "-o",
    ]
    assert command[7] == str(requirements)


def test_run_audit_exports_then_audits(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, Sequence[str], Path | None]] = []

    def fake_run_command(command: Sequence[str], *, cwd: Path | None = None) -> int:
        calls.append(("command", tuple(command), cwd))
        return 0

    def fake_run_module(module: str, args: Sequence[str] = (), *, cwd: Path | None = None) -> int:
        calls.append(("module", (module, *args), cwd))
        return 0

    monkeypatch.setattr(audit_deps.runner, "run_command", fake_run_command)
    monkeypatch.setattr(audit_deps.runner, "run_module", fake_run_module)

    assert audit_deps.run_audit(tmp_path) == 0
    assert len(calls) == 2
    export_kind, export_command, export_cwd = calls[0]
    assert export_kind == "command"
    assert export_command[0] == "uv"
    assert export_cwd == tmp_path
    audit_kind, audit_args, _ = calls[1]
    assert audit_kind == "module"
    assert audit_args[0] == "pip_audit"
    assert list(audit_args[-3:]) == ["--strict", "-s", "pypi"]


def test_run_audit_short_circuits_on_export_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fake_run_command(command: Sequence[str], *, cwd: Path | None = None) -> int:
        return 7

    called: list[str] = []

    def fake_run_module(module: str, args: Sequence[str] = (), *, cwd: Path | None = None) -> int:
        called.append(module)
        return 0

    monkeypatch.setattr(audit_deps.runner, "run_command", fake_run_command)
    monkeypatch.setattr(audit_deps.runner, "run_module", fake_run_module)

    assert audit_deps.run_audit(tmp_path) == 7
    assert called == []


def test_audit_service_defaults_to_pypi(tmp_path: Path) -> None:
    make_project(tmp_path)
    assert audit_deps.audit_service(tmp_path) == "pypi"


def test_audit_service_reads_canonist_override(tmp_path: Path) -> None:
    make_project(tmp_path, pyproject_extra='[tool.canonist.audit]\nservice = "osv"\n')
    assert audit_deps.audit_service(tmp_path) == "osv"


def test_audit_service_rejects_unknown_service(tmp_path: Path) -> None:
    make_project(tmp_path, pyproject_extra='[tool.canonist.audit]\nservice = "nonsense"\n')
    with pytest.raises(ValueError, match=r"invalid \[tool.canonist.audit\] service"):
        audit_deps.audit_service(tmp_path)


def test_run_audit_passes_service_through(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    audit_args: list[str] = []

    def fake_run_command(command: Sequence[str], *, cwd: Path | None = None) -> int:
        return 0

    def fake_run_module(module: str, args: Sequence[str] = (), *, cwd: Path | None = None) -> int:
        audit_args.extend(args)
        return 0

    monkeypatch.setattr(audit_deps.runner, "run_command", fake_run_command)
    monkeypatch.setattr(audit_deps.runner, "run_module", fake_run_module)

    assert audit_deps.run_audit(tmp_path, service="osv") == 0
    assert audit_args[-2:] == ["-s", "osv"]
