# Changelog

All notable changes to py-canon. Gate and rule changes that can fail previously-green
consumer repos are called out explicitly (semver policy: at least a minor bump).

## 0.1.0 - 2026-08-30

Initial release: the ts-canon pattern ported to the python-template toolchain.

- CLI `lint | format | test | doctor | migrate` via `python -m pycanon`
  (no console-script entry point; runner spawns tools as `python -m <module>`).
- Bundled tools as hard dependencies: ruff, pyright, pytest, pytest-cov, pip-audit.
- Shipped presets: `ruff.toml`, `pyright.base.json` (strict), `pytest.toml`
  (80% coverage gate, `src/tests/*` omitted) — effective configs generated per
  invocation into `<project>/.pycanon/`, preset deep-merged with consumer
  `[tool.pycanon.*]` overrides; `--keep-config` for inspection.
- `lint` pipeline (fail-fast, exit codes propagate): ruff format --check →
  ruff check → pyright (strict) → `uv lock --check` → pip-audit → duplication
  gate (5%). `--fast` skips audit + duplication.
- Gates ported from python-template's scripts: SCA audit (`uv export` +
  `pip-audit --strict`) and the lucidshark-duplo duplication gate with the
  SKIPPED-locally / fatal-in-CI policy.
- `migrate` with `--dry-run`: swaps tool dev-deps for `py-canon`, collapses Poe
  tasks, ports config blocks to preset overrides (deltas only), deletes the
  ported `scripts/`, appends `.pycanon/` to `.gitignore`.
- Self-hosting: this repo lints/tests itself through its own CLI, and CI runs the
  pipeline from the built wheel in a fresh venv.
