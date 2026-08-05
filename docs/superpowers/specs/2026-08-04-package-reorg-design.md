# Design: Reorganize as a Publishable Package (gh-pages-pypi)

**Date:** 2026-08-04
**Status:** Approved
**Supersedes layout of:** `2026-08-04-gh-pages-pypi-design.md` (demo behavior is preserved)

## Goal

Restructure the repository around bckohan/python-package-template (cookiecutter)
so the index builder becomes **gh-pages-pypi** — a package published to PyPI and
runnable as a uvx tool — while the repository remains its own living demo
(demo packages + GitHub Pages index built by the tool itself). The builder's
HTML generation moves to Jinja2 templates and its CLI to Typer.

## Decisions

- **Package/tool/import name:** `gh-pages-pypi` / `gh-pages-pypi` / `gh_pages_pypi`
- **Template application:** run `uvx cookiecutter` on the template, merge output
  into this repo (template files win; our content ports into the structure)
- **Demo:** kept — packages/, demo release chain, live Pages index
- **License:** MIT (replaces CC0)
- **CLI shape:** single command (no subcommands):
  `gh-pages-pypi OWNER/REPO --out DIR [--token TOKEN]`
- **Cookiecutter answers:** project_slug=gh-pages-pypi, description="Serve a
  PyPI-compatible package index from GitHub Pages, built from GitHub release
  assets.", author=Brian Kohan <bckohan@gmail.com>, github_owner=bckohan,
  version=0.1.0, scorecard=false, license=MIT. Post-generation, URLs referring
  to the slug-named repo are corrected to this repo's actual name
  (`gh_pages_pypi`); readthedocs/codecov URLs keep the slug (account wiring is
  a later manual step).

## Resulting Structure

```
pyproject.toml            # hatchling; name gh-pages-pypi 0.1.0; deps typer, jinja2
                          # [project.scripts] gh-pages-pypi = "gh_pages_pypi.cli:app"
src/gh_pages_pypi/
  __init__.py             # __version__
  cli.py                  # Typer app; thin argument layer over index.py
  index.py                # ported core logic from scripts/build_index.py
  templates/              # landing.html, simple_root.html, project.html
  py.typed
tests/                    # template layout; ported + adapted tests
packages/demo-lib,demo-app  # unchanged demo packages
.github/workflows/
  release.yml             # from template: PyPI publish on v* tags
  demo-release.yml        # our old release.yml renamed; demo-*-v* tags (no v* collision)
  pages.yml               # modified: astral-sh/setup-uv; `uv run gh-pages-pypi ...`
  test.yml lint.yml bandit.yml zizmor.yml  # from template (scorecard omitted)
doc/                      # template sphinx skeleton
justfile                  # template recipes + our CalVer recipe renamed `demo-release`
CONTRIBUTING.md SECURITY.md CLAUDE.md AGENTS.md .pre-commit-config.yaml
LICENSE                   # MIT
```

Removed: `scripts/build_index.py` (moves into the package), root `.venv`
workflow (template uses uv), CC0 LICENSE text.

## Components

### index.py (core)

Ported nearly verbatim from `scripts/build_index.py`, keeping tested behavior:
PEP 503 `normalize`, wheel/sdist `project_name_from_filename`, `fetch_releases`
(GitHub API, Bearer token), chunked-sha256 `hash_url`, `collect_projects`
(draft releases skipped, non-package assets ignored, injectable hash for
tests), `pages_url`, `write_site`. `write_site` renders three Jinja2 templates
via `Environment(loader=PackageLoader("gh_pages_pypi"), autoescape=True)`
instead of `str.format` — templates ship as package data so the tool works via
uvx anywhere.

### cli.py (Typer)

`app = typer.Typer()`; one command with: `repo` (positional, OWNER/NAME),
`--out` (required, Path), `--token` (envvar GITHUB_TOKEN). Behavior preserved
from the argparse version: missing token → clean error exit; API failure →
`error: GitHub API request for <repo> failed: ...`; zero package assets →
`error: no package assets found...` refusal; success prints the project count.
Non-zero exit codes in all error cases.

### Workflows

- `pages.yml`: replace setup-python + script invocation with
  astral-sh/setup-uv + `uv run gh-pages-pypi "$GITHUB_REPOSITORY" --out site`.
  Triggers, permissions, concurrency, deploy jobs unchanged. The repo dogfoods
  the packaged tool from source.
- `release.yml` (template): PyPI publishing on `v*` tags. Requires one-time
  PyPI trusted-publisher setup by the owner.
- `demo-release.yml`: current release workflow renamed, unchanged behavior
  (demo-*-v* tags → build → GitHub Release → dispatch pages.yml — dispatch
  target name stays `pages.yml`).
- Template `test.yml`, `lint.yml`, `bandit.yml`, `zizmor.yml`, dependabot,
  CODEOWNERS adopted as-is. Scorecard omitted (cookiecutter option false).

### justfile

Template justfile adopted (uv-based dev recipes). Our CalVer demo-release
recipe is appended, renamed `demo-release`, and updated for uv
(`uv run pytest` instead of sourcing `.venv`).

### Tests

Ported to template test layout: `test_build_index.py` →
`tests/test_index.py` (import `gh_pages_pypi.index`; same fixtures including
the draft-release exclusion), CLI test switches from argparse `main([...])` to
`typer.testing.CliRunner`. `tests/test_packages.py` (demo packages) retained;
demo packages installed into the uv dev environment as editable members of the
dev dependency group so their tests keep running.

## Error Handling

Unchanged semantics from the current script (clean messages, non-zero exits,
refusal to build an empty index). Template lint/type gates (ruff, mypy,
pyright basic) must pass on the new package code.

## Verification

- `uv run pytest` — full suite green
- `uv run gh-pages-pypi bckohan/gh_pages_pypi --out <tmp>` — real-API smoke
  test produces the three-page site
- `uvx --from git+https://github.com/bckohan/gh_pages_pypi gh-pages-pypi
  --help` — proves uvx-ability before PyPI exists
- Push: template test/lint workflows green; demo release chain re-run end to
  end (just demo-release → GitHub Release → pages deploy → live pip install)

## Out of Scope / Later Manual Steps

- PyPI trusted-publisher registration and first `v0.1.0` tag (owner action)
- readthedocs and codecov account wiring
- Multi-repo features for the tool (config files, multiple indexes) — YAGNI
