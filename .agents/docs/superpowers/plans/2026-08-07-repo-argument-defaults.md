# Repository Argument Defaults Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers-extended-cc:subagent-driven-development (recommended) or superpowers-extended-cc:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **PROJECT RULE (AGENTS.md):** agents never commit or push — the human driver
> does. Implementers stop at "verified in working tree".

**Goal:** `ghr-pypi` with no arguments builds the current repository's index into `_site`, so a GitHub Pages workflow needs no arguments at all.

**Architecture:** `REPO` becomes variadic and falls back to `$GITHUB_REPOSITORY`; `--out` defaults to `_site`; `repositories` becomes optional in the config file. All of the precedence logic moves out of the Typer command body into one pure function, `_resolve_config`, which raises `ConfigError` for every failure so the command body has a single error path.

**Spec:** `.agents/docs/superpowers/specs/2026-08-07-repo-argument-defaults-design.md`

**Context for the implementer:**
- Current suite: 203 tests green, `just check-all` exit 0. The tree carries a
  large amount of uncommitted work (rename, dynamic versioning, docs manual,
  yank/exclude) — touch only your task's files.
- **Do not run `just test-all <path>`.** It splices arguments into `uv run`'s
  flag position and destroys the project venv. Use `just test` (whole suite) or
  `uv run pytest <path>`.
- `config.py` must not import `index.py` (`index` imports `config` — cycle).
  That is why `_resolve_config` lives in `cli.py`: it needs both `config.load`
  and `index.pages_url`.
- doc8 max line length is 100 for RST. `just check-docs` must stay green.
- Read `src/ghr_pypi/cli.py` and `src/ghr_pypi/config.py` before writing; the
  code wins over this plan if they disagree.

---

### Task 1: `repositories` becomes optional in the config file

**Goal:** A config file may omit `repositories`; when present it is validated exactly as before.

**Files:**
- Modify: `src/ghr_pypi/config.py:134` (dataclass field), `src/ghr_pypi/config.py:249-257` (validation)
- Modify: `tests/test_config.py`

**Acceptance Criteria:**
- [ ] `Config.repositories` defaults to `()`; field order is unchanged
- [ ] A config with only `title:` loads and yields `repositories == ()`
- [ ] `repositories: []` still raises `'repositories' must be a non-empty list`
- [ ] `repositories: "a/b"` (a string, not a list) still raises the same error
- [ ] A malformed entry still raises `repository 'x' is not OWNER/NAME`
- [ ] Duplicates still raise `'repositories' contains duplicates`

**Verify:** `uv run pytest tests/test_config.py -q` → all pass; `just check-types` clean

**Steps:**

- [ ] **Step 1: Write the failing test.** Add to `tests/test_config.py`:

```python
def test_repositories_may_be_omitted(tmp_path):
    cfg = tmp_path / "index.yml"
    cfg.write_text("title: Just a title\n")
    loaded = load(cfg)
    assert loaded.repositories == ()
    assert loaded.title == "Just a title"


def test_empty_repositories_list_still_rejected(tmp_path):
    cfg = tmp_path / "index.yml"
    cfg.write_text("repositories: []\n")
    with pytest.raises(ConfigError, match="must be a non-empty list"):
        load(cfg)
```

Match the file's existing import style — it already imports `load`, `ConfigError` and `pytest`; do not add duplicate imports.

- [ ] **Step 2: Run it and confirm the first test fails.**

Run: `uv run pytest tests/test_config.py -q`
Expected: `test_repositories_may_be_omitted` FAILS with
`ConfigError: ...: 'repositories' must be a non-empty list`.

- [ ] **Step 3: Give the field a default.** In `src/ghr_pypi/config.py`, inside `class Config`:

```python
    repositories: tuple[str, ...] = ()
```

It is currently the only field without a default, so it stays first and no
other field moves.

- [ ] **Step 4: Make the key optional in `load`.** Replace the block at `src/ghr_pypi/config.py:249-257`:

