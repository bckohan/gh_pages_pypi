# Multi-Repo Config + Template Hooks Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers-extended-cc:subagent-driven-development (recommended) or superpowers-extended-cc:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **PROJECT RULE (AGENTS.md):** agents never commit or push — the human driver
> does. All "commit" checkpoints in this plan are therefore DRIVER actions;
> implementers stop at "verified in working tree".

**Goal:** Aggregate release assets from N configured repositories into one index (YAML config), with Jinja template overrides via a directory and `builtin/`-prefixed block inheritance.

**Architecture:** New `config.py` (frozen dataclass + validation, pyyaml). `index.py` gains `build_env(templates_dir)` (ChoiceLoader: overrides → PrefixLoader `builtin/` → package templates); `write_site` decouples from a single repo (`title`, `index_url`, `templates_dir` kwargs); `collect_projects` dedupes duplicate filenames with config-order precedence. CLI: `--config` XOR positional `REPO` (shortcut normalizes to a one-repo Config).

**Tech Stack:** Python 3.10+, typer, jinja2 (ChoiceLoader/PrefixLoader/FileSystemLoader), pyyaml, pytest.

**Spec:** `.agents/docs/superpowers/specs/2026-08-05-multi-repo-config-design.md`

**Context for the implementer:**
- Current call chain: `cli.build(repo, out, token)` → `index.fetch_releases(repo, token)` → `index.collect_projects(releases, hash_url)` → `index.write_site(projects, out, repo)`. Templates render via a module-global `_env = Environment(loader=PackageLoader("github_releases_pypi"), autoescape=select_autoescape(("html",)), keep_trailing_newline=True)`.
- Tests assert SUBSTRINGS of rendered output, not full bytes — insignificant whitespace changes from block tags are acceptable; every existing assertion must keep passing.
- The working tree already carries uncommitted (driver-pending) changes to justfile/.github/docs from the release-flow work — do not touch those files except where a task says so.

---

### Task 1: `config.py` with validation + pyyaml dependency

**Goal:** `config.load(path)` parses and validates the YAML config into a frozen `Config`; every invalid shape raises `ConfigError` with a precise message.

**Files:**
- Create: `src/github_releases_pypi/config.py`
- Create: `tests/test_config.py`
- Modify: `pyproject.toml` (add `"pyyaml>=6"` to `[project] dependencies`; add `"types-pyyaml"` to the typing dependency group used by `just check-types`)

**Acceptance Criteria:**
- [ ] Valid config (all keys) and minimal config (repositories only → defaults) load correctly
- [ ] Each invalid shape raises `ConfigError`: unreadable file, invalid YAML, non-mapping top level, unknown key, missing/empty/non-list `repositories`, non-`OWNER/NAME` entry, nonexistent `templates` dir, non-https `url`, non-string `title`
- [ ] Relative `templates` resolves against the config file's parent, not CWD

**Verify:** `just test tests/test_config.py` → all pass; `just check-types` → clean

**Steps:**

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_config.py
from pathlib import Path

import pytest

from github_releases_pypi.config import Config, ConfigError, load


def write(tmp_path: Path, text: str) -> Path:
    cfg = tmp_path / "index.yml"
    cfg.write_text(text)
    return cfg


def test_load_full(tmp_path):
    (tmp_path / "tpl").mkdir()
    cfg = load(
        write(
            tmp_path,
            """
repositories:
  - bckohan/github-releases-pypi
  - someorg/other-project
templates: ./tpl
title: My Package Index
url: https://example.github.io/idx/
""",
        )
    )
    assert cfg == Config(
        repositories=("bckohan/github-releases-pypi", "someorg/other-project"),
        templates=(tmp_path / "tpl").resolve(),
        title="My Package Index",
        url="https://example.github.io/idx/",
    )


def test_load_minimal_defaults(tmp_path):
    cfg = load(write(tmp_path, "repositories: [a/b]\n"))
    assert cfg.repositories == ("a/b",)
    assert cfg.templates is None
    assert cfg.title == "Package index"
    assert cfg.url is None


def test_templates_relative_to_config_dir(tmp_path, monkeypatch):
    (tmp_path / "tpl").mkdir()
    monkeypatch.chdir(tmp_path.parent)  # CWD != config dir
    cfg = load(write(tmp_path, "repositories: [a/b]\ntemplates: tpl\n"))
    assert cfg.templates == (tmp_path / "tpl").resolve()


