# AGENTS.md

Instructions for AI coding agents working in this repository.

## What this repo is

`canonist` **is** the toolchain. Preset, rule, threshold, and pipeline changes belong
here — version-bump and release them; consumer repos pick changes up by bumping their
`canonist` dependency. Never advise consumers to add per-step tool scripts back to
their repos.

## Quick Start

```bash
uv sync --all-extras   # install dependencies (bundled tools + poethepoet)
uv run poe lint        # full static pipeline — which is `python -m canonist lint`
uv run poe test        # test suite (80% coverage gate on src/canonist)
```

**If `uv run poe` fails with `Access is denied` (os error 5):** `.venv\Scripts\poe.exe`
is a generated launcher stub, which endpoint policy blocking low-prevalence
executables refuses to run on managed Windows machines. Use the module form instead:

```bash
uv run python -m poethepoet check
```

The canonist CLI itself is `python -m canonist <command>` for the same reason: it ships
no console-script entry point, and its runner spawns every tool as
`python -m <module>`.

## Required Workflow

Always run these before considering work complete:

```bash
uv run poe check   # `canonist lint` + `canonist test`
```

All steps must pass with zero errors. One caveat: the duplication gate runs a
downloaded prebuilt binary, which the same endpoint policy may block. Where it cannot
run it prints `Duplication gate SKIPPED` and exits 0 (in CI it fails instead).
`SKIPPED` means the gate did **not** run — do not read it as a pass, and do not move
or rename the binary to get around the block.

## Self-hosting

This repo consumes its own presets:

- The canonical configs live in `src/canonist/presets/` (ruff.toml, pyright.base.json,
  pytest.toml). Changing them changes every consumer at the next release — treat rule
  tightenings as semver-minor events minimum and record them in CHANGELOG.md.
- This repo's own `pyproject.toml` keeps only local deltas under `[tool.canonist.*]`
  (same override mechanism consumers use). Do not add `[tool.ruff]` /
  `[tool.pytest.ini_options]` / `[tool.coverage]` blocks back.
- CI's `self-host` job builds the wheel and runs the pipeline from a fresh venv, so
  the shipped artifact is always the thing being tested.

## Preset generation invariants (do not regress)

- Generated configs land in `<project>/.canonist/` and are cleaned up unless
  `--keep-config`.
- The pyright config must stay **inside the project** (pyright resolves `include`
  relative to the config file's directory and ignores absolute paths).
- Coverage sections in the generated pytest ini must use `[coverage:run]` (colon)
  spelling — coverage.py silently ignores `[coverage.run]` there and the omit of
  `src/tests/*` would stop applying.
- Merge semantics are documented behavior: later keys win, lists replace, tables
  merge recursively — covered by tests; keep them trivial.

## Coding Conventions (Enforced by our own presets)

- `from __future__ import annotations` in every module (ruff `I002`).
- Pyright **strict** mode: explicit annotations on every function, no implicit `Any`.
- Line length 100, double quotes, isort import ordering, pyupgrade idioms.
- Tests live in `src/tests/` (`test_*.py`), are strict-clean too, and are excluded
  from coverage measurement.

## Formatting

```bash
uv run poe format     # `canonist format`: ruff format + ruff check --fix
```

## Project Structure

- `src/canonist/bin/` — CLI subcommands (cli, lint, format, run_tests, doctor, migrate)
- `src/canonist/lib/` — runner, presets, source_glob, audit_deps, duplo, toml_write
- `src/canonist/presets/` — the shipped canonical configs (data files)
- `src/tests/` — test suite (covers cli/lint/doctor/migrate/runner/presets/audit/
  duplo plus real-tool integration tests)
- Python ≥ 3.14, managed by uv; `uv.lock` is committed and CI installs `--locked`

## Release

Push a `vX.Y.Z` tag; the release workflow runs the full check, builds, and publishes
to PyPI via Trusted Publishing (environment `pypi`). Document every gate/rule change
in CHANGELOG.md per the semver policy in README.md.