```python
    repositories = raw.get("repositories")
    if repositories is None:
        # optional: the CLI falls back to its arguments or $GITHUB_REPOSITORY
        repositories = []
    else:
        if not isinstance(repositories, list) or not repositories:
            raise ConfigError(f"{path}: 'repositories' must be a non-empty list")
        for repo in repositories:
            parts = repo.split("/") if isinstance(repo, str) else []
            if len(parts) != 2 or not all(parts):
                raise ConfigError(f"{path}: repository {repo!r} is not OWNER/NAME")
        if len({r.casefold() for r in repositories}) != len(repositories):
            raise ConfigError(f"{path}: 'repositories' contains duplicates")
```

Leave the `repositories=tuple(repositories)` in the `Config(...)` construction
at the end of `load` untouched.

- [ ] **Step 5: Verify.**

Run: `uv run pytest tests/test_config.py -q` → all pass
Run: `just test` → report the total count
Run: `just fix` then `just check-types` → clean

*(Driver checkpoint: commit as "Make config repositories optional")*

---

### Task 2: `_resolve_config`, variadic `REPO`, `--out` default

**Goal:** Zero-argument invocation resolves the repository from `$GITHUB_REPOSITORY` and writes to `_site`; every precedence and validation rule is unit-testable without `CliRunner`.

**Files:**
- Modify: `src/ghr_pypi/cli.py`
- Modify: `src/ghr_pypi/config.py` (the `ConfigError` docstring only)
- Modify: `tests/conftest.py`, `tests/test_cli.py`

**Acceptance Criteria:**
- [ ] `tests/conftest.py` has an autouse fixture deleting `GITHUB_REPOSITORY`
- [ ] `_resolve_config` is pure (environment passed in, never read) and raises `ConfigError` for every failure
- [ ] Precedence: config's `repositories` → explicit `REPO` args → `$GITHUB_REPOSITORY`
- [ ] Explicit `REPO` args together with `--config` → error; `$GITHUB_REPOSITORY` together with `--config` → no error
- [ ] `url` is derived from `$GITHUB_REPOSITORY` when the config did not set one, in both branches
- [ ] `title` is derived only in the no-config branch
- [ ] `--out` defaults to `_site`
- [ ] Existing CLI tests still pass

**Verify:** `just test` → all pass (report count)

**Steps:**

- [ ] **Step 1: Isolate the environment.** Add to `tests/conftest.py` (the file
  already imports `pytest`; add the fixture at module level, after the existing
  `pytest_addoption`):

```python
@pytest.fixture(autouse=True)
def _no_github_repository(monkeypatch):
    """GitHub Actions sets GITHUB_REPOSITORY for every step, including the test
    run. Unset it so only tests that opt in exercise the CLI's fallback —
    otherwise the "no repositories resolved" cases would pass in CI for the
    wrong reason."""
    monkeypatch.delenv("GITHUB_REPOSITORY", raising=False)
```

- [ ] **Step 2: Write the failing tests.** In `tests/test_cli.py`, add these
  imports alongside the existing ones:

```python
import pytest

from ghr_pypi.cli import _resolve_config, app
from ghr_pypi.config import ConfigError
```

Delete `test_cli_requires_exactly_one_source` (its message is being replaced)
and add:

