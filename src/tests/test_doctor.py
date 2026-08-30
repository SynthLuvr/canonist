from __future__ import annotations

from typing import TYPE_CHECKING

from pycanon.bin import doctor as doctor_mod
from tests.fixturelib import make_project

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


def test_check_python_passes_on_current_interpreter() -> None:
    result = doctor_mod.check_python()
    assert result.ok is True
    assert "3.14" in result.detail


def test_check_python_fails_on_old_interpreter(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(doctor_mod.sys, "version_info", (3, 11, 0, "final", 0))
    result = doctor_mod.check_python()
    assert result.ok is False


def test_check_module_found_vs_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_find_spec(module: str) -> object | None:
        return object() if module else None

    monkeypatch.setattr(doctor_mod.util, "find_spec", fake_find_spec)
    assert doctor_mod.check_module("ruff").ok is True

    def fake_find_spec_none(module: str) -> None:
        return None

    monkeypatch.setattr(doctor_mod.util, "find_spec", fake_find_spec_none)
    assert doctor_mod.check_module("ruff").ok is False
    assert doctor_mod.check_module("ruff", advisory=True).ok is None


def test_check_executable_found_vs_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_which(name: str) -> str | None:
        return f"/usr/bin/{name}"

    monkeypatch.setattr(doctor_mod.shutil, "which", fake_which)
    assert doctor_mod.check_executable("uv").ok is True

    def fake_which_none(name: str) -> None:
        return None

    monkeypatch.setattr(doctor_mod.shutil, "which", fake_which_none)
    assert doctor_mod.check_executable("uv").ok is False
    assert doctor_mod.check_executable("pandoc", advisory=True).ok is None


def test_check_presets() -> None:
    assert doctor_mod.check_presets().ok is True


def test_check_overrides(tmp_path: Path) -> None:
    project = make_project(tmp_path)
    assert doctor_mod.check_overrides(project).ok is True
    empty = tmp_path / "empty"
    empty.mkdir()
    assert doctor_mod.check_overrides(empty).ok is None


def test_check_overrides_invalid_toml(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("[project\nbroken", encoding="utf-8")
    result = doctor_mod.check_overrides(tmp_path)
    assert result.ok is False


def test_check_duplo_states(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    def fake_which_none(name: str) -> str | None:
        return None

    def missing_binary() -> Path:
        return tmp_path / "nowhere"

    def existing_binary() -> Path:
        cached = tmp_path / "lucidshark-duplo"
        cached.write_text("", encoding="utf-8")
        return cached

    monkeypatch.delenv("LUCIDSHARK_DUPLO", raising=False)
    monkeypatch.setattr(doctor_mod.shutil, "which", fake_which_none)
    monkeypatch.setattr(doctor_mod, "cached_binary", missing_binary)
    assert doctor_mod.check_duplo().ok is None  # advisory: will download on first lint
    monkeypatch.setattr(doctor_mod, "cached_binary", existing_binary)
    assert doctor_mod.check_duplo().ok is True


def test_run_doctor_all_good(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project = make_project(tmp_path)
    monkeypatch.chdir(project)

    def fake_which(name: str) -> str | None:
        return f"/usr/bin/{name}"

    def fake_find_spec(module: str) -> object:
        return object()

    monkeypatch.setattr(doctor_mod.shutil, "which", fake_which)
    monkeypatch.setattr(doctor_mod.util, "find_spec", fake_find_spec)
    assert doctor_mod.run_doctor() == 0


def test_run_doctor_fails_on_missing_bundled_tool(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    project = make_project(tmp_path)
    monkeypatch.chdir(project)

    def fake_which(name: str) -> str | None:
        return f"/usr/bin/{name}"

    def fake_find_spec(module: str) -> object | None:
        return None if module == "pyright" else object()

    monkeypatch.setattr(doctor_mod.shutil, "which", fake_which)
    monkeypatch.setattr(doctor_mod.util, "find_spec", fake_find_spec)
    assert doctor_mod.run_doctor() == 1
    captured = capsys.readouterr()
    assert "[FAIL] pyright" in captured.out
    assert "pyright" in captured.err
