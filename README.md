# gh_pages_pypi

A demo of how to use **GitHub Pages as a PyPI-compatible package index**,
with package files hosted as **GitHub Release assets**. Nothing is
published to pypi.org and no index server runs anywhere — it's all static
HTML, rebuilt automatically on every release.

## Try it

```sh
pip install --extra-index-url https://bckohan.github.io/gh_pages_pypi/simple/ gh-pages-pypi-demo-app
demo-app
# Hello, world! (served from GitHub Pages)
```

Installing `gh-pages-pypi-demo-app` also pulls its dependency
`gh-pages-pypi-demo-lib` from the same index — proving dependency
resolution works.

## How it works

pip doesn't need a server to install packages — just a static HTML index in
the [PEP 503 "simple repository"](https://peps.python.org/pep-0503/) format:

```
/simple/                          → lists every project
/simple/<project>/                → lists every file, linking to downloads
```

This repo wires that together with three pieces:

1. **`packages/`** — two tiny example packages.
   [`demo-lib`](packages/demo-lib) is a one-function library;
   [`demo-app`](packages/demo-app) depends on it and installs a `demo-app`
   CLI.
2. **[`release.yml`](.github/workflows/release.yml)** — pushing a tag like
   `demo-lib-v1.0.0` builds that package's wheel + sdist and attaches them
   to a GitHub Release.
3. **[`pages.yml`](.github/workflows/pages.yml)** — runs
   [`scripts/build_index.py`](scripts/build_index.py), which asks the
   GitHub API for every release asset, computes each file's `sha256`, and
   writes the PEP 503 HTML linking straight to the release download URLs.
   The result deploys to GitHub Pages. No generated file is ever committed.

## Releasing a package

1. Bump `version` in `packages/<pkg>/pyproject.toml`.
2. Commit, then tag and push:

   ```sh
   git tag demo-lib-v1.0.1
   git push origin demo-lib-v1.0.1
   ```

That's it. The release workflow builds and publishes the artifacts, then
triggers the Pages workflow to rebuild the index.

## Setting this up for your own repo

1. Copy `scripts/build_index.py` and both workflows.
2. In repo **Settings → Pages**, set **Source** to **GitHub Actions**.
3. Put your packages somewhere `release.yml` can find them (this repo uses
   `packages/<name>/`, tagged as `<name>-v<version>` — adjust the tag
   pattern in `release.yml`'s `on.push.tags` to match your names).
4. Push a tag. Your index appears at
   `https://<owner>.github.io/<repo>/simple/`.

Until the first release exists, the pages workflow fails on purpose —
`build_index.py` refuses to deploy an empty index.

## Caveats

- **Prefer `--extra-index-url` over `--index-url`** if you still want
  pypi.org for everything else — but be aware pip may consult *both*
  indexes, so a name squatted on pypi.org could shadow yours
  ([dependency confusion](https://medium.com/@alex.birsan/dependency-confusion-4a5d60fec610)).
  Give your packages names that don't exist on pypi.org (like the
  deliberately obscure names here), or use `--index-url` to use *only*
  your index.
- Release assets on public repos are public; this scheme does not provide
  a private index unless the repo (and thus asset downloads) are private —
  in which case plain `pip` can't fetch them without auth anyway.
- GitHub's API paginates releases at 100 per page; `build_index.py` reads
  one page, which is plenty for a demo.

## Development

```sh
python3 -m venv .venv
.venv/bin/pip install pytest build pyyaml
.venv/bin/pip install -e packages/demo-lib -e packages/demo-app
.venv/bin/python -m pytest tests/ -v
```
