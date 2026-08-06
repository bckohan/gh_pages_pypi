# github-releases-pypi
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![PyPI version](https://badge.fury.io/py/github-releases-pypi.svg)](https://pypi.python.org/pypi/github-releases-pypi/)
[![PyPI pyversions](https://img.shields.io/pypi/pyversions/github-releases-pypi.svg)](https://pypi.python.org/pypi/github-releases-pypi/)
[![PyPI status](https://img.shields.io/pypi/status/github-releases-pypi.svg)](https://pypi.python.org/pypi/github-releases-pypi)
[![Documentation Status](https://readthedocs.org/projects/github-releases-pypi/badge/?version=latest)](http://github-releases-pypi.readthedocs.io/?badge=latest/)
[![Code Cov](https://codecov.io/gh/bckohan/github-releases-pypi/branch/main/graph/badge.svg)](https://codecov.io/gh/bckohan/github-releases-pypi)
[![Test Status](https://github.com/bckohan/github-releases-pypi/actions/workflows/test.yml/badge.svg?branch=main)](https://github.com/bckohan/github-releases-pypi/actions/workflows/test.yml?query=branch:main)
[![Lint Status](https://github.com/bckohan/github-releases-pypi/actions/workflows/lint.yml/badge.svg?branch=main)](https://github.com/bckohan/github-releases-pypi/actions/workflows/lint.yml?query=branch:main)

Serve a **PyPI-compatible package index from GitHub Pages**, built from
**GitHub release assets**. No index server, nothing published to pypi.org —
just static PEP 503 HTML, rebuilt automatically on every release.

This repository is both the tool and its own demo: the index at
[bckohan.github.io/github-releases-pypi](https://bckohan.github.io/github-releases-pypi/)
is built by this tool from this repo's releases.

## Installation

```bash
pip install github-releases-pypi
# or run it without installing:
uvx github-releases-pypi --help
```

## Usage

```bash
github-releases-pypi OWNER/REPO --out site [--token TOKEN]
```

Reads every (non-draft) release of `OWNER/REPO` via the GitHub API
(`--token` defaults to `$GITHUB_TOKEN`), collects the wheel/sdist assets,
takes each file's `sha256` from the API's asset digest (downloading and
hashing only files that lack one), and writes a static
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
2. Publish your packages' wheels/sdists as GitHub Release assets (see the
   `github-release` job in [`release.yml`](.github/workflows/release.yml)
   for a tag-triggered example).
3. Add a Pages workflow that runs the tool — the core of it:

   ```yaml
   - uses: astral-sh/setup-uv@v5
   - name: Build the package index
     env:
       GITHUB_TOKEN: ${{ github.token }}
     run: uvx github-releases-pypi "$GITHUB_REPOSITORY" --out site
   - uses: actions/upload-pages-artifact@v3
     with:
       path: site
   ```

   See [`pages.yml`](.github/workflows/pages.yml) for the full workflow
   (triggers, permissions, deploy job). Note: releases created by workflows
   with `GITHUB_TOKEN` don't fire `release` events, so a release workflow
   must dispatch the Pages workflow explicitly (ours does).

Your index appears at `https://<owner>.github.io/<repo>/simple/`.

## Aggregating multiple repositories

To serve one index built from several repositories' releases, pass a YAML
config instead of a repository:

```yaml
# index.yml
repositories:
  - yourorg/lib-one
  - yourorg/lib-two
title: yourorg package index            # optional
url: https://yourorg.github.io/pypi/    # optional — enables the absolute
                                        # --extra-index-url example on the
                                        # landing page
missing_digest: download                # optional — see below
```

```sh
github-releases-pypi --config index.yml --out site
```

Any wheel or sdist attached to any (non-draft) release on any configured
repository is included. If two repositories publish the same filename, the
first repository in the list wins and a warning is printed.

GitHub's API supplies a sha256 digest for release assets uploaded since
mid-2025, which the builder uses directly — those files are never
downloaded. `missing_digest` controls what happens to older assets that
lack a digest:

| value | behavior |
| --- | --- |
| `download` (default) | download and hash the file |
| `no-fragment` | link it without a `#sha256=` fragment (pip skips integrity verification) |
| `omit` | leave it out of the index, with a warning |

Duplicate filenames are resolved before the policy applies, so if the first
repository's copy lacks a digest, a later copy's digest is not consulted.

## Customizing templates

Add a `templates:` directory to the config (resolved relative to the config
file) to override the built-in pages:

```yaml
templates: ./templates
```

A file named `landing.html`, `project.html`, or `simple_root.html` in that
directory replaces the built-in template wholesale. To change just part of a
page, extend the built-in under the `builtin/` prefix and override blocks:

```html
{% extends "builtin/landing.html" %}
{% block footer %}<footer>© yourorg</footer>{% endblock %}
```

Always extend via the `builtin/` prefix — an override that does
`{% extends "landing.html" %}` resolves to itself and fails with a recursion
error.

`landing.html` and `project.html` define blocks `title`, `head`, `header`,
`content`, and `footer`. `simple_root.html` defines only `head` — its body is
the PEP 503 anchor list that pip parses, so extend it with care.

If you replace `project.html` wholesale, guard the hash fragment with
`{% if file.sha256 %}` as the built-in does — with `missing_digest:
no-fragment`, `file.sha256` can be `None`, and an unconditional
`#sha256={{ file.sha256 }}` renders a link pip will refuse to verify.

## The live demo

Two tiny packages live in [`packages/`](packages/):
[`demo-lib`](packages/demo-lib) (a one-function library) and
[`demo-app`](packages/demo-app) (depends on it, installs a `demo-app` CLI).
Install them from this repo's Pages index:

```sh
pip install --index-url https://bckohan.github.io/github-releases-pypi/simple/ github-releases-pypi-demo-app
demo-app
# Hello, world! (served from GitHub Pages)
```

Resolving `demo-app`'s dependency on `demo-lib` from the same index proves
dependency resolution works end to end.

Cut a new release (CalVer-stamps every package — the tool and both demos —
runs the full check suite, tests, commits, tags, pushes; the workflows do the
rest):

```sh
just release
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
- This repo's own index also lists `github-releases-pypi` itself: the PyPI
  release workflow attaches the tool's wheels to GitHub Releases, and the
  index builder indexes every non-draft release — deliberate dogfooding.

## Development

```bash
just setup      # create the uv venv + pre-commit hooks
just install    # sync all dependency groups
just test       # run the test suite
just check      # lint, format, types, package, docs
```

Cut a release with `just release` — it pushes a signed `v*` tag that triggers
[`release.yml`](.github/workflows/release.yml).
