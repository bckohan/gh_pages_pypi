# GitHub Pages PyPI Demo Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers-extended-cc:subagent-driven-development (recommended) or superpowers-extended-cc:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A demo repository that serves a PEP 503 PyPI-compatible index from GitHub Pages, generated automatically from GitHub Release assets, with two example packages proving end-to-end installs.

**Architecture:** Two tiny packages live under `packages/` (`demo-app` depends on `demo-lib`). A tag-triggered workflow builds wheel+sdist and attaches them to a GitHub Release. A Pages workflow runs `scripts/build_index.py` (stdlib only) to turn the Releases API listing into `/simple/` PEP 503 HTML and deploys it with the official Pages actions.

**Tech Stack:** Python 3.11+ (tomllib in CI), setuptools build backend, `build`, `pytest`, GitHub Actions (`upload-pages-artifact`/`deploy-pages`).

**Spec:** `docs/superpowers/specs/2026-08-04-gh-pages-pypi-design.md`

**IMPORTANT — commits:** The repo owner's GPG signing requires an interactive passphrase and the owner has said they will commit everything themselves at the end. **Skip all `git commit` steps** — instead `git add` the task's files so the final staging area is complete. Do not run `git commit`.

---

## File Structure

```
gh_pages_pypi/
├── README.md                                    # Modify: full tutorial (Task 6)
├── packages/
│   ├── demo-lib/
│   │   ├── pyproject.toml                       # Task 1
│   │   ├── README.md                            # Task 1
│   │   └── src/gh_pages_pypi_demo_lib/__init__.py   # Task 1
│   └── demo-app/
│       ├── pyproject.toml                       # Task 2
│       ├── README.md                            # Task 2
│       └── src/gh_pages_pypi_demo_app/__init__.py   # Task 2
├── scripts/
│   └── build_index.py                           # Task 3
├── tests/
│   ├── test_packages.py                         # Tasks 1–2
│   └── test_build_index.py                      # Task 3
└── .github/workflows/
    ├── release.yml                              # Task 4
    └── pages.yml                                # Task 5
```

---

### Task 1: demo-lib package + dev environment

**Goal:** The `gh-pages-pypi-demo-lib` package exists, is installable, tested, and buildable; the repo has a working dev venv.

**Files:**
- Create: `packages/demo-lib/pyproject.toml`
- Create: `packages/demo-lib/README.md`
- Create: `packages/demo-lib/src/gh_pages_pypi_demo_lib/__init__.py`
- Test: `tests/test_packages.py`

**Acceptance Criteria:**
- [ ] `.venv` exists with `pytest`, `build`, `pyyaml` installed
- [ ] `greeting("PyPI")` returns `"Hello, PyPI! (served from GitHub Pages)"`
- [ ] `python -m build packages/demo-lib` produces a wheel and an sdist

**Verify:** `.venv/bin/python -m pytest tests/test_packages.py::test_greeting -v` → PASS

**Steps:**

- [ ] **Step 1: Create the dev venv**

```bash
python3 -m venv .venv
.venv/bin/pip install --quiet pytest build pyyaml
```

- [ ] **Step 2: Write the failing test**

Create `tests/test_packages.py`:

```python
from gh_pages_pypi_demo_lib import greeting


def test_greeting():
    assert greeting("PyPI") == "Hello, PyPI! (served from GitHub Pages)"
```

Run: `.venv/bin/python -m pytest tests/test_packages.py -v`
Expected: FAIL (ModuleNotFoundError: gh_pages_pypi_demo_lib)

- [ ] **Step 3: Create the package**

Create `packages/demo-lib/pyproject.toml`:

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "gh-pages-pypi-demo-lib"
version = "1.0.0"
description = "Tiny greeting library demonstrating GitHub Pages as a PyPI index"
readme = "README.md"
requires-python = ">=3.9"
license = { text = "CC0-1.0" }

[project.urls]
Repository = "https://github.com/bckohan/gh_pages_pypi"
```

Create `packages/demo-lib/README.md`:

```markdown
# gh-pages-pypi-demo-lib

