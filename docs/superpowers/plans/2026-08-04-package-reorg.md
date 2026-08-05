# Package Reorg Implementation Plan (gh-pages-pypi)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers-extended-cc:subagent-driven-development (recommended) or superpowers-extended-cc:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restructure the repo around bckohan/python-package-template so the index builder ships as the PyPI/uvx package `gh-pages-pypi` (Typer CLI + Jinja2 templates) while the repo remains its own live demo.

**Architecture:** Cookiecutter output is merged at repo root (template files win; conflicts resolved per task). The old `scripts/build_index.py` splits into `src/gh_pages_pypi/index.py` (core logic, Jinja2 rendering) and `src/gh_pages_pypi/cli.py` (Typer). Demo packages and the demo release chain stay; `pages.yml` dogfoods the packaged tool via `uv run`.

**Tech Stack:** uv + hatchling, Typer, Jinja2, pytest, template CI (ruff/mypy/pyright/bandit/zizmor, PyPI trusted publishing).

**Spec:** `docs/superpowers/specs/2026-08-04-package-reorg-design.md`

**Commits:** Git commits are GPG-signed; the owner's passphrase is normally cached from recent commits. If `git commit` fails with a gpg error, STOP and ask the owner to run the commit.

---

## File Structure (end state)

```
pyproject.toml                    # template + [typer, jinja2] deps + console script + uv sources
uv.lock                           # committed
justfile                          # template + appended `demo-release` recipe
src/gh_pages_pypi/
  __init__.py py.typed            # from template
  index.py                        # core logic (Task 2)
  cli.py                          # Typer CLI (Task 3)
  templates/{landing,simple_root,project}.html   # Jinja2 (Task 2)
tests/
  __init__.py conftest.py test.py # from template
  test_index.py                   # ported from tests/test_build_index.py (Task 2)
  test_cli.py                     # Typer CliRunner tests (Task 3)
  test_packages.py                # existing demo-package tests (kept)
packages/demo-lib, demo-app       # unchanged
.github/workflows/
  release.yml test.yml lint.yml bandit.yml zizmor.yml   # from template
  demo-release.yml                # old release.yml renamed
  pages.yml                       # modified (Task 4)
doc/ .codecov.yml .readthedocs.yaml .pre-commit-config.yaml .gitattributes
CONTRIBUTING.md SECURITY.md CLAUDE.md AGENTS.md LICENSE(MIT) README.md
REMOVED: scripts/, tests/test_build_index.py, .github/workflows/scorecard.yml
```

---

### Task 1: Template scaffolding merge + packaging config

**Goal:** Template files live at repo root, `pyproject.toml` declares the package (deps, console script, editable demo packages), and `uv sync` produces a working environment.

**Files:**
- Modify: `.github/workflows/release.yml` → rename to `.github/workflows/demo-release.yml` (content: only the `name:` line changes)
- Create (copied from cookiecutter output): `.codecov.yml`, `.gitattributes`, `.github/CODEOWNERS`, `.github/dependabot.yml`, `.github/zizmor.yml`, `.github/workflows/{release,test,lint,bandit,zizmor}.yml`, `.pre-commit-config.yaml`, `.readthedocs.yaml`, `AGENTS.md`, `CLAUDE.md`, `CONTRIBUTING.md`, `SECURITY.md`, `doc/**`, `justfile`, `LICENSE`, `README.md` (template version for now; rewritten in Task 5), `pyproject.toml`, `src/gh_pages_pypi/{__init__.py,py.typed}`, `tests/{__init__.py,conftest.py,test.py}`
- Modify: `pyproject.toml` (deps, scripts, uv sources), `.gitignore` (additions), `justfile` (append recipe)
- Create: `uv.lock` (via `uv sync`)

**Acceptance Criteria:**
- [ ] `uv sync` succeeds; demo packages installed editable
- [ ] `uv run python -c "import gh_pages_pypi"` works
- [ ] `uv run --no-sync pytest tests/test.py tests/test_packages.py -v` → 4 passed
- [ ] `.github/workflows/scorecard.yml` does NOT exist; `demo-release.yml` exists with old release content