@pytest.mark.parametrize(
    "text,match",
    [
        ("- just\n- a list\n", "top level must be a mapping"),
        ("repositories: [a/b]\nbogus: 1\n", "unknown key"),
        ("title: no repos\n", "'repositories' must be a non-empty list"),
        ("repositories: []\n", "'repositories' must be a non-empty list"),
        ("repositories: notalist\n", "'repositories' must be a non-empty list"),
        ("repositories: [noslash]\n", "is not OWNER/NAME"),
        ("repositories: [a/b/c]\n", "is not OWNER/NAME"),
        ("repositories: [/b]\n", "is not OWNER/NAME"),
        ("repositories: [a/b]\ntemplates: ./missing\n", "templates directory not found"),
        ("repositories: [a/b]\nurl: http://insecure.example\n", "'url' must be https"),
        ("repositories: [a/b]\ntitle: [not, a, string]\n", "'title' must be a string"),
        ("repositories: [a/b]\nurl: [::bad yaml::\n", "invalid YAML"),
    ],
)
def test_load_errors(tmp_path, text, match):
    with pytest.raises(ConfigError, match=match):
        load(write(tmp_path, text))


def test_load_missing_file(tmp_path):
    with pytest.raises(ConfigError, match="cannot read config file"):
        load(tmp_path / "nope.yml")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `just test tests/test_config.py`
Expected: FAIL — `ModuleNotFoundError: github_releases_pypi.config`

- [ ] **Step 3: Add dependencies and sync**

In `pyproject.toml`: append `"pyyaml>=6"` to `[project] dependencies`; append `"types-pyyaml"` to the typing group (find it: `grep -n -A5 'typing' pyproject.toml` — the group installed by `just check-types`). Then run `uv sync --all-extras` (updates `uv.lock` — a file edit, allowed).

- [ ] **Step 4: Write `config.py`**