A tiny greeting library. It exists to demonstrate installing packages from a
PyPI-compatible index hosted on GitHub Pages. See the
[repository README](https://github.com/bckohan/gh_pages_pypi) for the full demo.
```

Create `packages/demo-lib/src/gh_pages_pypi_demo_lib/__init__.py`:

```python
"""Tiny greeting library for the GitHub Pages PyPI demo."""

__version__ = "1.0.0"


def greeting(name):
    """Return a greeting proving this package was importable."""
    return f"Hello, {name}! (served from GitHub Pages)"
```

- [ ] **Step 4: Install editable and verify test passes**

```bash
.venv/bin/pip install --quiet -e packages/demo-lib
```

Run: `.venv/bin/python -m pytest tests/test_packages.py -v`
Expected: PASS (1 passed)

- [ ] **Step 5: Verify the package builds**

Run: `.venv/bin/python -m build packages/demo-lib && ls packages/demo-lib/dist/`
Expected: `gh_pages_pypi_demo_lib-1.0.0-py3-none-any.whl` and `gh_pages_pypi_demo_lib-1.0.0.tar.gz`

- [ ] **Step 6: Stage files (no commit — user commits at end)**

```bash
git add packages/demo-lib tests/test_packages.py
```

---

### Task 2: demo-app package (depends on demo-lib)

**Goal:** The `gh-pages-pypi-demo-app` package exists with a `demo-app` console script that uses `gh-pages-pypi-demo-lib`.

**Files:**
- Create: `packages/demo-app/pyproject.toml`
- Create: `packages/demo-app/README.md`
- Create: `packages/demo-app/src/gh_pages_pypi_demo_app/__init__.py`
- Modify (append): `tests/test_packages.py`

**Acceptance Criteria:**
- [ ] `main(["Pages"])` prints `Hello, Pages! (served from GitHub Pages)`
- [ ] `demo-app` console script is installed and runs
- [ ] `python -m build packages/demo-app` produces a wheel and an sdist

**Verify:** `.venv/bin/python -m pytest tests/test_packages.py -v` → 3 passed, and `.venv/bin/demo-app` prints the greeting

**Steps:**

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_packages.py`:

```python
from gh_pages_pypi_demo_app import main


def test_app_main_with_name(capsys):
    main(["Pages"])
    assert capsys.readouterr().out.strip() == "Hello, Pages! (served from GitHub Pages)"


def test_app_main_default(capsys):
    main([])
    assert capsys.readouterr().out.strip() == "Hello, world! (served from GitHub Pages)"
```

(Also move the new `from gh_pages_pypi_demo_app import main` import to the top of the file with the existing import.)

Run: `.venv/bin/python -m pytest tests/test_packages.py -v`
Expected: FAIL (ModuleNotFoundError: gh_pages_pypi_demo_app)

- [ ] **Step 2: Create the package**

Create `packages/demo-app/pyproject.toml`:

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "gh-pages-pypi-demo-app"
version = "1.0.0"
description = "Tiny CLI demonstrating dependency resolution from a GitHub Pages PyPI index"
readme = "README.md"
requires-python = ">=3.9"
license = { text = "CC0-1.0" }
dependencies = ["gh-pages-pypi-demo-lib>=1.0.0"]

[project.scripts]
demo-app = "gh_pages_pypi_demo_app:main"

[project.urls]
Repository = "https://github.com/bckohan/gh_pages_pypi"
```

Create `packages/demo-app/README.md`:

```markdown
# gh-pages-pypi-demo-app

A tiny CLI that depends on `gh-pages-pypi-demo-lib`. Installing it from the
GitHub Pages index proves the index resolves dependencies too. See the
[repository README](https://github.com/bckohan/gh_pages_pypi) for the full demo.
```

Create `packages/demo-app/src/gh_pages_pypi_demo_app/__init__.py`:

```python
"""Tiny CLI for the GitHub Pages PyPI demo."""

import sys

from gh_pages_pypi_demo_lib import greeting

__version__ = "1.0.0"


def main(argv=None):
    """Print a greeting for the first CLI argument (default: world)."""
    args = sys.argv[1:] if argv is None else argv
    print(greeting(args[0] if args else "world"))
```

- [ ] **Step 3: Install editable and verify tests pass**

```bash
.venv/bin/pip install --quiet -e packages/demo-app
```

Run: `.venv/bin/python -m pytest tests/test_packages.py -v`
Expected: PASS (3 passed)

Run: `.venv/bin/demo-app`
Expected: `Hello, world! (served from GitHub Pages)`

- [ ] **Step 4: Verify the package builds**

Run: `.venv/bin/python -m build packages/demo-app && ls packages/demo-app/dist/`
Expected: `gh_pages_pypi_demo_app-1.0.0-py3-none-any.whl` and `gh_pages_pypi_demo_app-1.0.0.tar.gz`

- [ ] **Step 5: Stage files**

```bash
git add packages/demo-app tests/test_packages.py
```

---

### Task 3: build_index.py — PEP 503 index generator

**Goal:** A stdlib-only script that turns GitHub release assets into a static PEP 503 index, unit-tested against fixture JSON.

**Files:**
- Create: `scripts/build_index.py`
- Test: `tests/test_build_index.py`

**Acceptance Criteria:**
- [ ] `normalize` implements PEP 503 normalization
- [ ] Wheel and sdist filenames map to project names; other assets are ignored
- [ ] Generated site has `/index.html`, `/simple/index.html`, `/simple/<project>/index.html` with `#sha256=` fragments
- [ ] Script exits non-zero with a clear message when no package assets exist

**Verify:** `.venv/bin/python -m pytest tests/test_build_index.py -v` → all pass

**Steps:**

- [ ] **Step 1: Write the failing tests**

Create `tests/test_build_index.py`:

```python
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import build_index

FIXTURE_RELEASES = [
    {
        "tag_name": "demo-lib-v1.0.0",
        "assets": [
            {
                "name": "gh_pages_pypi_demo_lib-1.0.0-py3-none-any.whl",
                "browser_download_url": "https://github.com/bckohan/gh_pages_pypi/releases/download/demo-lib-v1.0.0/gh_pages_pypi_demo_lib-1.0.0-py3-none-any.whl",
            },
            {
                "name": "gh_pages_pypi_demo_lib-1.0.0.tar.gz",
                "browser_download_url": "https://github.com/bckohan/gh_pages_pypi/releases/download/demo-lib-v1.0.0/gh_pages_pypi_demo_lib-1.0.0.tar.gz",
            },
            {
                "name": "release-notes.txt",
                "browser_download_url": "https://github.com/bckohan/gh_pages_pypi/releases/download/demo-lib-v1.0.0/release-notes.txt",
            },
        ],
    },
    {
        "tag_name": "demo-app-v1.0.0",
        "assets": [
            {
                "name": "gh_pages_pypi_demo_app-1.0.0-py3-none-any.whl",
                "browser_download_url": "https://github.com/bckohan/gh_pages_pypi/releases/download/demo-app-v1.0.0/gh_pages_pypi_demo_app-1.0.0-py3-none-any.whl",
            },
        ],
    },
    {
        "tag_name": "demo-lib-v2.0.0",
        "draft": True,
        "assets": [
            {
                "name": "gh_pages_pypi_demo_lib-2.0.0-py3-none-any.whl",
                "browser_download_url": "https://github.com/bckohan/gh_pages_pypi/releases/download/demo-lib-v2.0.0/gh_pages_pypi_demo_lib-2.0.0-py3-none-any.whl",
            },
        ],
    },
]


def fake_hash(url):
    return "cafef00d"


def test_normalize():
    assert build_index.normalize("Gh_Pages.PyPI--Demo") == "gh-pages-pypi-demo"


def test_project_name_from_filename():
    assert (
        build_index.project_name_from_filename("gh_pages_pypi_demo_lib-1.0.0-py3-none-any.whl")
        == "gh_pages_pypi_demo_lib"
    )
    assert (
        build_index.project_name_from_filename("gh_pages_pypi_demo_lib-1.0.0.tar.gz")
        == "gh_pages_pypi_demo_lib"
    )
    assert build_index.project_name_from_filename("release-notes.txt") is None


def test_collect_projects():
    projects = build_index.collect_projects(FIXTURE_RELEASES, hash_url=fake_hash)
    assert sorted(projects) == ["gh-pages-pypi-demo-app", "gh-pages-pypi-demo-lib"]
    lib_files = projects["gh-pages-pypi-demo-lib"]
    assert [f["filename"] for f in lib_files] == [
        "gh_pages_pypi_demo_lib-1.0.0-py3-none-any.whl",
        "gh_pages_pypi_demo_lib-1.0.0.tar.gz",
    ]
    assert all(f["sha256"] == "cafef00d" for f in lib_files)


def test_write_site(tmp_path):
    projects = build_index.collect_projects(FIXTURE_RELEASES, hash_url=fake_hash)
    build_index.write_site(projects, tmp_path, "bckohan/gh_pages_pypi")

    landing = (tmp_path / "index.html").read_text()
    assert "https://bckohan.github.io/gh_pages_pypi/simple/" in landing

    root = (tmp_path / "simple" / "index.html").read_text()
    assert '<a href="gh-pages-pypi-demo-lib/">' in root
    assert '<a href="gh-pages-pypi-demo-app/">' in root

    lib_page = (tmp_path / "simple" / "gh-pages-pypi-demo-lib" / "index.html").read_text()
    assert "#sha256=cafef00d" in lib_page
    assert "gh_pages_pypi_demo_lib-1.0.0-py3-none-any.whl</a>" in lib_page


def test_main_fails_with_no_packages(tmp_path, monkeypatch):
    monkeypatch.setattr(build_index, "fetch_releases", lambda repo, token: [])
    with pytest.raises(SystemExit) as excinfo:
        build_index.main(
            ["--repo", "bckohan/gh_pages_pypi", "--out", str(tmp_path), "--token", "x"]
        )
    assert "no package assets" in str(excinfo.value)
```

Run: `.venv/bin/python -m pytest tests/test_build_index.py -v`
Expected: FAIL (ModuleNotFoundError: build_index)

- [ ] **Step 2: Write the script**

Create `scripts/build_index.py`:

```python
#!/usr/bin/env python3
"""Generate a PEP 503 "simple" package index from GitHub release assets.

Lists every release in a GitHub repository, collects the ``.whl`` and
``.tar.gz`` assets, and writes a static PyPI-compatible index that GitHub
Pages can serve. Links point at the release assets' download URLs and carry
``#sha256=`` fragments so pip verifies every download.

Usage::

    build_index.py --repo OWNER/NAME --out DIR [--token TOKEN]

The token defaults to the ``GITHUB_TOKEN`` environment variable.
"""

import argparse
import hashlib
import html
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

API_ROOT = "https://api.github.com"

LANDING_PAGE = """<!DOCTYPE html>
<html>
  <head>
    <meta charset="utf-8">
    <title>{repo} package index</title>
  </head>
  <body>
    <h1>{repo} package index</h1>
    <p>A PyPI-compatible (PEP 503) package index served by GitHub Pages.
       Packages are hosted as GitHub release assets.</p>
    <p>Install packages with:</p>
    <pre>pip install --extra-index-url {index_url} PACKAGE</pre>
    <p>Available packages:</p>
    <ul>
{projects}
    </ul>
    <p><a href="simple/">Browse the simple index</a></p>
  </body>
</html>
"""

ROOT_PAGE = """<!DOCTYPE html>
<html>
  <head>
    <meta name="pypi:repository-version" content="1.0">
    <title>Simple index</title>
  </head>
  <body>
{anchors}
  </body>
</html>
"""

PROJECT_PAGE = """<!DOCTYPE html>
<html>
  <head>
    <meta name="pypi:repository-version" content="1.0">
    <title>Links for {project}</title>
  </head>
  <body>
    <h1>Links for {project}</h1>
{anchors}
  </body>
</html>
"""


def normalize(name):
    """Normalize a project name per PEP 503."""
    return re.sub(r"[-_.]+", "-", name).lower()


def project_name_from_filename(filename):
    """Return the project name for a wheel or sdist filename, else None."""
    if filename.endswith(".whl"):
        return filename.split("-")[0]
    if filename.endswith(".tar.gz"):
        return filename[: -len(".tar.gz")].rsplit("-", 1)[0]
    return None


def fetch_releases(repo, token):
    """Return the JSON list of releases for the ``owner/name`` repository."""
    request = urllib.request.Request(
        f"{API_ROOT}/repos/{repo}/releases?per_page=100",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
        },
    )
    with urllib.request.urlopen(request) as response:
        return json.load(response)


def hash_url(url):
    """Download ``url`` and return the sha256 hex digest of its content."""
    digest = hashlib.sha256()
    with urllib.request.urlopen(url) as response:
        for chunk in iter(lambda: response.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def collect_projects(releases, hash_url=hash_url):
    """Map normalized project names to their release files.

    Returns ``{project: [{"filename", "url", "sha256"}, ...]}`` sorted by
    project name and filename. Assets that are not wheels or sdists are
    ignored.
    """
    projects = {}
    for release in releases:
        if release.get("draft"):  # draft assets aren't publicly downloadable
            continue
        for asset in release.get("assets", []):
            project = project_name_from_filename(asset["name"])
            if project is None:
                continue
            projects.setdefault(normalize(project), []).append(
                {
                    "filename": asset["name"],
                    "url": asset["browser_download_url"],
                    "sha256": hash_url(asset["browser_download_url"]),
                }
            )
    for files in projects.values():
        files.sort(key=lambda file: file["filename"])
    return dict(sorted(projects.items()))


def pages_url(repo):
    """Return the GitHub Pages base URL for the ``owner/name`` repository."""
    owner, name = repo.split("/", 1)
    return f"https://{owner.lower()}.github.io/{name}/"


def write_site(projects, out_dir, repo):
    """Write the landing page and PEP 503 simple index under ``out_dir``."""
    simple = out_dir / "simple"
    for project, files in projects.items():
        anchors = "\n".join(
            '    <a href="{url}#sha256={sha}">{filename}</a><br/>'.format(
                url=html.escape(file["url"]),
                sha=file["sha256"],
                filename=html.escape(file["filename"]),
            )
            for file in files
        )
        project_dir = simple / project
        project_dir.mkdir(parents=True, exist_ok=True)
        (project_dir / "index.html").write_text(
            PROJECT_PAGE.format(project=html.escape(project), anchors=anchors)
        )
    root_anchors = "\n".join(
        f'    <a href="{project}/">{project}</a><br/>' for project in projects
    )
    (simple / "index.html").write_text(ROOT_PAGE.format(anchors=root_anchors))
    project_items = "\n".join(
        f"      <li><code>{project}</code></li>" for project in projects
    )
    (out_dir / "index.html").write_text(
        LANDING_PAGE.format(
            repo=html.escape(repo),
            index_url=pages_url(repo) + "simple/",
            projects=project_items,
        )
    )


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Generate a PEP 503 index from GitHub release assets."
    )
    parser.add_argument("--repo", required=True, help="repository as owner/name")
    parser.add_argument("--out", required=True, help="output directory")
    parser.add_argument(
        "--token",
        default=os.environ.get("GITHUB_TOKEN"),
        help="GitHub API token (defaults to $GITHUB_TOKEN)",
    )
    args = parser.parse_args(argv)
    if not args.token:
        sys.exit("error: provide --token or set GITHUB_TOKEN")

    try:
        releases = fetch_releases(args.repo, args.token)
    except urllib.error.URLError as error:
        sys.exit(f"error: GitHub API request for {args.repo} failed: {error}")
    projects = collect_projects(releases)
    if not projects:
        sys.exit(
            f"error: no package assets found in releases of {args.repo}; "
            "refusing to build an empty index"
        )
    write_site(projects, Path(args.out), args.repo)
    print(f"wrote index for {len(projects)} project(s) to {args.out}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Verify tests pass**

Run: `.venv/bin/python -m pytest tests/test_build_index.py -v`
Expected: PASS (5 passed)

- [ ] **Step 4: Stage files**

```bash
git add scripts/build_index.py tests/test_build_index.py
```

---

### Task 4: release.yml — tag-triggered package releases

**Goal:** Pushing a tag like `demo-lib-v1.0.0` builds that package and publishes a GitHub Release with wheel + sdist attached.

**Files:**
- Create: `.github/workflows/release.yml`

**Acceptance Criteria:**
- [ ] Triggers on tags matching `demo-*-v*`
- [ ] Fails on unknown package directory or tag/pyproject version mismatch
- [ ] Creates a release with both artifacts, then dispatches the pages workflow

**Verify:** `.venv/bin/python -c "import yaml, pathlib; yaml.safe_load(pathlib.Path('.github/workflows/release.yml').read_text()); print('OK')"` → `OK`

**Steps:**

- [ ] **Step 1: Write the workflow**

Create `.github/workflows/release.yml`:

```yaml
# Builds a package and publishes it as a GitHub Release when a tag like
# demo-lib-v1.0.0 or demo-app-v1.2.3 is pushed. The release assets become
# the package files served by the GitHub Pages index.
name: release

on:
  push:
    tags:
      - "demo-*-v*"

permissions:
  contents: write
  actions: write # to dispatch the pages workflow

jobs:
  release:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Parse tag into package and version
        id: parse
        run: |
          PACKAGE="${GITHUB_REF_NAME%-v*}"
          VERSION="${GITHUB_REF_NAME##*-v}"
          if [ ! -d "packages/${PACKAGE}" ]; then
            echo "::error::unknown package '${PACKAGE}' (no packages/${PACKAGE} directory)"
            exit 1
          fi
          echo "package=${PACKAGE}" >> "$GITHUB_OUTPUT"
          echo "version=${VERSION}" >> "$GITHUB_OUTPUT"

      - name: Verify tag version matches pyproject.toml
        env:
          PACKAGE: ${{ steps.parse.outputs.package }}
          VERSION: ${{ steps.parse.outputs.version }}
        run: |
          python - <<'EOF'
          import os, sys, tomllib
          from pathlib import Path

          package, version = os.environ["PACKAGE"], os.environ["VERSION"]
          pyproject = Path("packages") / package / "pyproject.toml"
          actual = tomllib.loads(pyproject.read_text())["project"]["version"]
          if actual != version:
              sys.exit(f"tag version {version} != {pyproject} version {actual}")
          EOF

      # Tag-derived values always flow through env vars, never ${{ }} inside
      # `run:` — interpolating them into shell text is the classic Actions
      # injection pitfall.
      - name: Build wheel and sdist
        env:
          PACKAGE: ${{ steps.parse.outputs.package }}
        run: |
          pip install build
          python -m build "packages/${PACKAGE}"

      - name: Create GitHub Release with artifacts
        env:
          GH_TOKEN: ${{ github.token }}
          PACKAGE: ${{ steps.parse.outputs.package }}
          VERSION: ${{ steps.parse.outputs.version }}
        run: |
          gh release create "$GITHUB_REF_NAME" \
            packages/"${PACKAGE}"/dist/* \
            --title "$GITHUB_REF_NAME" \
            --notes "Release ${VERSION} of ${PACKAGE}"

      # Releases created with GITHUB_TOKEN do not fire `release` events in
      # other workflows (GitHub suppresses them to prevent recursion), so
      # trigger the Pages rebuild explicitly.
      - name: Rebuild the Pages index
        env:
          GH_TOKEN: ${{ github.token }}
        run: gh workflow run pages.yml
```

- [ ] **Step 2: Verify YAML parses**

Run: `.venv/bin/python -c "import yaml, pathlib; yaml.safe_load(pathlib.Path('.github/workflows/release.yml').read_text()); print('OK')"`
Expected: `OK`

- [ ] **Step 3: Stage files**

```bash
git add .github/workflows/release.yml
```

---

### Task 5: pages.yml — index build + Pages deployment

**Goal:** A workflow that regenerates the PEP 503 index from release assets and deploys it to GitHub Pages.

**Files:**
- Create: `.github/workflows/pages.yml`

**Acceptance Criteria:**
- [ ] Triggers on `release` published/deleted, push to `main`, and `workflow_dispatch`
- [ ] Runs `scripts/build_index.py` with `GITHUB_TOKEN` into `site/`
- [ ] Deploys via `actions/upload-pages-artifact` + `actions/deploy-pages`

**Verify:** `.venv/bin/python -c "import yaml, pathlib; yaml.safe_load(pathlib.Path('.github/workflows/pages.yml').read_text()); print('OK')"` → `OK`

**Steps:**

- [ ] **Step 1: Write the workflow**

Create `.github/workflows/pages.yml`:

```yaml
# Regenerates the PEP 503 package index from GitHub release assets and
# deploys it to GitHub Pages. Runs on releases (created or deleted by hand),
# on any push to main (e.g. to pick up index script changes), on manual
# dispatch, and is triggered explicitly by release.yml (releases created
# with GITHUB_TOKEN do not fire `release` events).
#
# NOTE: this fails by design while the repository has no releases yet —
# build_index.py refuses to deploy an empty index.
name: pages

on:
  release:
    types: [published, deleted]
  push:
    branches: [main]
  workflow_dispatch:

permissions:
  contents: read
  pages: write
  id-token: write

# Latest-wins: a newer index build supersedes an in-flight one. (GitHub's
# Pages starter uses cancel-in-progress: false to protect production
# deploys; for an index rebuilt from scratch each run, newest data wins.)
concurrency:
  group: pages
  cancel-in-progress: true

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Build the package index
        env:
          GITHUB_TOKEN: ${{ github.token }}
        run: python scripts/build_index.py --repo "$GITHUB_REPOSITORY" --out site

      # Fails fast with a clear error if Pages isn't enabled for this repo.
      - uses: actions/configure-pages@v5

      - uses: actions/upload-pages-artifact@v3
        with:
          path: site

  deploy:
    needs: build
    runs-on: ubuntu-latest
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    steps:
      - id: deployment
        uses: actions/deploy-pages@v4
```

- [ ] **Step 2: Verify YAML parses**

Run: `.venv/bin/python -c "import yaml, pathlib; yaml.safe_load(pathlib.Path('.github/workflows/pages.yml').read_text()); print('OK')"`
Expected: `OK`

- [ ] **Step 3: Stage files**

```bash
git add .github/workflows/pages.yml
```

---

### Task 6: README tutorial + full local verification

**Goal:** The README explains the whole demo — how it works, how to set it up, how to release, how to install — and the complete test suite passes.

**Files:**
- Modify: `README.md`

**Acceptance Criteria:**
- [ ] README covers: how it works, repo layout, releasing a package, installing from the index, enabling Pages, and caveats (dependency confusion / `--extra-index-url` vs `--index-url`)
- [ ] Full test suite passes

**Verify:** `.venv/bin/python -m pytest tests/ -v` → all pass (8 passed)

**Steps:**

- [ ] **Step 1: Rewrite `README.md`**

Replace `README.md` with:

````markdown
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
````

- [ ] **Step 2: Verify the full suite passes**

Run: `.venv/bin/python -m pytest tests/ -v`
Expected: PASS (8 passed)

- [ ] **Step 3: Stage files**

```bash
git add README.md
```

---

## Post-implementation (user actions)

These require the owner's credentials and happen after the final commit:

1. Commit everything (owner does this — GPG passphrase required).
2. `git push origin main`.
3. Settings → Pages → Source: **GitHub Actions**.
4. `git tag demo-lib-v1.0.0 && git tag demo-app-v1.0.0 && git push origin --tags`
5. Verify: `pip install --extra-index-url https://bckohan.github.io/gh_pages_pypi/simple/ gh-pages-pypi-demo-app && demo-app`
