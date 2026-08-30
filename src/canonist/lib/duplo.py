"""Code-duplication gate powered by LucidShark's ``lucidshark-duplo`` (Duplo).

Ported from python-template's ``scripts/check_duplicates.py``. On first run the
pinned Duplo binary is downloaded for the current platform into the user cache
directory and reused thereafter, so the gate works locally and in CI with no
Rust toolchain or extra Python dependencies. Exits non-zero when the overall
duplicated-code percentage exceeds the threshold.

Because the binary is freshly downloaded, a managed endpoint may refuse to
execute it. When it cannot be downloaded or run the gate reports why and:
fails in CI (``CI`` env var set) so it can never silently vanish from a build,
and skips locally with a loud non-pass message so the rest of the pipeline
stays usable. ``LUCIDSHARK_DUPLO`` can point at an approved copy.
"""

from __future__ import annotations

import os
import platform
import re
import shutil
import subprocess
import sys
import tarfile
import urllib.request
import zipfile
from pathlib import Path

from canonist.lib import presets

DUPLO_VERSION = "0.2.0"
DEFAULT_THRESHOLD = 5.0
DEFAULT_MIN_LINES = 4


def configured_threshold(project: Path) -> float:
    """The configured duplication threshold: ``[tool.canonist.duplo] threshold``.

    Consumers whose codebase sits above the canonical 5% (e.g. many
    structurally similar adapters) can raise it explicitly; the value must be
    a positive number. Raises ``ValueError`` otherwise so misconfiguration
    fails loudly at pipeline start.
    """
    section = presets.as_table(presets.load_overrides(project).get("duplo"))
    value = section.get("threshold", DEFAULT_THRESHOLD)
    if isinstance(value, bool) or not isinstance(value, int | float) or value <= 0:
        raise ValueError(
            f"invalid [tool.canonist.duplo] threshold: {value!r} (expected a positive number)"
        )
    return float(value)


_BASE_URL = "https://github.com/toniantunovi/lucidshark-duplo/releases/download"

_UNAVAILABLE_HELP = """\
  The duplication gate requires a prebuilt binary that could not be
  downloaded or executed on this machine.
  Fix: point LUCIDSHARK_DUPLO at an existing copy of the binary."""

_ARCH_BY_MACHINE = {
    "x86_64": "x86_64",
    "amd64": "x86_64",
    "aarch64": "aarch64",
    "arm64": "aarch64",
}


def cache_dir() -> Path:
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home())
    else:
        base = os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    return Path(base) / "lucidshark-duplo"


def binary_name() -> str:
    return "lucidshark-duplo.exe" if sys.platform == "win32" else "lucidshark-duplo"


def _asset_name() -> str:
    if sys.platform == "win32":
        return "lucidshark-duplo-windows-x86_64.zip"
    os_part = {"linux": "linux", "darwin": "macos"}[sys.platform]
    arch = _ARCH_BY_MACHINE[platform.machine().lower()]
    return f"lucidshark-duplo-{os_part}-{arch}.tar.gz"


def _extract_archive(archive_path: Path, dest: Path) -> None:
    opener = zipfile.ZipFile if archive_path.suffix == ".zip" else tarfile.open
    with opener(archive_path) as archive:
        archive.extractall(dest)


def _download_binary(target: Path) -> None:
    asset = _asset_name()
    url = f"{_BASE_URL}/v{DUPLO_VERSION}/{asset}"
    target.parent.mkdir(parents=True, exist_ok=True)
    print(f"Downloading lucidshark-duplo v{DUPLO_VERSION} ({asset})...", file=sys.stderr)
    # Keep the asset's extension in the download path: urlretrieve's
    # auto-generated temp name drops it, defeating the zip-vs-tar detection
    # in _extract_archive.
    archive = target.parent / asset
    urllib.request.urlretrieve(url, archive)
    try:
        _extract_archive(archive, target.parent)
    finally:
        archive.unlink(missing_ok=True)
    if not target.is_file():
        sys.exit(f"error: {target} not found after extraction")
    target.chmod(0o755)


def resolve_binary() -> Path:
    env_path = os.environ.get("LUCIDSHARK_DUPLO")
    if env_path and Path(env_path).is_file():
        return Path(env_path)
    existing = shutil.which("lucidshark-duplo")
    if existing:
        return Path(existing)

    target = cache_dir() / f"v{DUPLO_VERSION}" / binary_name()
    if target.is_file():
        return target

    _download_binary(target)
    return target


def parse_duplication_percent(output: str) -> float | None:
    match = re.search(r"Duplication:\s*([\d.]+)%", output)
    return float(match.group(1)) if match else None


def in_ci() -> bool:
    return os.environ.get("CI", "").strip().lower() not in {"", "0", "false"}


def _run_duplo(min_lines: int) -> str:
    """Download Duplo if needed, run it over the git-tracked tree, return its output."""
    binary = resolve_binary()
    result = subprocess.run(
        [str(binary), "--git", "-m", str(min_lines), "-p", "100"],
        check=False,
        capture_output=True,
        text=True,
    )
    return result.stdout + result.stderr


def _report_unavailable(exc: OSError, *, required: bool) -> int:
    """Report that the gate could not run and decide whether that is fatal."""
    print(f"error: could not run lucidshark-duplo: {exc}", file=sys.stderr)
    print(_UNAVAILABLE_HELP, file=sys.stderr)
    if required:
        print("Duplication gate FAILED: gate could not run.", file=sys.stderr)
        return 1
    print(
        "Duplication gate SKIPPED: binary unavailable on this machine "
        "(not a pass - the gate did not run). It is fatal in CI; use "
        "LUCIDSHARK_DUPLO to point at an approved copy.",
        file=sys.stderr,
    )
    return 0


def gate(
    threshold: float = DEFAULT_THRESHOLD,
    min_lines: int = DEFAULT_MIN_LINES,
    output: str | None = None,
) -> int:
    """Run the duplication gate; return the process exit code.

    ``output`` may carry pre-captured duplo output (used by tests); when
    omitted the gate resolves and runs the binary itself.
    """
    required = in_ci()
    try:
        captured = output if output is not None else _run_duplo(min_lines)
    except OSError as exc:
        return _report_unavailable(exc, required=required)
    print(captured, end="")

    percent = parse_duplication_percent(captured)
    if percent is None:
        print("Duplication gate FAILED: could not parse duplication summary.", file=sys.stderr)
        return 1
    if percent > threshold:
        print(
            f"Duplication gate FAILED: {percent}% > {threshold}% threshold.",
            file=sys.stderr,
        )
        return 1

    print(f"Duplication gate passed: {percent}% <= {threshold}% threshold.", file=sys.stderr)
    return 0