```python
def resolve(repos=None, config=None, *, mirror=False, env_repo=None):
    return _resolve_config(repos, config, mirror=mirror, env_repo=env_repo)


def test_resolve_needs_a_source():
    with pytest.raises(ConfigError, match="provide REPO"):
        resolve()


def test_resolve_falls_back_to_the_environment():
    cfg = resolve(env_repo="bckohan/ghr-pypi")
    assert cfg.repositories == ("bckohan/ghr-pypi",)
    assert cfg.title == "bckohan/ghr-pypi package index"
    assert cfg.url == "https://bckohan.github.io/ghr-pypi/"


def test_resolve_empty_environment_variable_counts_as_unset():
    with pytest.raises(ConfigError, match="provide REPO"):
        resolve(env_repo="")


def test_resolve_several_repositories():
    cfg = resolve(["a/one", "a/two"])
    assert cfg.repositories == ("a/one", "a/two")
    assert cfg.title == "Package index"
    assert cfg.url is None


def test_resolve_url_comes_from_the_pages_host():
    cfg = resolve(["a/one", "a/two"], env_repo="host/site")
    assert cfg.repositories == ("a/one", "a/two")
    assert cfg.url == "https://host.github.io/site/"


def test_resolve_arguments_outrank_the_environment():
    cfg = resolve(["a/one"], env_repo="host/site")
    assert cfg.repositories == ("a/one",)
    assert cfg.url == "https://host.github.io/site/"


def test_resolve_rejects_a_bad_argument():
    with pytest.raises(ConfigError, match="repository 'nope' is not OWNER/NAME"):
        resolve(["nope"])


def test_resolve_rejects_a_bad_environment_value():
    with pytest.raises(
        ConfigError, match="GITHUB_REPOSITORY 'nope' is not OWNER/NAME"
    ):
        resolve(env_repo="nope")


def test_resolve_rejects_duplicate_arguments():
    with pytest.raises(ConfigError, match="given more than once"):
        resolve(["a/one", "A/One"])


def test_resolve_config_repositories_win(tmp_path):
    cfg_file = config_file(tmp_path, "repositories: [a/one]\n")
    cfg = resolve(config=cfg_file, env_repo="host/site")
    assert cfg.repositories == ("a/one",)
    assert cfg.url == "https://host.github.io/site/"


def test_resolve_rejects_arguments_beside_a_config(tmp_path):
    cfg_file = config_file(tmp_path, "repositories: [a/one]\n")
    with pytest.raises(ConfigError, match="list repositories in the config file"):
        resolve(["a/two"], cfg_file)


def test_resolve_config_without_repositories_uses_the_environment(tmp_path):
    cfg_file = config_file(tmp_path, "title: Mine\n")
    cfg = resolve(config=cfg_file, env_repo="host/site")
    assert cfg.repositories == ("host/site",)
    assert cfg.title == "Mine"


def test_resolve_config_without_repositories_and_no_environment(tmp_path):
    cfg_file = config_file(tmp_path, "title: Mine\n")
    with pytest.raises(ConfigError, match="has no 'repositories'"):
        resolve(config=cfg_file)


def test_resolve_keeps_the_configured_url(tmp_path):
    cfg_file = config_file(
        tmp_path, "repositories: [a/one]\nurl: https://example.com/pypi/\n"
    )
    cfg = resolve(config=cfg_file, env_repo="host/site")
    assert cfg.url == "https://example.com/pypi/"


def test_resolve_rejects_mirror_beside_a_config(tmp_path):
    cfg_file = config_file(tmp_path, "repositories: [a/one]\n")
    with pytest.raises(ConfigError, match="set 'mirror' in the config file"):
        resolve(config=cfg_file, mirror=True)


def test_cli_defaults_repository_and_out(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GITHUB_REPOSITORY", "bckohan/ghr-pypi")
    monkeypatch.setattr(index, "fetch_releases", fetch_stub(FIXTURE_RELEASES))
    monkeypatch.setattr(index, "hash_url", lambda url: "cafef00d")
    result = runner.invoke(app, ["--token", "x"])
    assert result.exit_code == 0, all_output(result)
    assert (tmp_path / "_site" / "simple" / "index.html").exists()
```

`config_file` is the existing helper further down the file; move the new tests
below it, or move `config_file` above them — either is fine, but the module
must define it before use at call time (it is a plain function, so definition
order in the file does not matter for pytest; keep them grouped for
readability).

- [ ] **Step 3: Run them and confirm they fail.**

Run: `uv run pytest tests/test_cli.py -q`
Expected: the `test_resolve_*` tests FAIL with
`ImportError: cannot import name '_resolve_config' from 'ghr_pypi.cli'`.

- [ ] **Step 4: Implement `_resolve_config`.** In `src/ghr_pypi/cli.py`, replace
  the imports and add the two functions above `app = typer.Typer(...)`:

