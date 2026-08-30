"""Shared helpers: build throwaway consumer projects for tests.

These modules are deliberately byte-exact ruff/pyright-clean so the
integration tests exercise the tools, not fixture typos.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

GOOD_MODULE = """from __future__ import annotations


def add(a: int, b: int) -> int:
    return a + b
"""

# Annotated header but sloppy spacing: `pycanon format` must fix it.
UNFORMATTED_MODULE = (
    "from __future__ import annotations\n\n\ndef  add( a:int,b:int )->int:\n    return a+b\n"
)

# Ruff-clean but not strict-typing-clean: the pyright step must fail on it.
UNTYPED_MODULE = "from __future__ import annotations\n\n\ndef add(x, y):\n    return x + y\n"

# Unused import: the ruff check step must fail on it (fixable with --fix).
LINT_ERROR_MODULE = "import os\n"

# A line-length violation (E501): neither `ruff format` nor `ruff check --fix`
# can fix it, so the format pipeline must fail on it.
UNFIXABLE_MODULE = "# " + "x" * 110 + "\n"

GOOD_TEST = """from __future__ import annotations

from pkg import add


def test_add() -> None:
    assert add(1, 2) == 3
"""

BASE_PYPROJECT = """\
[project]
name = "fixture"
version = "0.0.0"
requires-python = ">=3.14"
dependencies = []
"""


def make_project(
    root: Path,
    *,
    module: str = GOOD_MODULE,
    extra_module: str | None = None,
    test: str | None = GOOD_TEST,
    pyproject_extra: str = "",
) -> Path:
    """Create a minimal src-layout consumer project under ``root``."""
    package = root / "src" / "pkg"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text(module, encoding="utf-8")
    if extra_module is not None:
        (package / "bad.py").write_text(extra_module, encoding="utf-8")
    tests = root / "src" / "tests"
    tests.mkdir(parents=True)
    (tests / "__init__.py").write_text("", encoding="utf-8")
    if test is not None:
        (tests / "test_pkg.py").write_text(test, encoding="utf-8")
    (root / "pyproject.toml").write_text(BASE_PYPROJECT + pyproject_extra, encoding="utf-8")
    return root
