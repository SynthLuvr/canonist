# Changelog

All notable changes to canonist. Gate and rule changes that can fail previously-green
consumer repos are called out explicitly (semver policy: at least a minor bump).

## 0.1.0 - 2026-08-30

Initial release: the python-template toolchain consolidated into one versioned,
distributable dependency.

> Renamed from `py-canon` to `canonist` before first publication (the `py-canon`
> name was not registrable on PyPI). No `py-canon` release ever shipped, so the
> distribution, import name (`canonist`), config key (`[tool.canonist.*]`),
> generated-config dir (`.canonist/`), and CLI (`python -m canonist`) change
> atomically with no compatibility alias.

- CLI `lint | format | test | doctor | migrate` via `python -m canonist`
  (no console-script entry point; runner spawns tools as `python -m <module>`).
- Bundled tools as hard dependencies: ruff, pyright, pytest, pytest-cov, pip-audit.
- Shipped presets: `ruff.toml`, `pyright.base.json` (strict), `pytest.toml`
  (80% coverage gate, `src/tests/*` omitted) — effective configs generated per
  invocation into `<project>/.canonist/`, preset deep-merged with consumer
  `[tool.canonist.*]` overrides; `--keep-config` for inspection.
- `lint` pipeline (fail-fast, exit codes propagate): ruff format --check →
  ruff check → pyright (strict) → `uv lock --check` → pip-audit → duplication
  gate (5%). `--fast` skips audit + duplication.
- Gates ported from python-template's scripts: SCA audit (`uv export` +
  `pip-audit --strict`) and the lucidshark-duplo duplication gate with the
  SKIPPED-locally / fatal-in-CI policy.
- `migrate` with `--dry-run`: swaps tool dev-deps for `canonist`, collapses Poe
  tasks, ports config blocks to preset overrides (deltas only), deletes the
  ported `scripts/`, appends `.canonist/` to `.gitignore`.
- Self-hosting: this repo lints/tests itself through its own CLI, and CI runs the
  pipeline from the built wheel in a fresh venv.
- Fixed (Windows): the generated pyright config raised ``ValueError`` when the
  consumer project and the running interpreter's venv sat on different drives
  (the CI Windows matrix leg); such paths now fall back to absolute posix form.
