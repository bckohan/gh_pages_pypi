# ghr-pypi
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![PyPI version](https://badge.fury.io/py/ghr-pypi.svg)](https://pypi.python.org/pypi/ghr-pypi/)
[![PyPI pyversions](https://img.shields.io/pypi/pyversions/ghr-pypi.svg)](https://pypi.python.org/pypi/ghr-pypi/)
[![PyPI status](https://img.shields.io/pypi/status/ghr-pypi.svg)](https://pypi.python.org/pypi/ghr-pypi)
[![Documentation Status](https://readthedocs.org/projects/ghr-pypi/badge/?version=latest)](http://ghr-pypi.readthedocs.io/?badge=latest/)
[![Code Cov](https://codecov.io/gh/bckohan/ghr-pypi/branch/main/graph/badge.svg)](https://codecov.io/gh/bckohan/ghr-pypi)
[![Test Status](https://github.com/bckohan/ghr-pypi/actions/workflows/test.yml/badge.svg?branch=main)](https://github.com/bckohan/ghr-pypi/actions/workflows/test.yml?query=branch:main)
[![Lint Status](https://github.com/bckohan/ghr-pypi/actions/workflows/lint.yml/badge.svg?branch=main)](https://github.com/bckohan/ghr-pypi/actions/workflows/lint.yml?query=branch:main)

**Documentation:** [ghr-pypi.readthedocs.io](https://ghr-pypi.readthedocs.io) — deployment
tutorials, how-to guides, and the full configuration and CLI reference.

<!-- docs-index-start -->

**Tools for creating Python package indexes from GitHub release assets.** No
index server, nothing published to pypi.org — just static PEP 503 HTML and
PEP 691 JSON, servable from GitHub Pages, a CDN or your own webserver, and
rebuilt automatically on every release.

This repository is both the tool and its own demo: the index at
[bckohan.github.io/ghr-pypi](https://bckohan.github.io/ghr-pypi/)
is built by this tool from this repo's releases.

## Installation

```bash
pip install ghr-pypi
# or run it without installing:
uvx ghr-pypi --help
```

## Usage

```bash
ghr-pypi OWNER/REPO --out site [--token TOKEN]
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
site/simple/**/index.json         → PEP 691 JSON Simple API (see below)
```

It refuses to build an empty index (non-zero exit) so a misconfigured CI run
can never deploy a blank package index.

## Using it in your own repo

1. In repo **Settings → Pages**, set **Source** to **GitHub Actions**.
2. Publish your packages' wheels/sdists as GitHub Release assets (see the
   `github-release` job in [`release.yml`](https://github.com/bckohan/ghr-pypi/blob/main/.github/workflows/release.yml)
   for a tag-triggered example).
3. Add a Pages workflow that runs the tool — the core of it:

   ```yaml
   - uses: astral-sh/setup-uv@v5
   - name: Build the package index
     env:
       GITHUB_TOKEN: ${{ github.token }}
     run: uvx ghr-pypi "$GITHUB_REPOSITORY" --out site
   - uses: actions/upload-pages-artifact@v3
     with:
       path: site
   ```

   See [`pages.yml`](https://github.com/bckohan/ghr-pypi/blob/main/.github/workflows/pages.yml) for the full workflow
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
formats: [html, json]                   # optional — default: both
mirror: false                           # optional — see "Mirroring assets"
metadata: true                          # optional — see "Dependency metadata"

yanked:                                 # optional — PEP 592 yanks, keyed by
  yourpkg:                              #   project then (quoted) version
    "1.0.1": broken sdist, use 1.0.2    #   reason string, or `true`
exclude:                                # optional — versions dropped from the
  yourpkg:                              #   index entirely
    - "0.0.1"                           #   see below
```

```sh
ghr-pypi --config index.yml --out site
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

## JSON Simple API

With `json` in `formats` (the default), the builder also writes a
[PEP 691](https://peps.python.org/pep-0691/) JSON index — `simple/index.json`
and `simple/<project>/index.json`, api-version 1.1 with
[PEP 700](https://peps.python.org/pep-0700/) `versions`, `size`, and
`upload-time` fields (uv's `--exclude-newer` uses `upload-time`).

On a full webserver you can serve the JSON at the canonical URLs via
`Accept`-header content negotiation (`application/vnd.pypi.simple.v1+json`);
on static hosts the files sit alongside the HTML. The JSON shape is
spec-defined and is NOT affected by template overrides.

`formats: [json]` emits a JSON-only, headless index (no landing page);
`formats: [html]` reproduces today's HTML-only output.

## Mirroring assets

With `mirror: true` (or `--mirror` on the single-repository form), the
builder downloads every asset into `site/files/<project>/` and the index
links to those local copies with relative URLs — the site is fully
self-contained and relocatable, and GitHub is out of the serving path.

This is also the way to index **private repositories**: downloads go
through GitHub's authenticated asset API using your `--token`, and the
resulting site can be served behind whatever auth your host provides
(pip and uv understand basic auth and netrc). Direct links to a private
repo's assets would not be fetchable by pip.

```sh
ghr-pypi yourorg/private-repo --out site --token $TOKEN --mirror
```

When the mirrored site will be hosted somewhere other than GitHub Pages,
prefer a config file with `mirror: true` and set `url` to the real host (or
omit it) — the single-repository form assumes a Pages URL for the landing
page's install example.

Every mirrored file is hashed while downloading; when GitHub's API
advertises a digest it is verified and a mismatch fails the build
(downloads are staged to a temporary file, so a failed or interrupted
build never corrupts previously mirrored files). The
`missing_digest` option does not apply (and is rejected) under mirroring —
every file gets a real hash. Files already present in `site/files/` with
the right hash are not re-downloaded, so repeat builds only fetch new
assets. In GitHub Actions, persist them between runs:

```yaml
- uses: actions/cache@v4
  with:
    path: site/files
    key: mirrored-assets-${{ github.run_id }}
    restore-keys: mirrored-assets-
```

Note: files removed from releases (and their extracted `.metadata`
siblings) are not pruned from `site/files/` — clear the directory (or the
cache) to drop them.

## Dependency metadata (PEP 658)

Resolvers can read a wheel's dependencies without downloading the wheel
when the index serves its core metadata
([PEP 658](https://peps.python.org/pep-0658/)/[714](https://peps.python.org/pep-0714/)) —
uv in particular resolves dramatically faster against large indexes.

- **Mirror mode:** metadata is extracted from every mirrored wheel
  automatically and served as `<filename>.metadata` beside it — no
  configuration needed.
- **Link mode:** the index can only advertise metadata files that live
  next to the wheel's own URL, so they must be uploaded as release assets
  named `<wheel-filename>.metadata`. The builder warns per repository when
  wheels lack them:

      warning: yourorg/lib-one: 3 of 4 wheels have no .metadata asset; ...

  To publish metadata assets from your release workflow, extract each
  wheel's `METADATA` and upload it next to the wheel (see the
  "Extract PEP 658 metadata from wheels" step in
  [`release.yml`](https://github.com/bckohan/ghr-pypi/blob/main/.github/workflows/release.yml) for the full version):

      - name: Extract PEP 658 metadata
        run: |
          python3 -c "
          import pathlib, zipfile
          for w in pathlib.Path('dist').glob('*.whl'):
              m = [n for n in zipfile.ZipFile(w).namelist()
                   if n.endswith('.dist-info/METADATA') and n.count('/') == 1]
              w.with_name(w.name + '.metadata').write_bytes(
                  zipfile.ZipFile(w).read(m[0]))
          "
      - run: gh release upload "$GITHUB_REF_NAME" dist/*.whl.metadata

Set `metadata: false` to disable extraction, advertising, and warnings.
If you replace `project.html` wholesale, copy the built-in's
`data-core-metadata` handling to keep advertising metadata.

## Yanking and excluding releases

A bad release does not have to be deleted. `yanked` marks it
[PEP 592](https://peps.python.org/pep-0592/) yanked: the file stays in the
index (and in the PEP 700 `versions` list, and in the mirror) carrying a
`data-yanked` attribute and a `"yanked"` JSON key, so pip and uv stop
selecting it — but still install it, and print your reason, when a
requirement pins that exact version. Existing pinned installs keep working.

`exclude` is the harder edge: the listed versions never enter the index at
all — no link, no JSON entry, no `versions` entry, nothing mirrored — and
anything pinned to them stops resolving. Use it when the release must not be
installable by anyone.

```yaml
yanked:
  yourpkg:
    "1.0.1": broken sdist, use 1.0.2   # or `true` for no reason
exclude:
  yourpkg:
    - "0.0.1"
```

Both are keyed by project (PEP 503-normalized) then version, and versions
match by PEP 440 equivalence, so `"1.0"` matches a `1.0.0` file — but
`"1.0.0"` does *not* match `1.0.0+local`; write local versions out in full.
Neither key touches GitHub: removing the entry restores the files on the
next build. If you replace `project.html` wholesale, copy the built-in's
`data-yanked` conditional too, or yanked files will be published as if they
were fine.

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

Two tiny packages live in [`packages/`](https://github.com/bckohan/ghr-pypi/tree/main/packages):
[`demo-lib`](https://github.com/bckohan/ghr-pypi/tree/main/packages/demo-lib) (a one-function library) and
[`demo-app`](https://github.com/bckohan/ghr-pypi/tree/main/packages/demo-app) (depends on it, installs a `demo-app` CLI).
Install them from this repo's Pages index:

```sh
pip install --index-url https://bckohan.github.io/ghr-pypi/simple/ ghr-pypi-demo-app
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
- This repo's own index also lists `ghr-pypi` itself: the PyPI
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
[`release.yml`](https://github.com/bckohan/ghr-pypi/blob/main/.github/workflows/release.yml).

<!-- docs-index-end -->