```python
"""Typer command line interface for ghr-pypi."""

import os
import urllib.error
from dataclasses import replace
from pathlib import Path
from typing import Annotated

import typer

from ghr_pypi import index
from ghr_pypi.config import Config, ConfigError, load

app = typer.Typer(add_completion=False)


def _check_slug(value: str, source: str) -> None:
    """Raise ``ConfigError`` unless ``value`` is an ``OWNER/NAME`` slug."""
    parts = value.split("/")
    if len(parts) != 2 or not all(parts):
        raise ConfigError(f"{source} is not OWNER/NAME")


def _resolve_config(
    repos: list[str] | None,
    config_path: Path | None,
    *,
    mirror: bool,
    env_repo: str | None,
) -> Config:
    """Resolve the build configuration from the command line and environment.

    ``env_repo`` is ``$GITHUB_REPOSITORY``; an empty value counts as unset. It
    is the last fallback in both branches and never conflicts with anything the
    user typed: GitHub Actions sets it for every step, so treating it as a
    conflict would break every config file user in CI. It is validated whenever
    it is set, because it is also the source of the GitHub Pages URL.
    """
    env_repo = env_repo or None
    if env_repo is not None:
        _check_slug(env_repo, f"GITHUB_REPOSITORY {env_repo!r}")
    given = list(repos or [])
    if config_path is not None:
        if given:
            raise ConfigError("with --config, list repositories in the config file")
        if mirror:
            raise ConfigError("with --config, set 'mirror' in the config file")
        cfg = load(config_path)
        repositories = cfg.repositories
        if not repositories:
            if env_repo is None:
                raise ConfigError(
                    f"{config_path} has no 'repositories' and "
                    "GITHUB_REPOSITORY is not set"
                )
            repositories = (env_repo,)
    else:
        seen: set[str] = set()
        for repo in given:
            _check_slug(repo, f"repository {repo!r}")
            if repo.casefold() in seen:
                raise ConfigError(f"repository {repo!r} given more than once")
            seen.add(repo.casefold())
        if given:
            repositories = tuple(given)
        elif env_repo is not None:
            repositories = (env_repo,)
        else:
            raise ConfigError(
                "provide REPO..., set GITHUB_REPOSITORY, or use --config"
            )
        cfg = Config(
            repositories=repositories,
            title=(
                f"{repositories[0]} package index"
                if len(repositories) == 1
                else "Package index"
            ),
            mirror=mirror,
        )
    url = cfg.url
    if url is None:
        if env_repo is not None:
            url = index.pages_url(env_repo)
        elif len(repositories) == 1:
            url = index.pages_url(repositories[0])
    return replace(cfg, repositories=repositories, url=url)
```

- [ ] **Step 5: Rewrite the command signature and its first lines.** Replace
  `src/ghr_pypi/cli.py` lines 15-76 (the `@app.command()` decorator through the
  end of the `else:` block that builds `Config`) with:

```python
@app.command()
def build(
    repos: Annotated[
        list[str] | None,
        typer.Argument(
            metavar="[REPO]...",
            help="GitHub repositories as OWNER/NAME; defaults to "
            "$GITHUB_REPOSITORY (omit when using --config)",
        ),
    ] = None,
    out: Annotated[
        Path, typer.Option(help="Directory to write the index to")
    ] = Path("_site"),
    config: Annotated[
        Path | None,
        typer.Option(
            "--config",
            help=(
                "YAML config aggregating multiple repositories "
                "(list the repositories in it, not on the command line)"
            ),
        ),
    ] = None,
    token: Annotated[
        str | None,
        typer.Option(envvar="GITHUB_TOKEN", help="GitHub API token"),
    ] = None,
    mirror: Annotated[
        bool,
        typer.Option(
            "--mirror",
            help="Download assets into the site instead of linking to GitHub "
            "(with --config, set 'mirror' in the config file instead)",
        ),
    ] = False,
) -> None:
    """Build a PEP 503 package index from GitHub release assets."""
    if not token:
        typer.echo("error: provide --token or set GITHUB_TOKEN", err=True)
        raise typer.Exit(1)
    try:
        cfg = _resolve_config(
            repos,
            config,
            mirror=mirror,
            env_repo=os.environ.get("GITHUB_REPOSITORY"),
        )
    except ConfigError as error:
        typer.echo(f"error: {error}", err=True)
        raise typer.Exit(1) from error
```