```python
# src/github_releases_pypi/config.py
"""Load and validate the YAML configuration for multi-repository indexes."""

from dataclasses import dataclass
from pathlib import Path

import yaml

_KNOWN_KEYS = {"repositories", "templates", "title", "url"}


class ConfigError(ValueError):
    """Raised when the YAML configuration is missing or invalid."""


@dataclass(frozen=True)
class Config:
    """Validated build configuration."""

    repositories: tuple[str, ...]
    templates: Path | None = None
    title: str = "Package index"
    url: str | None = None


def load(path: Path) -> Config:
    """Parse and validate the YAML config file at ``path``."""
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError as error:
        raise ConfigError(f"cannot read config file {path}: {error}") from error
    except UnicodeDecodeError as error:
        raise ConfigError(f"config file {path} is not valid UTF-8") from error
    except yaml.YAMLError as error:
        raise ConfigError(f"invalid YAML in {path}: {error}") from error
    if not isinstance(raw, dict):
        raise ConfigError(f"{path}: top level must be a mapping")
    if unknown := set(raw) - _KNOWN_KEYS:
        raise ConfigError(f"{path}: unknown key(s): {', '.join(sorted(unknown))}")
    repositories = raw.get("repositories")
    if not isinstance(repositories, list) or not repositories:
        raise ConfigError(f"{path}: 'repositories' must be a non-empty list")
    for repo in repositories:
        parts = repo.split("/") if isinstance(repo, str) else []
        if len(parts) != 2 or not all(parts):
            raise ConfigError(f"{path}: repository {repo!r} is not OWNER/NAME")
    if len({r.casefold() for r in repositories}) != len(repositories):
        raise ConfigError(f"{path}: 'repositories' contains duplicates")
    templates = None
    if (raw_templates := raw.get("templates")) is not None:
        if not isinstance(raw_templates, str):
            raise ConfigError(f"{path}: 'templates' must be a string path")
        templates = (path.parent / raw_templates).resolve()
        if not templates.is_dir():
            raise ConfigError(f"{path}: templates directory not found: {templates}")
    url = raw.get("url")
    if url is not None and not isinstance(url, str):
        raise ConfigError(f"{path}: 'url' must be a string")
    if url is not None and not url.startswith("https://"):
        raise ConfigError(f"{path}: 'url' must be https")
    title = raw.get("title", "Package index")
    if not isinstance(title, str):
        raise ConfigError(f"{path}: 'title' must be a string")
    return Config(
        repositories=tuple(repositories),
        templates=templates,
        title=title,
        url=None if url is None else str(url),
    )
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `just test tests/test_config.py` → Expected: all pass
Run: `just check-types` → Expected: clean (this is why `types-pyyaml` was added)
Run: `just test` → Expected: existing suite still green (13 + new)

*(Driver checkpoint: commit as "Add YAML config loading for multi-repository indexes")*

---

### Task 2: Template environment, blocks, and `write_site` signature

**Goal:** `build_env(templates_dir)` serves overrides ahead of built-ins (with `builtin/` prefix for extends); built-in templates gain blocks; `write_site` takes `title`/`index_url`/`templates_dir` instead of `repo`.

**Files:**
- Modify: `src/github_releases_pypi/index.py` (imports, remove `_env`, add `build_env`, rewrite `write_site`)
- Modify: `src/github_releases_pypi/templates/landing.html`, `project.html`, `simple_root.html`
- Modify: `tests/test_index.py` (update `test_write_site`; add override/block/no-url tests)

**Acceptance Criteria:**
- [ ] A `landing.html` in the override dir replaces the landing page wholesale
- [ ] An override doing `{% extends "builtin/landing.html" %}` overriding one block keeps the rest of the built-in output
- [ ] `write_site(..., index_url=None)` omits the `pip install --extra-index-url` example; with a URL it renders as before
- [ ] All existing substring assertions still pass

**Verify:** `just test tests/test_index.py` → all pass

**Steps:**

- [ ] **Step 1: Write the failing tests**

In `tests/test_index.py`, REPLACE `test_write_site` with the following and ADD the three new tests:

```python
def test_write_site(tmp_path):
    projects = index.collect_projects(FIXTURE_RELEASES, hash_url=fake_hash)
    index.write_site(
        projects,
        tmp_path,
        title="bckohan/github-releases-pypi package index",
        index_url="https://bckohan.github.io/github-releases-pypi/simple/",
    )

    landing = (tmp_path / "index.html").read_text()
    assert "https://bckohan.github.io/github-releases-pypi/simple/" in landing
    assert "bckohan/github-releases-pypi package index" in landing

    root = (tmp_path / "simple" / "index.html").read_text()
    assert '<a href="github-releases-pypi-demo-lib/">' in root
    assert '<a href="github-releases-pypi-demo-app/">' in root

    lib_page = (
        tmp_path / "simple" / "github-releases-pypi-demo-lib" / "index.html"
    ).read_text()
    assert "#sha256=cafef00d" in lib_page
    assert "github_releases_pypi_demo_lib-1.0.0-py3-none-any.whl</a>" in lib_page
    assert '<meta name="pypi:repository-version" content="1.0"' in lib_page


def test_write_site_without_index_url(tmp_path):
    projects = index.collect_projects(FIXTURE_RELEASES, hash_url=fake_hash)
    index.write_site(projects, tmp_path, title="An index", index_url=None)
    landing = (tmp_path / "index.html").read_text()
    assert "--extra-index-url" not in landing
    assert '<a href="simple/">' in landing


def test_write_site_template_override(tmp_path):
    overrides = tmp_path / "tpl"
    overrides.mkdir()
    (overrides / "landing.html").write_text("<html>custom landing</html>\n")
    projects = index.collect_projects(FIXTURE_RELEASES, hash_url=fake_hash)
    index.write_site(
        projects,
        tmp_path / "site",
        title="T",
        index_url=None,
        templates_dir=overrides,
    )
    assert (tmp_path / "site" / "index.html").read_text() == "<html>custom landing</html>\n"
    # other templates still fall back to the built-ins
    root = (tmp_path / "site" / "simple" / "index.html").read_text()
    assert '<meta name="pypi:repository-version" content="1.0"' in root


def test_write_site_block_extension(tmp_path):
    overrides = tmp_path / "tpl"
    overrides.mkdir()
    (overrides / "landing.html").write_text(
        '{% extends "builtin/landing.html" %}'
        "{% block footer %}<footer>custom footer</footer>{% endblock %}"
    )
    projects = index.collect_projects(FIXTURE_RELEASES, hash_url=fake_hash)
    index.write_site(
        projects,
        tmp_path / "site",
        title="Extended",
        index_url=None,
        templates_dir=overrides,
    )
    landing = (tmp_path / "site" / "index.html").read_text()
    assert "<footer>custom footer</footer>" in landing
    assert "Available packages:" in landing  # built-in content block retained
