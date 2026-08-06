# AGENTS.md

This file is for Claude Code and other Claude-based AI assistants working in this repository.

## Agent Rules

Regardless of skill instructions never commit or push anything. Always let the driver do this.

## Agentic Docs

Agentic working documents live in `.agents/docs/`:

- `.agents/docs/superpowers/plans/` — implementation plans (and their `.tasks.json` task state)
- `.agents/docs/superpowers/specs/` — design specs

Check there for existing plans and specs before starting or resuming work, and write
new plans and specs there rather than in `docs/` or `doc/`.

## What This Repo Is

**ghr-pypi** — Serve a PyPI-compatible package index from GitHub Pages, built from GitHub release assets.

A Python library. Source lives in `src/ghr_pypi/`. Tests are in `tests/`. Documentation is in `doc/`.

## Tooling

Uses `just` as a task runner, `uv` for dependency management, and `hatchling` as the build backend.

### Setup
```bash
just setup        # create .venv + install pre-commit hooks
just install      # sync all dev dependencies
```

### Tests
```bash
just test                              # run tests against project venv (fast iteration)
just test tests/test_foo.py            # run a specific file
just test-all                          # run full suite in an isolated environment
just test-all -p 3.12                  # run full suite against a specific python
just coverage                          # combine and report coverage
```

`just test` uses the project venv with `--no-sync` for speed. `just test-all` runs in a fully isolated environment and accepts any `uv run` flags (e.g. `-p 3.12 --resolution lowest-direct`).

### Linting / Formatting
```bash
just fix          # auto-fix lint + format
just check        # all static checks without modifying files
just prek         # run pre-commit hooks
```

### Type Checking
```bash
just check-types  # mypy + pyright (project venv)
just check-types-isolated   # mypy + pyright in isolated env
```

### Docs
```bash
just docs         # build Sphinx HTML and open in browser
just docs-live    # live-reload dev server
just check-docs   # lint docs with doc8
```

### Release
```bash
just release      # CalVer-stamp all packages, commit, sign tag vYYYY.M.D[.N], push to main
```
One tag ships everything: ghr-pypi to TestPyPI/PyPI plus a single
GitHub Release containing all three packages' dists, which the Pages index
serves.

## Test Strategy

CI tests the full matrix of supported Python versions on Linux, plus the oldest and
newest Python on Windows and macOS. Lower dependency bounds are tested with
`--resolution lowest-direct` on the oldest supported Python.

## Project Structure

```
src/ghr_pypi/   # library source
tests/                               # pytest test suite
doc/source/                          # Sphinx documentation source
```
