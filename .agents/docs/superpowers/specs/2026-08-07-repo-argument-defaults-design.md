# Repository Argument Defaults — Design

**Date:** 2026-08-07
**Status:** Approved

## Problem

Building an index for the repository you are already in should take no
arguments. Today it takes two: the positional `REPO` is required (exactly one
of `REPO` or `--config`), and `--out` has no default. A GitHub Pages workflow
must therefore spell out `ghr-pypi "$GITHUB_REPOSITORY" --out site` and repeat
`site` again on the upload step.

`REPO` is also limited to one repository, so indexing three repositories
without a config file is impossible even though `Config.repositories` is
already a tuple.

## Decisions

- **`REPO` becomes variadic** (zero or more), defaulting to
  `$GITHUB_REPOSITORY`.
- **`--out` defaults to `_site`**, which is also
  `actions/upload-pages-artifact`'s default `path`.
- **`repositories` becomes optional in the config file**, so a config kept
  only for `title`/`templates`/`yanked` still works in a Pages workflow.
- **All resolution moves into one pure function**, `_resolve_config`, which
  replaces the four validation branches currently inline in the command body.
  This is the `cli.py` extraction already flagged as a follow-up.

## Resolution

`_resolve_config(repos, config_path, mirror, env_repo)` lives in `cli.py`
(it needs both `config.load` and `index.pages_url`; `config.py` cannot import
`index`). It is pure — the environment is read by the command body and passed
in — and it raises `ConfigError` for every failure, so the command body has a
single `except ConfigError` that echoes `error: {error}` and exits 1.

`ConfigError`'s docstring widens from "the YAML configuration" to cover
configuration from the file, the command line, and the environment.

### With `--config`

1. Explicit `REPO` arguments → `ConfigError`:
   `with --config, list repositories in the config file`
2. `--mirror` → `ConfigError` (unchanged message)
3. `cfg = load(config_path)`
4. `repositories = cfg.repositories or ((env_repo,) if env_repo else ())`
5. Empty → `ConfigError`:
   `{path} has no 'repositories' and GITHUB_REPOSITORY is not set`

### Without `--config`

1. `repositories = tuple(repos) or ((env_repo,) if env_repo else ())`
2. Empty → `ConfigError`:
   `provide REPO..., set GITHUB_REPOSITORY, or use --config`
3. Each must be `OWNER/NAME` with both parts non-empty. A bad explicit
   argument reports `repository {value!r} is not OWNER/NAME`; a bad
   environment value names its source:
   `GITHUB_REPOSITORY {value!r} is not OWNER/NAME`
4. Case-insensitive duplicates → `repository {value!r} given more than once`
   (the config file already rejects duplicates; the CLI now matches)
5. Build a `Config` with the derived `title` and `url` below, plus `mirror`.

`$GITHUB_REPOSITORY` is the last fallback in both branches and therefore never
conflicts with anything the user typed. This matters: the variable is always
set inside GitHub Actions, so treating it as a conflict would break every
config-file user in CI. An empty-string value counts as unset.

## Title and URL

`url` has a real unset state (`None`), so it is derived whenever the config did
not set it:

```
url = cfg.url                      if the config set it
    | pages_url(env_repo)          if $GITHUB_REPOSITORY is set        (both branches)
    | pages_url(repositories[0])   if exactly one repository resolved  (no-config branch only)
    | None
```

`env_repo` outranks the resolved repository because that repository is the
Pages host, even when the assets being indexed live elsewhere.

The single-repository fallback is deliberately restricted to the command line
form (amendment, found in review: applying it to the config branch as well
would have changed existing behavior). A config file that lists one repository
and omits `url` has always meant "no install example on the landing page", and
a repository listed there is not necessarily the one serving the site.

`title` keeps its existing `"Package index"` default on `Config`, so it is
derived only in the no-config branch: `f"{repo} package index"` when exactly
one repository resolved, `"Package index"` otherwise. Deriving it in the config
branch as well would require giving `Config.title` a `None` state purely to
detect "unset", and a config author can simply write `title:`.

## Config file change

`repositories` becomes optional. When present it must still be a non-empty list
of valid, non-duplicate `OWNER/NAME` strings — the existing validation and its
messages are unchanged. When absent, `Config.repositories` defaults to `()`.

`Config.repositories` gains a default of `()`. It is currently the only field
without a default, so it stays in place and no field order changes.

## CLI surface

```
ghr-pypi [REPO...] [--config PATH] [--out DIR] [--token TOKEN] [--mirror]
```

- `REPO...`: `list[str] | None = None`, help "GitHub repositories as
  OWNER/NAME; defaults to $GITHUB_REPOSITORY (omit when using --config)"
- `--out`: defaults to `Path("_site")`

The environment is read in the command body as
`os.environ.get("GITHUB_REPOSITORY")` — not as a Typer `envvar=` default — so
resolution stays explicit and testable, and so the value is read at call time
rather than at import.

## Testing

**`GITHUB_REPOSITORY` is set inside GitHub Actions.** Without isolation, every
"no repositories resolved" test would silently pass in CI for the wrong reason.
`tests/conftest.py` gains an autouse fixture that does
`monkeypatch.delenv("GITHUB_REPOSITORY", raising=False)`; tests that want the
variable set it themselves.

`_resolve_config` is pure, so the precedence matrix is unit-tested directly
without `CliRunner`:

- no config, no args, no env → error
- no config, no args, env set → that repository; `url` and `title` derived
  from it
- no config, two args → both repositories, `title` is `"Package index"`,
  `url` is `None` (no env) and `pages_url(env)` (with env)
- no config, one arg + a *different* env value → the argument is indexed, the
  URL points at the env repository
- config with `repositories` + env set → config wins, no error
- config with `repositories` + explicit args → error
- config without `repositories` + env → env repository
- config without `repositories`, no env → error
- config setting `url` + env set → config's `url` survives
- malformed argument, malformed env value, duplicate arguments → the three
  distinct messages
- `--mirror` with `--config` → unchanged error

End-to-end through `CliRunner`: a bare invocation with `GITHUB_REPOSITORY` set
and no `--out` writes a site into `_site`.

## Workflow and docs

`.github/workflows/pages.yml` drops both arguments and the upload step's
`with: path:`, since `_site` is that action's default — the repository
demonstrates the zero-argument path it documents.

Updated: `doc/source/reference/cli.rst`, `doc/source/reference/configuration.rst`
(`repositories` optional), `doc/source/how-to/build-failed.rst` (the
`exactly one of REPO or --config` entry is replaced by the new messages),
`doc/source/tutorials/github-pages.rst`, `README.md`, `doc/source/changelog.rst`.

## Out of scope

- Reading other GitHub Actions variables (`GITHUB_TOKEN` is already an
  `envvar` on `--token`).
- Organization-wide repository discovery, and merging CLI repositories with
  config repositories — both remain future items in `direction.md`.