```

- [ ] **Step 2: Run to verify failure**

Run: `just test tests/test_index.py` → Expected: FAIL (`write_site` rejects keyword args)

- [ ] **Step 3: Rewrite the env + `write_site` in index.py**

Replace the jinja import and `_env` global:

```python
from jinja2 import (
    ChoiceLoader,
    Environment,
    FileSystemLoader,
    PackageLoader,
    PrefixLoader,
    select_autoescape,
)
```

```python
def build_env(templates_dir: Path | None = None) -> Environment:
    """Return the Jinja environment, checking ``templates_dir`` first.

    Built-in templates stay reachable under a ``builtin/`` prefix so an
    override can ``{% extends "builtin/landing.html" %}`` without recursing
    into itself.
    """
    builtin = PackageLoader("github_releases_pypi")
    loaders: list = []
    if templates_dir is not None:
        loaders.append(FileSystemLoader(templates_dir))
    loaders += [PrefixLoader({"builtin": builtin}), builtin]
    return Environment(
        loader=ChoiceLoader(loaders),
        autoescape=select_autoescape(("html",)),
        keep_trailing_newline=True,
    )
```

Replace `write_site`:

```python
def write_site(
    projects: Projects,
    out_dir: Path,
    *,
    title: str,
    index_url: str | None,
    templates_dir: Path | None = None,
) -> None:
    """Write the landing page and PEP 503 simple index under ``out_dir``."""
    env = build_env(templates_dir)
    simple = out_dir / "simple"
    simple.mkdir(parents=True, exist_ok=True)
    project_page = env.get_template("project.html")
    for project, files in projects.items():
        project_dir = simple / project
        project_dir.mkdir(parents=True, exist_ok=True)
        (project_dir / "index.html").write_text(
            project_page.render(project=project, files=files), encoding="utf-8"
        )
    (simple / "index.html").write_text(
        env.get_template("simple_root.html").render(projects=projects),
        encoding="utf-8",
    )
    (out_dir / "index.html").write_text(
        env.get_template("landing.html").render(
            title=title, index_url=index_url, projects=projects
        ),
        encoding="utf-8",
    )
```

- [ ] **Step 4: Blockify the templates**

`templates/landing.html` (full new content):

```html
<!DOCTYPE html>
<html>
  <head>
    <meta charset="utf-8">
    <title>{% block title %}{{ title }}{% endblock %}</title>{% block head %}{% endblock %}
  </head>
  <body>
    {% block header %}<h1>{{ title }}</h1>
    <p>A PyPI-compatible (PEP 503) package index served by GitHub Pages.
       Packages are hosted as GitHub release assets.</p>{% endblock %}
    {% block content %}{% if index_url %}<p>Install packages with:</p>
    <pre>pip install --extra-index-url {{ index_url }} PACKAGE</pre>
    {% endif %}<p>Available packages:</p>
    <ul>
{% for project in projects %}      <li><code>{{ project }}</code></li>
{% endfor %}    </ul>
    <p><a href="simple/">Browse the simple index</a></p>{% endblock %}
    {% block footer %}{% endblock %}
  </body>
</html>
```

`templates/project.html` (full new content):

```html
<!DOCTYPE html>
<html>
  <head>
    <meta name="pypi:repository-version" content="1.0">
    <title>{% block title %}Links for {{ project }}{% endblock %}</title>{% block head %}{% endblock %}
  </head>
  <body>
    {% block header %}<h1>Links for {{ project }}</h1>{% endblock %}
{% block content %}{% for file in files %}    <a href="{{ file.url }}#sha256={{ file.sha256 }}">{{ file.filename }}</a><br/>
{% endfor %}{% endblock %}    {% block footer %}{% endblock %}
  </body>
