"""Minimal TOML serialization for values that survive a ``tomllib`` round-trip.

Supports exactly the shapes that appear in tool configuration and
``pyproject.toml`` files: strings, booleans, integers, floats, lists, and
string-keyed tables (rendered as ``[dotted.headers]`` or ``[[arrays]]``).
Anything else (datetimes, non-string keys) raises :class:`TomlWriteError`
naming the offending key path, so callers fail loudly instead of emitting
silently-wrong TOML.

Used both for the generated ruff config and for ``migrate``'s rewrite of the
consumer's ``pyproject.toml`` (comments are not preserved; the migration diff
is meant to be reviewed).
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping


type Scalar = str | bool | int | float
type TomlValue = Scalar | list[TomlValue] | dict[str, TomlValue]


class TomlWriteError(ValueError):
    """Raised when a value cannot be represented as TOML by this writer."""


def dumps(data: Mapping[str, TomlValue]) -> str:
    """Serialize ``data`` to a TOML document string."""
    lines: list[str] = []
    _emit_table(data, (), lines)
    return "\n".join(lines) + ("\n" if lines else "")


def _emit_table(
    table: Mapping[str, TomlValue],
    path: tuple[str, ...],
    lines: list[str],
    *,
    emit_header: bool = True,
) -> None:
    scalars: list[tuple[str, TomlValue]] = []
    children: list[tuple[str, dict[str, TomlValue]]] = []
    arrays: list[tuple[str, list[dict[str, TomlValue]]]] = []
    for key, value in table.items():
        quoted = _key(key)
        if isinstance(value, dict):
            children.append((quoted, value))
        elif isinstance(value, list) and value and all(isinstance(item, dict) for item in value):
            arrays.append((quoted, [item for item in value if isinstance(item, dict)]))
        else:
            scalars.append((quoted, value))
    # A table header is needed only when the table carries its own keys or is
    # empty; pure container tables are represented by their children's headers.
    if path and emit_header and (scalars or not (children or arrays)):
        _header(path, lines, array=False)
    for key, value in scalars:
        lines.append(f"{key} = {_format(value, (*path, key))}")
    for key, child in children:
        _emit_table(child, (*path, key), lines)
    for key, items in arrays:
        for item in items:
            _header((*path, key), lines, array=True)
            _emit_table(item, (*path, key), lines, emit_header=False)


def _header(path: tuple[str, ...], lines: list[str], *, array: bool) -> None:
    if lines:
        lines.append("")
    name = ".".join(path)
    lines.append(f"[[{name}]]" if array else f"[{name}]")


def _key(key: str) -> str:
    if key and all(char.isalnum() or char in "-_" for char in key):
        return key
    return json.dumps(key)


def _format(value: TomlValue, path: tuple[str, ...]) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return _number(value, path)
    if isinstance(value, str):
        # JSON basic-string escaping is a valid TOML basic string.
        return json.dumps(value)
    if isinstance(value, list):
        items = ", ".join(_format(item, path) for item in value)
        return f"[{items}]"
    if isinstance(value, dict):  # pyright: ignore[reportUnnecessaryIsInstance]
        # Reachable at runtime for values that were cast into TomlValue
        # (migrate round-trips tomllib output); the type system says this
        # branch is exhaustive, so the guard exists for the trailing raise.
        inner = ", ".join(
            f"{_key(key)} = {_format(item, (*path, key))}" for key, item in value.items()
        )
        return f"{{{inner}}}"
    raise TomlWriteError(f"unsupported value of type {type(value).__name__} at {_where(path)}")


def _number(value: int | float, path: tuple[str, ...]) -> str:
    if isinstance(value, float) and (value != value or value in {float("inf"), float("-inf")}):
        raise TomlWriteError(f"non-finite float at {_where(path)}")
    return str(value)


def _where(path: tuple[str, ...]) -> str:
    return ".".join(path) or "<root>"