Everything from `releases = []` onward is unchanged. The token check stays
first, as `doc/source/how-to/build-failed.rst` documents ("checked before
anything else, so it masks other problems until you fix it").

- [ ] **Step 6: Widen the `ConfigError` docstring.** It now covers command line
  and environment failures too. In `src/ghr_pypi/config.py`:

```python
class ConfigError(ValueError):
    """Raised when the build configuration is missing or invalid.

    Covers the YAML file as well as the command line arguments and environment
    that ``cli._resolve_config`` folds into a :class:`Config`.
    """
```

- [ ] **Step 7: Verify.**

Run: `uv run pytest tests/test_cli.py -q` → all pass
Run: `just test` → report the total count
Run: `just fix` then `just check-types` → clean

- [ ] **Step 8: Prove the wiring is live.** Temporarily change the `--out`
  default to `Path("site")` and confirm `test_cli_defaults_repository_and_out`
  fails; then temporarily delete the `elif env_repo is not None:` branch in the
  no-config path and confirm `test_resolve_falls_back_to_the_environment`
  fails. Revert both. Report both results — a test that stays green under
  mutation is not testing anything.

*(Driver checkpoint: commit as "Default the repository argument to $GITHUB_REPOSITORY")*

---

### Task 3: Workflow, docs, full gate

**Goal:** The repository's own Pages workflow uses the zero-argument form, and every document describing the old contract is corrected.

**Files:**
- Modify: `.github/workflows/pages.yml`, `README.md`, `direction.md`
- Modify: `doc/source/reference/cli.rst`, `doc/source/reference/configuration.rst`, `doc/source/how-to/build-failed.rst`, `doc/source/tutorials/github-pages.rst`, `doc/source/changelog.rst`

**Acceptance Criteria:**
- [ ] `pages.yml` runs the CLI with no arguments and the upload step has no `with: path:`
- [ ] No document still says "exactly one of REPO or --config"
- [ ] `cli.rst` documents the variadic `REPO`, the `$GITHUB_REPOSITORY` fallback, and `--out`'s `_site` default
- [ ] `configuration.rst` shows `repositories` as optional and explains the fallback
- [ ] `build-failed.rst` lists the four new error messages
- [ ] The two implemented bullets are removed from `direction.md`
- [ ] `just check-all` → exit 0

**Verify:** `just check-all > /tmp/gate.log 2>&1; echo EXIT=$?` → `EXIT=0`

**Steps:**

- [ ] **Step 1: `.github/workflows/pages.yml`.** Replace the build step's
  comment and `run:`, and drop the upload step's `with:` block:

```yaml
      # Runs the ghr-pypi CLI from this repo's own source — the repo
      # dogfoods the tool it publishes. Other repos would use:
      #   uvx ghr-pypi
      # With no arguments it indexes $GITHUB_REPOSITORY into _site, which is
      # also upload-pages-artifact's default path.
      - name: Build the package index
        env:
          GITHUB_TOKEN: ${{ github.token }}
        run: uv run --locked --no-default-groups ghr-pypi

      # Fails fast with a clear error if Pages isn't enabled for this repo.
      - uses: actions/configure-pages@45bfe0192ca1faeb007ade9deae92b16b8254a0d # v6.0.0

      - uses: actions/upload-pages-artifact@fc324d3547104276b827a68afc52ff2a11cc49c9 # v5.0.0
```

Keep the existing pinned SHAs exactly as they are in the file — copy them from
the file rather than from this plan.

- [ ] **Step 2: `doc/source/reference/cli.rst`.** Four edits.

Synopsis:

```rst
.. code-block:: text

   ghr-pypi [REPO]... [--out DIRECTORY] [--config PATH] [--token TOKEN] [--mirror]
```

The invocation examples below it:

```rst
   uvx ghr-pypi
   python -m pip install ghr-pypi && ghr-pypi yourorg/yourrepo --out site
```

Replace the "Invocation forms" opening paragraph and the "Single repository"
section with:

```rst
Invocation forms
================

Repositories come from the first of these that yields any: the ``repositories``
key of a ``--config`` file, the positional ``REPO`` arguments, or the
``GITHUB_REPOSITORY`` environment variable. If none of them does, the command
exits 1.

No arguments
------------

.. code-block:: sh

   ghr-pypi

Inside GitHub Actions this is the whole invocation: ``GITHUB_REPOSITORY`` names
the repository being built and ``--out`` defaults to ``_site``, which is also
the directory ``actions/upload-pages-artifact`` uploads by default.

One or more repositories
------------------------

.. code-block:: sh

   ghr-pypi yourorg/yourrepo --out site
   ghr-pypi yourorg/lib-one yourorg/lib-two --out site

Each argument is a bare ``OWNER/NAME`` slug — not a URL, not a clone path —
and repeating one (ignoring case) is an error. In this form the remaining
settings take their defaults, except:

* the landing page title becomes ``yourorg/yourrepo package index`` when
  exactly one repository is resolved, and ``Package index`` otherwise;
* the index URL advertised on the landing page is the GitHub Pages URL of
  ``GITHUB_REPOSITORY`` when that is set — the repository running the build is
  the one serving the site, even when it is indexing someone else's assets —
  falling back to the single resolved repository's Pages URL, and to nothing at
  all when several repositories were given outside Actions. The owner is
  lower-cased; the repository name is used as given.

``--mirror`` is the only behavioral switch available here; everything else
requires a configuration file.
```

In the "Configuration file" section, replace the sentence beginning
"``--mirror`` is rejected in this form" — keep it, but change the preceding
mutual-exclusion wording to:

```rst
Required for indexing more than one repository from a fixed list, and the only
way to set ``title``, ``url``, ``templates``, ``formats``, ``missing_digest``,
or ``metadata``. See :ref:`configuration` for every key. Repositories must be
listed in the file, not on the command line — passing both is an error, though
``GITHUB_REPOSITORY`` may be set alongside a config file and is used only when
the file omits ``repositories``. ``--mirror`` is rejected in this form — set
``mirror: true`` in the file instead, so that the file remains the whole
description of the build.
```

And in "Options", replace the ``--out``, ``REPO`` and ``--config`` entries:

```rst
``--out DIRECTORY``
   Where the site is written. Defaults to ``_site``, matching
   ``actions/upload-pages-artifact``. The directory and its parents are created
   if they do not exist. Existing files are overwritten; nothing is deleted, so
   stale projects or mirrored files from a previous build survive unless you
   clear the directory first.

``REPO...``
   Zero or more repositories to index, each as ``OWNER/NAME``. Defaults to the
   ``GITHUB_REPOSITORY`` environment variable. Must not be combined with
   ``--config``.

``--config PATH``
   Path to the YAML configuration file. Its ``repositories`` key replaces the
   positional arguments, which must then be omitted. Relative paths in the file
   (``templates``) resolve against the file's own directory, not the working
   directory.
```

Finally, in the ``GITHUB_TOKEN`` section, change the Actions example's
``run:`` line to ``run: uvx ghr-pypi``.

- [ ] **Step 3: `doc/source/reference/configuration.rst`.** Replace the two
  opening paragraphs (lines 9-18) with:

```rst
``ghr-pypi`` can be driven from the command line alone — repositories as
positional arguments, or none at all, falling back to the
``GITHUB_REPOSITORY`` environment variable — or with a YAML configuration file
given with ``--config``. Repositories may not be given both ways at once (see
:ref:`cli`).

The configuration file is the only way to aggregate a fixed list of
repositories into one index, and the only way to set ``title``, ``url``,
``templates``, ``formats``, ``missing_digest``, ``metadata``, ``mirror``,
``yanked``, or ``exclude``. The command line form supports ``--mirror`` and
otherwise uses the defaults listed below, with ``title`` set to
``"<OWNER/NAME> package index"`` when exactly one repository is resolved and
``url`` set to a GitHub Pages URL (``https://<owner>.github.io/<name>/``).
```

In the summary table, change the ``repositories`` row's Default cell from
``*required*`` to ``*optional*`` and its Notes cell to
``When present: non-empty, no case-insensitive duplicates``.

In the ``repositories`` key subsection, replace the field list and add a
paragraph after it:

```rst
:Type: list of strings
:Default: none — falls back to the positional ``REPO`` arguments, then to
          ``$GITHUB_REPOSITORY``
:Constraints: When present, must be a non-empty list. Every entry must be a
              string of exactly two non-empty, ``/``-separated parts
              (``OWNER/NAME``). Entries must be unique when compared
              case-insensitively.

Omitting the key is useful when the file exists only to set ``title``,
``templates`` or ``yanked`` for the repository the build is running in: inside
GitHub Actions ``GITHUB_REPOSITORY`` supplies the repository. If the key is
absent and ``GITHUB_REPOSITORY`` is unset, the build fails rather than
producing an empty index.
```

The three validation-error entries around line 440 keep their messages; add
"(only checked when the key is present)" to the
``'repositories' must be a non-empty list`` entry's explanation.

- [ ] **Step 4: `doc/source/how-to/build-failed.rst`.** Replace the
  ``error: provide exactly one of REPO or --config`` entry with:

```rst
``error: provide REPO..., set GITHUB_REPOSITORY, or use --config``
   No repositories were resolved. Pass one or more ``OWNER/NAME`` arguments,
   run inside GitHub Actions (which sets ``GITHUB_REPOSITORY``), or supply a
   config file that lists them.

``error: with --config, list repositories in the config file``
   Positional arguments and ``--config`` are mutually exclusive. Move the
   repositories into the file's ``repositories`` key. ``GITHUB_REPOSITORY``
   does not trigger this — it is used only when the file omits the key.

``error: <path> has no 'repositories' and GITHUB_REPOSITORY is not set``
   The config file omits ``repositories`` and there is nothing to fall back to.
   Add the key, or pass the repository in the environment.

``error: GITHUB_REPOSITORY 'x' is not OWNER/NAME``
   The environment variable is malformed. It is validated whenever it is set,
   even when the repositories come from elsewhere, because it also supplies the
   GitHub Pages URL.

``error: repository 'x' given more than once``
   The same repository was passed twice on the command line (the comparison
   ignores case).
```

- [ ] **Step 5: `doc/source/tutorials/github-pages.rst`.** In the workflow
  listing, change the build step to ``run: uvx ghr-pypi`` and delete the
  ``with:``/``path: site`` lines under ``actions/upload-pages-artifact@v5``.
  Then reread the surrounding prose and fix any sentence that still tells the
  reader to pass the repository or the output directory.

- [ ] **Step 6: `README.md`.** In the "Using it in your own repo" workflow
  snippet:

```yaml
   - uses: astral-sh/setup-uv@v5
   - name: Build the package index
     env:
       GITHUB_TOKEN: ${{ github.token }}
     run: uvx ghr-pypi
   - uses: actions/upload-pages-artifact@v3
```

Add one sentence under it: "With no arguments it indexes `$GITHUB_REPOSITORY`
into `_site`, which is also what `upload-pages-artifact` uploads by default."
Keep lines short — this region is inside the `<!-- docs-index-start -->`
markers and is included verbatim into `doc/source/index.rst`.

- [ ] **Step 7: `doc/source/changelog.rst`.** Add to the `2026.8.X` section,
  below the existing `* Support yank/exclude.` bullet:

```rst
* The positional ``REPO`` argument takes zero or more repositories and defaults
  to ``$GITHUB_REPOSITORY``; ``--out`` defaults to ``_site`` and the config
  file's ``repositories`` key is optional. A GitHub Pages workflow can now run
  ``ghr-pypi`` with no arguments.
```

- [ ] **Step 8: `direction.md`.** Delete the two now-implemented bullets — the
  one beginning "Set repository CLI argument to 0-many" and the one beginning
  "Set the --out default to _site". Leave the remaining bullets untouched.

- [ ] **Step 9: Gate.**

Run: `just fix`
Run: `just test` → report the count
Run: `just check-all > /tmp/gate.log 2>&1; echo EXIT=$?` → `EXIT=0`

Fix any linkcheck failure by correcting the URL — never by disabling
linkcheck. Then grep the tree to prove nothing stale survives:

```bash
grep -rn "exactly one of REPO" --include='*.rst' --include='*.md' --include='*.py' . | grep -v '^\./\.agents/'
```

Expected: no output.

*(Driver checkpoint: commit as "Default the CLI to GITHUB_REPOSITORY and _site")*

---

## After the plan

Driver: commit the checkpoints. A Pages workflow is now three lines — install
uv, run `ghr-pypi`, upload — with no arguments repeated between them.