</html>
```

`templates/simple_root.html` (full new content — `head` block only; body stays PEP 503 machine-parseable):

```html
<!DOCTYPE html>
<html>
  <head>
    <meta name="pypi:repository-version" content="1.0">
    <title>Simple index</title>{% block head %}{% endblock %}
  </head>
  <body>
{% for project in projects %}    <a href="{{ project }}/">{{ project }}</a><br/>
{% endfor %}  </body>
</html>
```

- [ ] **Step 5: Run tests**

Run: `just test tests/test_index.py` → Expected: all pass.
NOTE: `tests/test_cli.py::test_cli_writes_site` and `test_cli_token_from_env` will FAIL at this point — `cli.py` still calls `write_site(projects, out, repo)` positionally. Make the minimal interim fix in `cli.py` line 41: `index.write_site(projects, out, title=f"{repo} package index", index_url=index.pages_url(repo) + "simple/")` — Task 4 replaces this line properly.
Run: `just test` → Expected: whole suite green.

*(Driver checkpoint: commit as "Add template override hooks and block-based extension")*

---

### Task 3: Duplicate-filename dedupe in `collect_projects`

**Goal:** The same filename appearing in multiple releases/repos is indexed once (first occurrence wins) with a stderr warning; the duplicate is never hashed (no wasted download).

**Files:**
- Modify: `src/github_releases_pypi/index.py` (`collect_projects`; add `import sys`)
- Modify: `tests/test_index.py` (one new test)

**Acceptance Criteria:**
- [ ] Duplicate filename skipped before `hash_url` is called for it
- [ ] Warning names the duplicate filename on stderr
- [ ] First-occurrence ordering preserved

**Verify:** `just test tests/test_index.py` → all pass

**Steps:**

- [ ] **Step 1: Write the failing test**

```python
def test_collect_projects_dedupes_duplicate_filenames(capsys):
    duplicate = {
        "tag_name": "mirror-v1.0.0",
        "assets": [
            {
                "name": "github_releases_pypi_demo_lib-1.0.0-py3-none-any.whl",
                "browser_download_url": "https://github.com/other/mirror/releases/download/v1/github_releases_pypi_demo_lib-1.0.0-py3-none-any.whl",
            },
        ],
    }
    hashed = []

    def counting_hash(url):
        hashed.append(url)
        return "cafef00d"

    projects = index.collect_projects(
        FIXTURE_RELEASES + [duplicate], hash_url=counting_hash
    )
    lib_files = projects["github-releases-pypi-demo-lib"]
    whl = [f for f in lib_files if f["filename"].endswith(".whl")]
    assert len(whl) == 1
    assert "bckohan/github-releases-pypi" in whl[0]["url"]  # first occurrence won
    assert not any("other/mirror" in url for url in hashed)  # duplicate never hashed
    assert (
        "duplicate asset github_releases_pypi_demo_lib-1.0.0-py3-none-any.whl"
        in capsys.readouterr().err
    )
```

- [ ] **Step 2: Run to verify failure**

Run: `just test tests/test_index.py::test_collect_projects_dedupes_duplicate_filenames`
Expected: FAIL (two wheel entries, no warning)

- [ ] **Step 3: Implement**

Add `import sys` to index.py's imports. In `collect_projects`, add a `seen: set[str] = set()` before the loop and inside the asset loop, after the `project is None` check:

```python
            if asset["name"] in seen:
                print(
                    f"warning: duplicate asset {asset['name']} ignored "
                    f"({asset['browser_download_url']})",
                    file=sys.stderr,
                )
                continue
            seen.add(asset["name"])
```

- [ ] **Step 4: Run tests**

Run: `just test tests/test_index.py` → Expected: all pass

*(Driver checkpoint: commit as "Dedupe duplicate asset filenames across releases")*

---

### Task 4: CLI `--config`

**Goal:** `--config index.yml` drives a multi-repo build; positional `REPO` remains as a one-repo shortcut; exactly one of the two is required.

**Files:**
- Modify: `src/github_releases_pypi/cli.py` (full rewrite of `build`)
- Modify: `tests/test_cli.py` (new tests; existing ones unchanged)

**Acceptance Criteria:**
- [ ] Neither or both of REPO/--config → exit 1 with "provide exactly one of REPO or --config"
- [ ] `--config` with two repos merges both repos' assets into one index; landing shows the config's title
- [ ] `ConfigError` surfaces as `error: <message>`, exit 1
- [ ] URLError message names the specific repo that failed
- [ ] All existing CLI tests pass unchanged

**Verify:** `just test tests/test_cli.py` → all pass

**Steps:**

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_cli.py`:

