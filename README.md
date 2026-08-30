# py-canon

The SynthLuvr Python toolchain as **one versioned, distributable dependency** — the
[`ts-canon`](https://github.com/SynthLuvr/ts-canon) pattern, for Python. Import name
`pycanon`; invoke as `python -m pycanon` (no console-script launcher, so it works on
managed Windows endpoints that block generated `.exe` stubs).

One dev dependency replaces the duplicated Python toolchain — the Poe task blocks,
`scripts/audit_deps.py`, `scripts/check_duplicates.py`, the ruff/pyright/pytest config
blocks, and the six-package dev dependency set — across every Python repo in the org.
Tool, rule, and preset changes happen here; consumers bump the version and the whole
toolchain moves together.

## Quick start (consumer)

```bash
uv add --optional dev py-canon poethepoet   # or your usual dev-dependency flow
```

```toml
[tool.poe.tasks.lint]
cmd = "python -m pycanon lint"
[tool.poe.tasks.test]
cmd = "python -m pycanon test"
```

Migrating an existing python-template-style repo? Run `python -m pycanon migrate --dry-run`
first; it rewrites `pyproject.toml` (tool dev-deps → `py-canon`, Poe tasks collapsed,
config blocks ported to preset overrides) and deletes the ported `scripts/` helpers.
Reverting the migration commit is the rollback.

## Commands

| Command | Runs |
|---------|------|
| `python -m pycanon lint` | Fail-fast pipeline: `ruff format --check`, `ruff check`, `pyright` (strict), `uv lock --check`, pip-audit (SCA), duplication gate |
| `python -m pycanon format` | `ruff format` then `ruff check --fix` (writes changes) |
| `python -m pycanon test` | pytest with the canonical coverage gate (80%, tests omitted from measurement) |
| `python -m pycanon doctor` | Environment diagnostics: Python ≥ 3.14, uv, bundled tools, presets, duplo availability |
| `python -m pycanon migrate` | Convert an existing repo to consume py-canon (`--dry-run` supported) |

Options: `--fast` (lint: skip pip-audit and the duplication gate), `--keep-config`
(keep the generated configs in `.pycanon/` for inspection), `--dry-run` (migrate).
Exit codes: `0` success/help, `2` usage error, otherwise the failing step's code
propagates. Positional path arguments default to `src/` and `scripts/` (whichever
exist); test paths default to the merged preset's `testpaths`.

## How the presets work

The canonical ruff, pyright, and pytest/coverage configurations live in
[`src/pycanon/presets/`](src/pycanon/presets/) and ship inside the wheel. Python has
no version-independent `node_modules`-style path (site-packages embeds the interpreter
version), and ruff rejects multiple `--config` files — so at invocation time py-canon
writes the **effective config** (preset deep-merged with your `[tool.pycanon.*]`
overrides) into `<project>/.pycanon/` and points each tool at it:

- **ruff** — merged `ruff.toml` passed as the single `--config` file.
- **pyright** — a generated `pyrightconfig.json` that `extends` the bundled
  `pyright.base.json` (strict mode flows from the preset). The config dir sits inside
  the project because pyright resolves `include` relative to the config file and
  rejects absolute paths.
- **pytest** — a generated `pytest.ini` carrying `[pytest]` and `[coverage:run]`
  sections (colon spelling: coverage ignores `[coverage.run]` in ini files).

Merge semantics: **later keys win, lists replace, tables merge recursively.** Keep only
true local deltas in `pyproject.toml`:

```toml
[tool.pycanon.ruff.lint.per-file-ignores]
"scripts/*" = ["S"]          # repo-specific paths; preset values elsewhere survive
```

`.pycanon/` is removed after every run unless `--keep-config` is passed (add it to
`.gitignore`; `migrate` does this for you).

## Why the tools are hard dependencies

npm devDependencies are transitive; Python `[dependency-groups]` are not — a consumer
that adds py-canon as a dev dependency would not receive its group members. So, exactly
like ts-canon's "regular deps, not peers" decision, the bundled tools (ruff, pyright,
pytest, pytest-cov, pip-audit) are py-canon's install dependencies. Poe stays
consumer-side (it is the shell around the tools, not a tool), and the pinned
lucidshark-duplo binary is downloaded at first use, exactly as in python-template.

## Gates and skip policies

- **Audit (SCA)** — `uv export` → `pip-audit --strict`; skipped by `--fast`.
- **Duplication gate** — lucidshark-duplo, 5% threshold. If the binary cannot be
  downloaded or executed it **fails in CI** and prints `SKIPPED` locally (a loud
  non-pass, not a silent one). `LUCIDSHARK_DUPLO` points at an approved copy.
- **Lockfile freshness** — `uv lock --check`; a repo without `uv.lock` skips locally
  and fails in CI.
- **Coverage** — 80% gate, `src/tests/*` omitted from measurement.

## Self-hosting

This repository eats its own dogfood: its Poe tasks are `python -m pycanon lint` /
`test`, its only config deltas are the `[tool.pycanon.*]` overrides in `pyproject.toml`,
and CI additionally builds the wheel, installs it into a fresh venv, and runs the
pipeline against this checkout with the built artifact (see the `self-host` job in
[ci.yml](.github/workflows/ci.yml)).

## Versioning

Semver, mirroring ts-canon's policy: rule additions or threshold tightenings that can
fail previously-green repos are **minor** bumps at minimum and are documented in
[CHANGELOG.md](CHANGELOG.md); breaking CLI/config changes are **major**. Until 1.0,
tighten freely but document. Releases are tag-driven (`v*`) and publish to PyPI via
Trusted Publishing.
