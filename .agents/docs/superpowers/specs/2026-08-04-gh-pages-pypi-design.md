# Design: GitHub Pages as a PyPI Repository (Demo)

**Date:** 2026-08-04
**Status:** Approved

## Goal

A demo repository showing how to serve a PEP 503 ("simple") PyPI-compatible
index from GitHub Pages, with package artifacts hosted as GitHub Release
assets. The index is generated automatically — no manual intervention after
a release is published. Two example packages prove the index works,
including dependency resolution between packages on the same index.

## Repository Layout

```
gh_pages_pypi/
├── README.md                    # the tutorial — how it works, how to use it
├── packages/
│   ├── demo-lib/                # gh-pages-pypi-demo-lib
│   │   ├── pyproject.toml
│   │   └── src/gh_pages_pypi_demo_lib/__init__.py
│   └── demo-app/                # gh-pages-pypi-demo-app (depends on demo-lib)
│       ├── pyproject.toml
│       └── src/gh_pages_pypi_demo_app/__init__.py
├── scripts/
│   └── build_index.py           # PEP 503 index generator (stdlib only)
└── .github/workflows/
    ├── release.yml              # builds + publishes a package release
    └── pages.yml                # rebuilds the index + deploys Pages
```

## Example Packages

- **gh-pages-pypi-demo-lib** — exposes one tiny function (a greeting
  formatter). No dependencies.
- **gh-pages-pypi-demo-app** — depends on `gh-pages-pypi-demo-lib`.
  Installs a `demo-app` console script that calls the lib function.
  `pip install gh-pages-pypi-demo-app` followed by running `demo-app`
  proves both packages and dependency resolution work end to end.

Both use `pyproject.toml` with a modern build backend (setuptools),
`src/` layout, Python >= 3.9.

## Release Flow (`release.yml`)

- **Trigger:** push of a tag matching `<package>-v<version>`, e.g.
  `demo-lib-v1.0.0`, `demo-app-v0.2.1`.
- **Steps:**
  1. Parse the tag into package directory + version; fail if the package
     directory does not exist under `packages/`.
  2. Verify the tag version matches the `version` in that package's
     `pyproject.toml`; fail on mismatch.
  3. Build wheel + sdist with `python -m build`.
  4. Create a GitHub Release for the tag with both artifacts attached
     (`gh release create`).
- **Permissions:** `contents: write` only.

## Index Flow (`pages.yml`)

- **Triggers:** `release: [published, deleted]`, `push` to `main`, and
  `workflow_dispatch`.
- **Generator:** `scripts/build_index.py`, Python stdlib only (`urllib`,
  `json`, `hashlib`, `html`). Uses `GITHUB_TOKEN` to call the GitHub
  Releases API for the repository:
  1. List all releases and their assets; keep `.whl` and `.tar.gz` files.
  2. Derive the PEP 503-normalized project name from each filename.
  3. Download each asset and compute its `sha256` (few small files —
     cheap; no coordination with the release workflow needed).
  4. Write the site:
     - `/index.html` — human landing page with pip instructions
     - `/simple/index.html` — root index of projects
     - `/simple/<project>/index.html` — anchor per file pointing at the
       release-asset `browser_download_url`, with `#sha256=...` fragment
- **Deploy:** official `actions/upload-pages-artifact` +
  `actions/deploy-pages`. Permissions: `pages: write`, `id-token: write`.
  No generated files are committed to git.

## Error Handling

- `build_index.py` exits non-zero (failing the workflow) on GitHub API
  errors or when zero releases are found, with a clear message — it never
  deploys an empty index silently.
- Non-package assets attached to releases are ignored.
- `release.yml` fails on unknown package names or tag/`pyproject.toml`
  version mismatches.

## Verification

- **Local:** build both packages with `python -m build`; smoke-test
  `build_index.py` against fixture JSON of fake releases and inspect the
  generated HTML.
- **Live (after enabling Pages and tagging both packages):**

  ```sh
  pip install --index-url https://bckohan.github.io/gh_pages_pypi/simple/ gh-pages-pypi-demo-app
  demo-app
  ```

  This must resolve and install both packages from the Pages index and
  print the lib-generated greeting.

## Out of Scope

- Uploading via `twine` / PyPI upload API (Pages is read-only hosting).
- PEP 691 JSON index (HTML index is sufficient for pip).
- Package signing / attestations.