```python
def config_file(tmp_path, text):
    cfg = tmp_path / "index.yml"
    cfg.write_text(text)
    return cfg


def test_cli_requires_exactly_one_source(tmp_path):
    result = runner.invoke(app, ["--out", str(tmp_path), "--token", "x"])
    assert result.exit_code == 1
    assert "provide exactly one of REPO or --config" in all_output(result)

    cfg = config_file(tmp_path, "repositories: [a/b]\n")
    result = runner.invoke(
        app,
        ["a/b", "--config", str(cfg), "--out", str(tmp_path), "--token", "x"],
    )
    assert result.exit_code == 1
    assert "provide exactly one of REPO or --config" in all_output(result)


def test_cli_config_merges_repositories(tmp_path, monkeypatch):
    second_repo_releases = [
        {
            "tag_name": "v1.0.0",
            "assets": [
                {
                    "name": "otherpkg-1.0.0-py3-none-any.whl",
                    "browser_download_url": "https://github.com/someorg/other/releases/download/v1.0.0/otherpkg-1.0.0-py3-none-any.whl",
                },
            ],
        },
    ]
    releases_by_repo = {
        "bckohan/github-releases-pypi": FIXTURE_RELEASES,
        "someorg/other-project": second_repo_releases,
    }
    monkeypatch.setattr(
        index, "fetch_releases", lambda repo, token: releases_by_repo[repo]
    )
    monkeypatch.setattr(index, "hash_url", lambda url: "cafef00d")
    cfg = config_file(
        tmp_path,
        """
repositories:
  - bckohan/github-releases-pypi
  - someorg/other-project
title: Aggregated Index
""",
    )
    out = tmp_path / "site"
    result = runner.invoke(
        app, ["--config", str(cfg), "--out", str(out), "--token", "x"]
    )
    assert result.exit_code == 0, all_output(result)
    assert "wrote index for 3 project(s)" in result.output
    assert (out / "simple" / "otherpkg" / "index.html").exists()
    assert (out / "simple" / "github-releases-pypi-demo-lib" / "index.html").exists()
    landing = (out / "index.html").read_text()
    assert "Aggregated Index" in landing
    assert "--extra-index-url" not in landing  # no url in config


def test_cli_config_error(tmp_path):
    cfg = config_file(tmp_path, "repositories: []\n")
    result = runner.invoke(
        app, ["--config", str(cfg), "--out", str(tmp_path), "--token", "x"]
    )
    assert result.exit_code == 1
    assert "'repositories' must be a non-empty list" in all_output(result)


def test_cli_config_url_failure_names_repo(tmp_path, monkeypatch):
    import urllib.error

    def boom(repo, token):
        if repo == "someorg/other-project":
            raise urllib.error.URLError("nope")
        return FIXTURE_RELEASES

    monkeypatch.setattr(index, "fetch_releases", boom)
    cfg = config_file(
        tmp_path,
        "repositories: [bckohan/github-releases-pypi, someorg/other-project]\n",
    )
    result = runner.invoke(
        app, ["--config", str(cfg), "--out", str(tmp_path), "--token", "x"]
    )
    assert result.exit_code == 1
    assert "GitHub API request for someorg/other-project failed" in all_output(result)
```

- [ ] **Step 2: Run to verify failure**

Run: `just test tests/test_cli.py` → Expected: new tests FAIL (no `--config` option)

- [ ] **Step 3: Rewrite `cli.py`**

Full new content:

```python
"""Typer command line interface for github-releases-pypi."""

import urllib.error
from pathlib import Path
from typing import Annotated, Optional

import typer

from github_releases_pypi import index
from github_releases_pypi.config import Config, ConfigError, load

app = typer.Typer(add_completion=False)


@app.command()
def build(
    repo: Annotated[
        Optional[str], typer.Argument(help="GitHub repository as OWNER/NAME")
    ] = None,
    out: Annotated[Path, typer.Option(help="Directory to write the index to")] = ...,
    config: Annotated[
        Optional[Path],
        typer.Option("--config", help="YAML config aggregating multiple repositories"),
    ] = None,
    token: Annotated[
        Optional[str],
        typer.Option(envvar="GITHUB_TOKEN", help="GitHub API token"),
    ] = None,
) -> None:
    """Build a PEP 503 package index from GitHub release assets."""
    if (repo is None) == (config is None):
        typer.echo("error: provide exactly one of REPO or --config", err=True)
        raise typer.Exit(1)
    if not token:
        typer.echo("error: provide --token or set GITHUB_TOKEN", err=True)
        raise typer.Exit(1)
    if config is not None:
        try:
            cfg = load(config)
        except ConfigError as error:
            typer.echo(f"error: {error}", err=True)
            raise typer.Exit(1) from error
    else:
        assert repo is not None
        parts = repo.split("/")
        if len(parts) != 2 or not all(parts):
            typer.echo(f"error: repository {repo!r} is not OWNER/NAME", err=True)
            raise typer.Exit(1)
        cfg = Config(
            repositories=(repo,),
            title=f"{repo} package index",
            url=index.pages_url(repo),
        )
    releases = []
    try:
        for current in cfg.repositories:
            releases.extend(index.fetch_releases(current, token))
    except urllib.error.URLError as error:
        typer.echo(f"error: GitHub API request for {current} failed: {error}", err=True)
        raise typer.Exit(1) from error
    try:
        # pass via module attribute so tests can monkeypatch index.hash_url
        projects = index.collect_projects(releases, hash_url=index.hash_url)
    except urllib.error.URLError as error:
        typer.echo(f"error: downloading a release asset failed: {error}", err=True)
        raise typer.Exit(1) from error
    if not projects:
        typer.echo(
            f"error: no package assets found in releases of "
            f"{', '.join(cfg.repositories)}; refusing to build an empty index",
            err=True,
        )
        raise typer.Exit(1)
    index.write_site(
        projects,
        out,
        title=cfg.title,
        index_url=cfg.url.rstrip("/") + "/simple/" if cfg.url else None,
        templates_dir=cfg.templates,
    )
    typer.echo(f"wrote index for {len(projects)} project(s) to {out}")
```

