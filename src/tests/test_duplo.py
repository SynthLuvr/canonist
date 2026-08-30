from __future__ import annotations

from typing import TYPE_CHECKING

from pycanon.lib import duplo

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


def test_parse_duplication_percent() -> None:
    assert duplo.parse_duplication_percent("... Duplication: 3.45% ...") == 3.45
    assert duplo.parse_duplication_percent("no summary here") is None


def test_in_ci_detection(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CI", raising=False)
    assert duplo.in_ci() is False
    monkeypatch.setenv("CI", "true")
    assert duplo.in_ci() is True
    monkeypatch.setenv("CI", "0")
    assert duplo.in_ci() is False


def test_gate_passes_at_or_below_threshold(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(duplo, "in_ci", lambda: False)
    assert duplo.gate(output="Duplication: 5.0%", threshold=5.0) == 0
    assert "passed" in capsys.readouterr().err


def test_gate_fails_above_threshold(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(duplo, "in_ci", lambda: False)
    assert duplo.gate(output="Duplication: 5.01%") == 1
    assert "5.01% > 5.0%" in capsys.readouterr().err


def test_gate_fails_on_unparseable_output(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(duplo, "in_ci", lambda: True)
    assert duplo.gate(output="garbage") == 1
    assert "could not parse" in capsys.readouterr().err


def test_gate_unavailable_skips_locally(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(duplo, "in_ci", lambda: False)

    def broken(min_lines: int) -> str:
        raise OSError("blocked")

    monkeypatch.setattr(duplo, "_run_duplo", broken)
    assert duplo.gate() == 0
    captured = capsys.readouterr().err
    assert "SKIPPED" in captured
    assert "not a pass" in captured


def test_gate_unavailable_fails_in_ci(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(duplo, "in_ci", lambda: True)

    def broken(min_lines: int) -> str:
        raise OSError("blocked")

    monkeypatch.setattr(duplo, "_run_duplo", broken)
    assert duplo.gate() == 1
    assert "FAILED" in capsys.readouterr().err


def test_resolve_binary_env_override(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    binary = tmp_path / "duplo"
    binary.write_text("", encoding="utf-8")
    monkeypatch.setenv("LUCIDSHARK_DUPLO", str(binary))
    assert duplo.resolve_binary() == binary


def test_cached_binary_path_shape() -> None:
    cached = duplo.cache_dir() / f"v{duplo.DUPLO_VERSION}" / duplo.binary_name()
    assert cached.name.startswith("lucidshark-duplo")
    assert f"v{duplo.DUPLO_VERSION}" in str(cached)
