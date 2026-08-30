from __future__ import annotations

import tomllib
from datetime import date
from typing import cast

import pytest

from pycanon.lib.toml_write import TomlValue, TomlWriteError, dumps


def test_scalars_and_lists_round_trip() -> None:
    original: dict[str, TomlValue] = {
        "name": 'a "quoted" value',
        "count": 3,
        "ratio": 1.5,
        "flag": True,
        "off": False,
        "items": ["a", "b"],
        "empty": [],
    }
    assert tomllib.loads(dumps(original)) == original


def test_nested_tables() -> None:
    text = dumps({"tool": {"ruff": {"line-length": 100}, "pyright": {"strict": True}}})
    assert "[tool.ruff]" in text
    assert "line-length = 100" in text
    assert "[tool.pyright]" in text
    assert "strict = true" in text


def test_arrays_of_tables() -> None:
    text = dumps({"tool": {"poe": {"seq": [{"cmd": "a"}, {"cmd": "b"}]}}})
    assert "[[tool.poe.seq]]" in text
    assert 'cmd = "a"' in text
    assert 'cmd = "b"' in text
    assert tomllib.loads(text)["tool"]["poe"]["seq"] == [{"cmd": "a"}, {"cmd": "b"}]


def test_quoted_keys() -> None:
    text = dumps({"lint": {"per-file-ignores": {"src/tests/*": ["S101"]}}})
    assert '"src/tests/*" = ["S101"]' in text


def test_inline_table_inside_list() -> None:
    text = dumps({"outer": {"items": [{"cmd": "run"}, "plain"]}})
    assert tomllib.loads(text)["outer"]["items"] == [{"cmd": "run"}, "plain"]


def test_empty_document() -> None:
    assert dumps({}) == ""


def test_unsupported_value_raises() -> None:
    bad = cast("dict[str, TomlValue]", {"when": date(2020, 1, 1)})
    with pytest.raises(TomlWriteError, match="when"):
        dumps(bad)


def test_non_finite_float_raises() -> None:
    with pytest.raises(TomlWriteError, match="ratio"):
        dumps({"ratio": float("inf")})


def test_empty_subtable() -> None:
    text = dumps({"tool": {"empty_section": {}}})
    assert text == "[tool.empty_section]\n"