Notes: `Optional[X]` (not `X | None`) — typer's runtime introspection needs it on
Python 3.10; check the file's existing convention and match it. The `out` option
keeps its current required-ness semantics: verify `--out` behaves as before
(`typer.Option(...)` with `= ...` ellipsis default means required — if the
current file uses a different required-option idiom, follow the existing one).

- [ ] **Step 4: Run tests**

Run: `just test tests/test_cli.py` → Expected: all pass (old and new)
Run: `just test` → Expected: whole suite green
Run: `just check-types` → Expected: clean

*(Driver checkpoint: commit as "Add --config for multi-repository indexes")*

---

### Task 5: Docs + changelog + full gate

**Goal:** README documents aggregation and template customization; changelog notes the feature; full check suite green.

**Files:**
- Modify: `README.md` (two new sections after the "Using it in your own repo" section)
- Modify: `doc/source/changelog.rst` (add bullets to the current entry)

**Acceptance Criteria:**
- [ ] README shows a working config example and the template-override contract (override dir, `builtin/` extends, block names, simple_root caveat)
- [ ] `just check-all` → exit 0

**Verify:** `just check-all` → exit 0; `just test` → all pass

**Steps:**

- [ ] **Step 1: README — add after the "Using it in your own repo" numbered list**

```markdown
## Aggregating multiple repositories

To serve one index built from several repositories' releases, pass a YAML
config instead of a repository:

​```yaml
# index.yml
repositories:
  - yourorg/lib-one
  - yourorg/lib-two
title: yourorg package index            # optional
url: https://yourorg.github.io/pypi/    # optional — enables the absolute
                                        # --extra-index-url example on the
                                        # landing page
​```

​```sh
github-releases-pypi --config index.yml --out site
​```

Any wheel or sdist attached to any (non-draft) release on any configured
repository is included. If two repositories publish the same filename, the
first repository in the list wins and a warning is printed.

## Customizing templates

Add a `templates:` directory to the config to override the built-in pages:

​```yaml
templates: ./templates
​```

A file named `landing.html`, `project.html`, or `simple_root.html` in that
directory replaces the built-in template wholesale. To change just part of a
page, extend the built-in under the `builtin/` prefix and override blocks:

​```html
{% extends "builtin/landing.html" %}
{% block footer %}<footer>© yourorg</footer>{% endblock %}
​```

`landing.html` and `project.html` define blocks `title`, `head`, `header`,
`content`, and `footer`. `simple_root.html` defines only `head` — its body is
the PEP 503 anchor list that pip parses, so extend it with care.
```

- [ ] **Step 2: Changelog — extend the current entry in `doc/source/changelog.rst`**

```rst
* Initial release.
* Aggregate releases from multiple repositories via ``--config`` (YAML).
* Template override hooks: a config-specified directory and ``builtin/``-prefixed block inheritance.
```

- [ ] **Step 3: Full gate**

Run: `just check-all` → Expected: exit 0
Run: `just test` → Expected: all pass

*(Driver checkpoint: commit as "Document multi-repository aggregation and template hooks")*

---

## After the plan

Driver: commit the checkpoints (or one squashed commit), then the feature
rides into the next `just release` alongside the unified CalVer flow.
