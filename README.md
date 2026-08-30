# canonist

An opinionated Python toolchain as **one versioned, distributable dependency**.
Invoke as `python -m canonist` (no console-script launcher, so it works on
managed Windows endpoints that block generated `.exe` stubs).

One dev dependency replaces the duplicated Python toolchain — the Poe task blocks,
`scripts/audit_deps.py`, `scripts/check_duplicates.py`, the ruff/pyright/pytest config
blocks, and the six-package dev dependency set — across every Python repo that adopts
it. Tool, rule, and preset changes happen here; consumers bump the version and the
whole toolchain moves together.

## Quick start (consumer)

```bash
uv add --optional dev canonist poethepoet   # or your usual dev-dependency flow
```

```toml
[tool.poe.tasks.lint]
cmd = "python -m canonist lint"
[tool.poe.tasks.test]
cmd = "python -m canonist test"
```

Migrating an existing python-template-style repo? Run `python -m canonist migrate --dry-run`
first; it rewrites `pyproject.toml` (tool dev-deps → `canonist`, Poe tasks collapsed,
config blocks ported to preset overrides) and deletes the ported `scripts/` helpers.
Reverting the migration commit is the rollback.

## Commands

| Command | Runs |
|---------|------|
| `python -m canonist lint` | Fail-fast pipeline: `ruff format --check`, `ruff check`, `pyright` (strict), `uv lock --check`, pip-audit (SCA), duplication gate |
| `python -m canonist format` | `ruff format` then `ruff check --fix` (writes changes) |
| `python -m canonist test` | pytest with the canonical coverage gate (80%, tests omitted from measurement) |
| `python -m canonist doctor` | Environment diagnostics: Python ≥ 3.14, uv, bundled tools, presets, duplo availability |
| `python -m canonist migrate` | Convert an existing repo to consume canonist (`--dry-run` supported) |

Options: `--fast` (lint: skip pip-audit and the duplication gate), `--keep-config`
(keep the generated configs in `.canonist/` for inspection), `--dry-run` (migrate).
Exit codes: `0` success/help, `2` usage error, otherwise the failing step's code
propagates. Positional path arguments default to `src/` and `scripts/` (whichever
exist); test paths default to the merged preset's `testpaths`.

## How the presets work

The canonical ruff, pyright, and pytest/coverage configurations live in
[`src/canonist/presets/`](src/canonist/presets/) and ship inside the wheel. Python has
no version-independent `node_modules`-style path (site-packages embeds the interpreter
version), and ruff rejects multiple `--config` files — so at invocation time canonist
writes the **effective config** (preset deep-merged with your `[tool.canonist.*]`
overrides) into `<project>/.canonist/` and points each tool at it:

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
[tool.canonist.ruff.lint.per-file-ignores]
"scripts/*" = ["S"]          # repo-specific paths; preset values elsewhere survive
```

`.canonist/` is removed after every run unless `--keep-config` is passed (add it to
`.gitignore`; `migrate` does this for you).

## Why the tools are hard dependencies

npm devDependencies are transitive; Python `[dependency-groups]` are not — a consumer
that adds canonist as a dev dependency would not receive its group members. So the
bundled tools (ruff, pyright, pytest, pytest-cov, pip-audit) are canonist's install
dependencies. Poe stays consumer-side (it is the shell around the tools, not a tool),
and the pinned lucidshark-duplo binary is downloaded at first use, exactly as in
python-template.

## Gates and skip policies

- **Audit (SCA)** — `uv export` → `pip-audit --strict`; skipped by `--fast`.
- **Duplication gate** — lucidshark-duplo, 5% threshold. If the binary cannot be
  downloaded or executed it **fails in CI** and prints `SKIPPED` locally (a loud
  non-pass, not a silent one). `LUCIDSHARK_DUPLO` points at an approved copy.
- **Lockfile freshness** — `uv lock --check`; a repo without `uv.lock` skips locally
  and fails in CI.
- **Coverage** — 80% gate, `src/tests/*` omitted from measurement.

## Self-hosting

This repository eats its own dogfood: its Poe tasks are `python -m canonist lint` /
`test`, its only config deltas are the `[tool.canonist.*]` overrides in `pyproject.toml`,
and CI additionally builds the wheel, installs it into a fresh venv, and runs the
pipeline against this checkout with the built artifact (see the `self-host` job in
[ci.yml](.github/workflows/ci.yml)).

## Versioning

Semver: rule additions or threshold tightenings that can fail previously-green
repos are **minor** bumps at minimum and are called out with each release;
breaking CLI/config changes are **major**. Until 1.0, tighten freely but
document. Releases are dispatched from the **Release** workflow (exact version or
patch/minor/major bump); it publishes to PyPI via Trusted Publishing, lands the
version bump as a PR, tags `vX.Y.Z`, and creates the GitHub release.

## License

MIT — see [LICENSE](LICENSE).