**Verify:** `uv run --no-sync pytest tests/test.py tests/test_packages.py -v` → 4 passed

**Steps:**

- [ ] **Step 1: Rename the demo release workflow (before the template's release.yml lands)**

```bash
git mv .github/workflows/release.yml .github/workflows/demo-release.yml
```

Then edit `.github/workflows/demo-release.yml` line 4: change `name: release` to `name: demo-release`.

- [ ] **Step 2: Generate the template**

```bash
cd "$(mktemp -d)" && uvx --with jinja2_time cookiecutter gh:bckohan/python-package-template --no-input \
  project_slug=gh-pages-pypi \
  description="Serve a PyPI-compatible package index from GitHub Pages, built from GitHub release assets." \
  author_name="Brian Kohan" author_email="bckohan@gmail.com" \
  github_owner=bckohan version=0.1.0 scorecard=false license=MIT
echo "GENERATED AT: $PWD/gh-pages-pypi"
```

- [ ] **Step 3: Copy generated files into the repo (template wins on conflicts; do NOT copy a .gitignore — the template doesn't generate one; our existing .gitignore stays)**

```bash
GEN=<generated-dir-from-step-2>/gh-pages-pypi
REPO=/Users/bckohan/Development/gh_pages_pypi
cp -R "$GEN/.codecov.yml" "$GEN/.gitattributes" "$GEN/.pre-commit-config.yaml" \
      "$GEN/.readthedocs.yaml" "$GEN/AGENTS.md" "$GEN/CLAUDE.md" "$GEN/CONTRIBUTING.md" \
      "$GEN/SECURITY.md" "$GEN/LICENSE" "$GEN/README.md" "$GEN/pyproject.toml" \
      "$GEN/justfile" "$GEN/doc" "$REPO/"
mkdir -p "$REPO/src" && cp -R "$GEN/src/gh_pages_pypi" "$REPO/src/"
cp "$GEN/tests/__init__.py" "$GEN/tests/conftest.py" "$GEN/tests/test.py" "$REPO/tests/"
cp "$GEN/.github/CODEOWNERS" "$GEN/.github/dependabot.yml" "$GEN/.github/zizmor.yml" "$REPO/.github/"
cp "$GEN"/.github/workflows/{release,test,lint,bandit,zizmor}.yml "$REPO/.github/workflows/"
```

Deliberately NOT copied: `.github/workflows/scorecard.yml` (spec: scorecard off).

- [ ] **Step 4: Fix repo URLs (repo is gh_pages_pypi, slug is gh-pages-pypi; readthedocs/codecov slugs stay dashed)**

```bash
cd /Users/bckohan/Development/gh_pages_pypi
grep -rl "github.com/bckohan/gh_pages_pypi" --include='*' . | grep -v '^\./\.git/' \
  | xargs sed -i '' 's|github.com/bckohan/gh_pages_pypi|github.com/bckohan/gh_pages_pypi|g'
```

- [ ] **Step 5: Wire packaging into `pyproject.toml`**

In the `[project]` table, replace `dependencies = []` with:

```toml
dependencies = [
    "typer>=0.15",
    "jinja2>=3.1",
]
```

After the `[project]` table (before `[build-system]`), add:

```toml
[project.scripts]
gh-pages-pypi = "gh_pages_pypi.cli:app"
```

In `[dependency-groups]`, append to the `dev` group list:

```toml
    "gh-pages-pypi-demo-lib",
    "gh-pages-pypi-demo-app",
```

And add (after the `[tool.uv]` table that contains `package = true`):

```toml
[tool.uv.sources]
gh-pages-pypi-demo-lib = { path = "packages/demo-lib", editable = true }
gh-pages-pypi-demo-app = { path = "packages/demo-app", editable = true }
```

- [ ] **Step 6: Append the demo-release recipe to the template `justfile`** (replaces the old repo-root justfile's `release` recipe; the old justfile was overwritten in Step 3)

```just

# CalVer-release a demo package: bump, test, commit, tag, push — triggers demo-release.yml → pages.yml
demo-release package:
    #!/usr/bin/env bash
    set -euo pipefail
    cd "{{ justfile_directory() }}"

    version=$(uv run python - "{{ package }}" <<'PYEOF'
    import re
    import subprocess
    import sys
    from datetime import date
    from pathlib import Path

    package = sys.argv[1]
    pyproject = Path("packages") / package / "pyproject.toml"
    if not pyproject.exists():
        sys.exit(f"error: no such package: {pyproject.parent}")

    today = date.today()
    base = f"{today.year}.{today.month}.{today.day}"
    tags = subprocess.run(
        ["git", "tag", "--list", f"{package}-v{base}*"],
        capture_output=True, text=True, check=True,
    ).stdout.split()
    version, serial = base, 0
    while f"{package}-v{version}" in tags:
        serial += 1
        version = f"{base}.{serial}"

    text, count = re.subn(
        r'(?m)^version = ".*"$', f'version = "{version}"', pyproject.read_text(), count=1
    )
    if count != 1:
        sys.exit(f"error: no version line found in {pyproject}")
    pyproject.write_text(text)
    print(version)
    PYEOF
    )

    uv run --no-sync pytest tests/ -q
    git add "packages/{{ package }}/pyproject.toml"
    git commit -m "Release {{ package }} ${version}"
    git tag "{{ package }}-v${version}"
    git push origin main "{{ package }}-v${version}"
    echo "Released {{ package }} ${version} — watch it at: gh run watch"
```

- [ ] **Step 7: .gitignore additions** (append; keep everything already there)

```
# template tooling artifacts
doc/build/
*.sarif
requirements-test-*.txt
```

- [ ] **Step 8: Sync environment and verify**

```bash
uv sync
uv run python -c "import gh_pages_pypi; print(gh_pages_pypi.__version__)"
```
Expected: `0.1.0`. `uv.lock` now exists.

Run: `uv run --no-sync pytest tests/test.py tests/test_packages.py -v`
Expected: 4 passed (template example test + 3 demo package tests). Note: `tests/test_build_index.py` still exists and still passes at this point (it imports `scripts/build_index.py` via sys.path); it is replaced in Task 2.

- [ ] **Step 9: Commit**

```bash
git add -A
git commit -m "Adopt python-package-template scaffolding for gh-pages-pypi"
```

---

### Task 2: index.py + Jinja2 templates (port core logic)

**Goal:** Core index-building logic lives in `src/gh_pages_pypi/index.py` rendering via packaged Jinja2 templates; old script and its test file are removed.

**Files:**
- Create: `src/gh_pages_pypi/index.py`
- Create: `src/gh_pages_pypi/templates/landing.html`, `src/gh_pages_pypi/templates/simple_root.html`, `src/gh_pages_pypi/templates/project.html`
- Create: `tests/test_index.py`
- Delete: `scripts/build_index.py`, `tests/test_build_index.py`

**Acceptance Criteria:**
- [ ] Same behavior as the old script's library surface (normalize, filename parsing, draft skip, sha256 fragments, empty-safe write_site)
- [ ] Templates ship inside the package (PackageLoader) with autoescape on
- [ ] `uv run --no-sync pytest tests/test_index.py -v` → 4 passed

**Verify:** `uv run --no-sync pytest tests/test_index.py -v` → 4 passed

**Steps:**

- [ ] **Step 1: Write the failing tests.** Create `tests/test_index.py` (ported from `tests/test_build_index.py`: same fixtures incl. the draft release; the argparse `main` test moves to Task 3 as a CLI test):

```python
from gh_pages_pypi import index

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
    assert index.normalize("Gh_Pages.PyPI--Demo") == "gh-pages-pypi-demo"


def test_project_name_from_filename():
    assert (
        index.project_name_from_filename("gh_pages_pypi_demo_lib-1.0.0-py3-none-any.whl")
        == "gh_pages_pypi_demo_lib"
    )
    assert (
        index.project_name_from_filename("gh_pages_pypi_demo_lib-1.0.0.tar.gz")
        == "gh_pages_pypi_demo_lib"
    )
    assert index.project_name_from_filename("release-notes.txt") is None


def test_collect_projects():
    projects = index.collect_projects(FIXTURE_RELEASES, hash_url=fake_hash)
    assert sorted(projects) == ["gh-pages-pypi-demo-app", "gh-pages-pypi-demo-lib"]
    lib_files = projects["gh-pages-pypi-demo-lib"]
    assert [f["filename"] for f in lib_files] == [
        "gh_pages_pypi_demo_lib-1.0.0-py3-none-any.whl",
        "gh_pages_pypi_demo_lib-1.0.0.tar.gz",
    ]
    assert all(f["sha256"] == "cafef00d" for f in lib_files)


def test_write_site(tmp_path):
    projects = index.collect_projects(FIXTURE_RELEASES, hash_url=fake_hash)
    index.write_site(projects, tmp_path, "bckohan/gh_pages_pypi")

    landing = (tmp_path / "index.html").read_text()
    assert "https://bckohan.github.io/gh_pages_pypi/simple/" in landing

    root = (tmp_path / "simple" / "index.html").read_text()
    assert '<a href="gh-pages-pypi-demo-lib/">' in root
    assert '<a href="gh-pages-pypi-demo-app/">' in root

    lib_page = (tmp_path / "simple" / "gh-pages-pypi-demo-lib" / "index.html").read_text()
    assert "#sha256=cafef00d" in lib_page
    assert "gh_pages_pypi_demo_lib-1.0.0-py3-none-any.whl</a>" in lib_page
    assert '<meta name="pypi:repository-version" content="1.0"' in lib_page
```

Run: `uv run --no-sync pytest tests/test_index.py -v`
Expected: FAIL (ModuleNotFoundError: gh_pages_pypi.index)

- [ ] **Step 2: Create `src/gh_pages_pypi/index.py`:**

```python
"""Build a PEP 503 "simple" package index from GitHub release assets.

Lists every release in a GitHub repository, collects the ``.whl`` and
``.tar.gz`` assets, and writes a static PyPI-compatible index that GitHub
Pages can serve. Links point at the release assets' download URLs and carry
``#sha256=`` fragments so pip verifies every download.
"""

import hashlib
import json
import re
import urllib.request
from pathlib import Path

from jinja2 import Environment, PackageLoader, select_autoescape

API_ROOT = "https://api.github.com"

_env = Environment(
    loader=PackageLoader("gh_pages_pypi"),
    autoescape=select_autoescape(("html",)),
    keep_trailing_newline=True,
)


def normalize(name: str) -> str:
    """Normalize a project name per PEP 503."""
    return re.sub(r"[-_.]+", "-", name).lower()


def project_name_from_filename(filename: str) -> "str | None":
    """Return the project name for a wheel or sdist filename, else None."""
    if filename.endswith(".whl"):
        return filename.split("-")[0]
    if filename.endswith(".tar.gz"):
        return filename[: -len(".tar.gz")].rsplit("-", 1)[0]
    return None


def fetch_releases(repo: str, token: str) -> list:
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


def hash_url(url: str) -> str:
    """Download ``url`` and return the sha256 hex digest of its content."""
    digest = hashlib.sha256()
    with urllib.request.urlopen(url) as response:
        for chunk in iter(lambda: response.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def collect_projects(releases: list, hash_url=hash_url) -> dict:
    """Map normalized project names to their release files.

    Returns ``{project: [{"filename", "url", "sha256"}, ...]}`` sorted by
    project name and filename. Assets that are not wheels or sdists are
    ignored, as are draft releases (their assets aren't publicly
    downloadable).
    """
    projects: dict = {}
    for release in releases:
        if release.get("draft"):
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


def pages_url(repo: str) -> str:
    """Return the GitHub Pages base URL for the ``owner/name`` repository."""
    owner, name = repo.split("/", 1)
    return f"https://{owner.lower()}.github.io/{name}/"


def write_site(projects: dict, out_dir: Path, repo: str) -> None:
    """Write the landing page and PEP 503 simple index under ``out_dir``."""
    simple = out_dir / "simple"
    simple.mkdir(parents=True, exist_ok=True)
    project_page = _env.get_template("project.html")
    for project, files in projects.items():
        project_dir = simple / project
        project_dir.mkdir(parents=True, exist_ok=True)
        (project_dir / "index.html").write_text(
            project_page.render(project=project, files=files)
        )
    (simple / "index.html").write_text(
        _env.get_template("simple_root.html").render(projects=projects)
    )
    (out_dir / "index.html").write_text(
        _env.get_template("landing.html").render(
            repo=repo, index_url=pages_url(repo) + "simple/", projects=projects
        )
    )
```

- [ ] **Step 3: Create the templates.**

`src/gh_pages_pypi/templates/project.html`:

```html
<!DOCTYPE html>
<html>
  <head>
    <meta name="pypi:repository-version" content="1.0">
    <title>Links for {{ project }}</title>
  </head>
  <body>
    <h1>Links for {{ project }}</h1>
{% for file in files %}    <a href="{{ file.url }}#sha256={{ file.sha256 }}">{{ file.filename }}</a><br/>
{% endfor %}  </body>
</html>
```

`src/gh_pages_pypi/templates/simple_root.html`:

```html
<!DOCTYPE html>
<html>
  <head>
    <meta name="pypi:repository-version" content="1.0">
    <title>Simple index</title>
  </head>
  <body>
{% for project in projects %}    <a href="{{ project }}/">{{ project }}</a><br/>
{% endfor %}  </body>
</html>
```

`src/gh_pages_pypi/templates/landing.html`:

```html
<!DOCTYPE html>
<html>
  <head>
    <meta charset="utf-8">
    <title>{{ repo }} package index</title>
  </head>
  <body>
    <h1>{{ repo }} package index</h1>
    <p>A PyPI-compatible (PEP 503) package index served by GitHub Pages.
       Packages are hosted as GitHub release assets.</p>
    <p>Install packages with:</p>
    <pre>pip install --extra-index-url {{ index_url }} PACKAGE</pre>
    <p>Available packages:</p>
    <ul>
{% for project in projects %}      <li><code>{{ project }}</code></li>
{% endfor %}    </ul>
    <p><a href="simple/">Browse the simple index</a></p>
  </body>
</html>
```

- [ ] **Step 4: Delete the old script and test**

```bash
git rm scripts/build_index.py tests/test_build_index.py
rmdir scripts 2>/dev/null || true
```

- [ ] **Step 5: Verify**

Run: `uv run --no-sync pytest tests/test_index.py -v`
Expected: 4 passed.

Run: `uv run --no-sync pytest tests/ -v`
Expected: 8 passed (test.py 1 + test_index 4 + test_packages 3).

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "Move index builder into gh_pages_pypi.index with Jinja2 templates"
```

---

### Task 3: Typer CLI

**Goal:** `gh-pages-pypi OWNER/REPO --out DIR [--token ...]` works as a console script with the old error semantics.

**Files:**
- Create: `src/gh_pages_pypi/cli.py`
- Create: `tests/test_cli.py`

**Acceptance Criteria:**
- [ ] Missing token / API failure / zero packages → clean error message, exit code 1
- [ ] Success writes the site and prints the project count
- [ ] `uv run --no-sync gh-pages-pypi --help` shows usage

**Verify:** `uv run --no-sync pytest tests/test_cli.py -v` → 4 passed

**Steps:**

- [ ] **Step 1: Write the failing tests.** Create `tests/test_cli.py`:

```python
from typer.testing import CliRunner

from gh_pages_pypi import index
from gh_pages_pypi.cli import app
from tests.test_index import FIXTURE_RELEASES

runner = CliRunner()


def all_output(result):
    """stdout+stderr across click versions (mix_stderr removed in click 8.2)."""
    try:
        return result.output + (result.stderr or "")
    except (ValueError, AttributeError):
        return result.output


def test_cli_requires_token(tmp_path, monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    result = runner.invoke(app, ["bckohan/gh_pages_pypi", "--out", str(tmp_path)])
    assert result.exit_code == 1
    assert "provide --token or set GITHUB_TOKEN" in all_output(result)


def test_cli_fails_with_no_packages(tmp_path, monkeypatch):
    monkeypatch.setattr(index, "fetch_releases", lambda repo, token: [])
    result = runner.invoke(
        app, ["bckohan/gh_pages_pypi", "--out", str(tmp_path), "--token", "x"]
    )
    assert result.exit_code == 1
    assert "no package assets" in all_output(result)


def test_cli_reports_api_failure(tmp_path, monkeypatch):
    import urllib.error

    def boom(repo, token):
        raise urllib.error.URLError("nope")

    monkeypatch.setattr(index, "fetch_releases", boom)
    result = runner.invoke(
        app, ["bckohan/gh_pages_pypi", "--out", str(tmp_path), "--token", "x"]
    )
    assert result.exit_code == 1
    assert "GitHub API request for bckohan/gh_pages_pypi failed" in all_output(result)


def test_cli_writes_site(tmp_path, monkeypatch):
    monkeypatch.setattr(index, "fetch_releases", lambda repo, token: FIXTURE_RELEASES)
    monkeypatch.setattr(index, "hash_url", lambda url: "cafef00d")
    result = runner.invoke(
        app, ["bckohan/gh_pages_pypi", "--out", str(tmp_path), "--token", "x"]
    )
    assert result.exit_code == 0, all_output(result)
    assert "wrote index for 2 project(s)" in result.output
    assert (tmp_path / "simple" / "gh-pages-pypi-demo-lib" / "index.html").exists()
```

Note: `test_cli_writes_site` monkeypatches `index.hash_url` (the module attribute); `collect_projects`' default argument binds at def time, so the CLI path must call `collect_projects(releases)` and `collect_projects` must look the hash function up dynamically — to keep the default-arg injection for tests AND allow this monkeypatching, the CLI passes nothing and `collect_projects`'s default is used. Therefore this test instead passes because the CLI calls `index.collect_projects(releases, hash_url=index.hash_url)`? NO — keep it simple: the CLI calls `index.collect_projects(releases)`, and this test monkeypatches BEFORE invoke, but the default arg was already bound. **Resolution (implement exactly this):** in `cli.py`, call `index.collect_projects(releases, hash_url=index.hash_url)` so the module attribute is looked up at call time and the monkeypatch takes effect.

Run: `uv run --no-sync pytest tests/test_cli.py -v`
Expected: FAIL (ModuleNotFoundError: gh_pages_pypi.cli)

- [ ] **Step 2: Create `src/gh_pages_pypi/cli.py`:**

```python
"""Typer command line interface for gh-pages-pypi."""

import urllib.error
from pathlib import Path
from typing import Annotated, Optional

import typer

from gh_pages_pypi import index

app = typer.Typer(add_completion=False)


@app.command()
def build(
    repo: Annotated[str, typer.Argument(help="GitHub repository as OWNER/NAME")],
    out: Annotated[Path, typer.Option(help="Directory to write the index to")],
    token: Annotated[
        Optional[str],
        typer.Option(envvar="GITHUB_TOKEN", help="GitHub API token"),
    ] = None,
) -> None:
    """Build a PEP 503 package index from the repository's release assets."""
    if not token:
        typer.echo("error: provide --token or set GITHUB_TOKEN", err=True)
        raise typer.Exit(1)
    try:
        releases = index.fetch_releases(repo, token)
    except urllib.error.URLError as error:
        typer.echo(f"error: GitHub API request for {repo} failed: {error}", err=True)
        raise typer.Exit(1)
    projects = index.collect_projects(releases, hash_url=index.hash_url)
    if not projects:
        typer.echo(
            f"error: no package assets found in releases of {repo}; "
            "refusing to build an empty index",
            err=True,
        )
        raise typer.Exit(1)
    index.write_site(projects, out, repo)
    typer.echo(f"wrote index for {len(projects)} project(s) to {out}")
```

- [ ] **Step 3: Verify**

Run: `uv run --no-sync pytest tests/test_cli.py -v` → 4 passed
Run: `uv run --no-sync pytest tests/ -v` → 12 passed
Run: `uv run gh-pages-pypi --help`
Expected: usage text showing REPO argument and --out/--token options (a fresh `uv run` without --no-sync installs the console script from the current source).

- [ ] **Step 4: Commit**

```bash
git add src/gh_pages_pypi/cli.py tests/test_cli.py
git commit -m "Add Typer CLI and console script"
```

---

### Task 4: pages.yml dogfoods the tool

**Goal:** The Pages workflow builds the index with the packaged tool via uv instead of the deleted script.

**Files:**
- Modify: `.github/workflows/pages.yml` (build job only)

**Acceptance Criteria:**
- [ ] Build step uses astral-sh/setup-uv and `uv run gh-pages-pypi`
- [ ] Triggers, permissions, concurrency, deploy job unchanged
- [ ] All workflow files parse as YAML

**Verify:** `uv run --no-sync python -c "import pathlib, yaml; [yaml.safe_load(p.read_text()) for p in pathlib.Path('.github/workflows').glob('*.yml')]; print('OK')"` → `OK` (pyyaml comes from the docs/lint tooling; if missing, use `uvx --from pyyaml python ...` equivalent: `uvx --with pyyaml python -c ...`)

**Steps:**

- [ ] **Step 1: Replace the build job's python setup + script step.** In `.github/workflows/pages.yml`, replace:

```yaml
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Build the package index
        env:
          GITHUB_TOKEN: ${{ github.token }}
        run: python scripts/build_index.py --repo "$GITHUB_REPOSITORY" --out site
```

with:

```yaml
      - name: Install uv
        uses: astral-sh/setup-uv@v5

      # Runs the gh-pages-pypi CLI from this repo's own source — the repo
      # dogfoods the tool it publishes. Other repos would use:
      #   uvx gh-pages-pypi "$GITHUB_REPOSITORY" --out site
      - name: Build the package index
        env:
          GITHUB_TOKEN: ${{ github.token }}
        run: uv run --no-default-groups gh-pages-pypi "$GITHUB_REPOSITORY" --out site
```

Also update the header comment line `# build_index.py refuses to deploy an empty index.` to `# gh-pages-pypi refuses to deploy an empty index.` and the line above it accordingly (`# NOTE: this fails by design while the repository has no releases yet —`  stays).

- [ ] **Step 2: Verify all workflows parse**

Run: `uvx --with pyyaml python -c "import pathlib, yaml; [yaml.safe_load(p.read_text()) for p in pathlib.Path('.github/workflows').glob('*.yml')]; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/pages.yml
git commit -m "pages.yml: build the index with the packaged gh-pages-pypi CLI"
```

---

### Task 5: README rewrite + full local verification

**Goal:** README presents the tool first (uvx/pip + workflow snippet) and the live demo second; the whole quality gate passes locally.

**Files:**
- Modify: `README.md` (template version from Task 1 → final content)

**Acceptance Criteria:**
- [ ] Keeps the template's badge header
- [ ] Documents: install (pip/uvx), CLI usage, using it in any repo's workflow, the live demo (Try it), demo release chain (`just demo-release`), development (uv/just), caveats
- [ ] `uv run --no-sync pytest tests/ -v` → 12 passed; ruff clean; mypy clean

**Verify:** `uv run --no-sync pytest tests/ -v` → 12 passed

**Steps:**

- [ ] **Step 1: Rewrite README.** Keep lines 1–11 of the template README (title + badge block) exactly as generated, then replace everything after with:

````markdown

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

## Development

```bash
just setup      # create the uv venv + pre-commit hooks
just install    # sync all dependency groups
just test       # run the test suite
just check      # lint, format, types, package, docs
```
````

- [ ] **Step 2: Lint/format/type-check the new code**

```bash
uv run --no-default-groups --group lint ruff check src tests --fix
uv run --no-default-groups --group lint ruff format src tests
uv run --no-default-groups --all-extras --group typing mypy
```
Expected: ruff reports no remaining errors; mypy: no issues found. (If mypy needs stubs config already provided by the template pyproject, it is already set to `packages = ["gh_pages_pypi"]`.)

- [ ] **Step 3: Full verification**

Run: `uv run --no-sync pytest tests/ -v`
Expected: 12 passed.

Real-API smoke test:

```bash
GITHUB_TOKEN=$(gh auth token) uv run gh-pages-pypi bckohan/gh_pages_pypi --out /tmp/ghp-site-check
ls /tmp/ghp-site-check/simple
```
Expected: `wrote index for 2 project(s)...`; `gh-pages-pypi-demo-app  gh-pages-pypi-demo-lib  index.html`.

uvx-ability (from local source):

```bash
uvx --from . gh-pages-pypi --help
```
Expected: usage text.

- [ ] **Step 4: Commit**

```bash
git add README.md src tests
git commit -m "Rewrite README around the gh-pages-pypi tool; lint and type-check"
```

---

### Task 6: Push + CI + live-demo verification

**Goal:** Everything is green on GitHub: template CI passes, the demo chain still works, the live index still serves.

**Files:** none (operational)

**Acceptance Criteria:**
- [ ] test.yml and lint.yml green on main
- [ ] A `just demo-release demo-lib` run completes: GitHub Release created, pages deployed
- [ ] Fresh-venv `pip install --index-url https://bckohan.github.io/gh_pages_pypi/simple/ gh-pages-pypi-demo-app` works and `demo-app` prints the greeting

**Verify:** the pip install + `demo-app` output above

**Steps:**

- [ ] **Step 1: Push and watch CI**

```bash
git push origin main
gh run list --limit 10   # poll until test/lint/pages complete
```
Expected: test.yml green, lint.yml green (bandit/zizmor may need repo settings; report but don't block), pages.yml green (releases exist).

- [ ] **Step 2: Exercise the demo chain** — run `just demo-release demo-lib` (or its constituent commands if the recipe is blocked by the environment), watch the demo-release run create the GitHub Release and dispatch pages.

- [ ] **Step 3: Live install proof**

```bash
python3 -m venv /tmp/ghp-livetest
/tmp/ghp-livetest/bin/pip install --quiet --index-url https://bckohan.github.io/gh_pages_pypi/simple/ gh-pages-pypi-demo-app
/tmp/ghp-livetest/bin/demo-app "reorganized"
```
Expected: `Hello, reorganized! (served from GitHub Pages)`

- [ ] **Step 4: Report remaining owner-only setup** (do not attempt): PyPI trusted-publisher registration for `gh-pages-pypi` + first `v0.1.0` tag (template release.yml verifies signed tags), readthedocs + codecov wiring.

---

## Post-plan notes

- The template's `release.yml` publishes on `v[0-9]*` tags only — demo tags (`demo-*-v*`) never trigger it, and `demo-release.yml`'s trigger doesn't match `v*`. No collision.
- `tests/test_packages.py` keeps passing throughout because Task 1 wires the demo packages into the uv dev environment (`[tool.uv.sources]`, editable).
- The `.venv` directory created earlier by `python -m venv` is replaced by uv on the first `uv sync` (uv reuses/replaces `.venv`).
