# gh-pages-pypi
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![PyPI version](https://badge.fury.io/py/gh-pages-pypi.svg)](https://pypi.python.org/pypi/gh-pages-pypi/)
[![PyPI pyversions](https://img.shields.io/pypi/pyversions/gh-pages-pypi.svg)](https://pypi.python.org/pypi/gh-pages-pypi/)
[![PyPI status](https://img.shields.io/pypi/status/gh-pages-pypi.svg)](https://pypi.python.org/pypi/gh-pages-pypi)
[![Documentation Status](https://readthedocs.org/projects/gh-pages-pypi/badge/?version=latest)](http://gh-pages-pypi.readthedocs.io/?badge=latest/)
[![Code Cov](https://codecov.io/gh/bckohan/gh_pages_pypi/branch/main/graph/badge.svg)](https://codecov.io/gh/bckohan/gh_pages_pypi)
[![Test Status](https://github.com/bckohan/gh_pages_pypi/actions/workflows/test.yml/badge.svg?branch=main)](https://github.com/bckohan/gh_pages_pypi/actions/workflows/test.yml?query=branch:main)
[![Lint Status](https://github.com/bckohan/gh_pages_pypi/actions/workflows/lint.yml/badge.svg?branch=main)](https://github.com/bckohan/gh_pages_pypi/actions/workflows/lint.yml?query=branch:main)

Serve a **PyPI-compatible package index from GitHub Pages**, built from
**GitHub release assets**. No index server, nothing published to pypi.org —
just static PEP 503 HTML, rebuilt automatically on every release.

This repository is both the tool and its own demo: the index at
[bckohan.github.io/gh_pages_pypi](https://bckohan.github.io/gh_pages_pypi/)
is built by this tool from this repo's releases.

## Installation

```bash
pip install gh-pages-pypi
# or run it without installing:
uvx gh-pages-pypi --help
```

## Usage

```bash
gh-pages-pypi OWNER/REPO --out site [--token TOKEN]
```

Reads every (non-draft) release of `OWNER/REPO` via the GitHub API
(`--token` defaults to `$GITHUB_TOKEN`), collects the wheel/sdist assets,
computes each file's `sha256`, and writes a static
[PEP 503](https://peps.python.org/pep-0503/) index to `site/`:

```
site/index.html                   → human landing page
site/simple/                      → lists every project
site/simple/<project>/            → file links with #sha256= fragments
```

It refuses to build an empty index (non-zero exit) so a misconfigured CI run
can never deploy a blank package index.

## Using it in your own repo

1. In repo **Settings → Pages**, set **Source** to **GitHub Actions**.
2. Publish your packages' wheels/sdists as GitHub Release assets (see
   [`demo-release.yml`](.github/workflows/demo-release.yml) for a
   tag-triggered example).
3. Add a Pages workflow that runs the tool — the core of it:

   ```yaml
   - uses: astral-sh/setup-uv@v5
   - name: Build the package index
     env:
       GITHUB_TOKEN: ${{ github.token }}
     run: uvx gh-pages-pypi "$GITHUB_REPOSITORY" --out site
   - uses: actions/upload-pages-artifact@v3
     with:
       path: site
   ```

   See [`pages.yml`](.github/workflows/pages.yml) for the full workflow
   (triggers, permissions, deploy job). Note: releases created by workflows
   with `GITHUB_TOKEN` don't fire `release` events, so a release workflow
   must dispatch the Pages workflow explicitly (ours does).

Your index appears at `https://<owner>.github.io/<repo>/simple/`.

## The live demo

Two tiny packages live in [`packages/`](packages/):
[`demo-lib`](packages/demo-lib) (a one-function library) and
[`demo-app`](packages/demo-app) (depends on it, installs a `demo-app` CLI).
Install them from this repo's Pages index:

```sh
pip install --index-url https://bckohan.github.io/gh_pages_pypi/simple/ gh-pages-pypi-demo-app
demo-app
# Hello, world! (served from GitHub Pages)
```

Resolving `demo-app`'s dependency on `demo-lib` from the same index proves
dependency resolution works end to end.

Cut a new demo release (CalVer-bumps the package, tests, commits, tags,
pushes — the workflows do the rest):

```sh
just demo-release demo-lib
```

## Caveats

- **Prefer `--extra-index-url` over `--index-url`** if you still want
  pypi.org for everything else — but pip may consult *both* indexes, so a
  name squatted on pypi.org could shadow yours
  ([dependency confusion](https://medium.com/@alex.birsan/dependency-confusion-4a5d60fec610)).
  Use names that don't exist on pypi.org, or `--index-url` for your index
  only.
- Release assets on public repos are public; this is not a private index.
- The GitHub API returns at most 100 releases per page and the tool reads
  one page.
- This repo's own index also lists `gh-pages-pypi` itself: the PyPI
  release workflow attaches the tool's wheels to GitHub Releases, and the
  index builder indexes every non-draft release — deliberate dogfooding.

## Development

```bash
just setup      # create the uv venv + pre-commit hooks
just install    # sync all dependency groups
just test       # run the test suite
just check      # lint, format, types, package, docs
```

Cut a PyPI release by pushing a signed `v*` tag (see
[`release.yml`](.github/workflows/release.yml)).
