# Multi-Repo Config + Template Hooks — Design

**Date:** 2026-08-05
**Status:** Approved

## Problem

The tool builds a package index from ONE repository's releases, and the three
Jinja templates are baked into the package. Users should be able to:

1. Aggregate: any wheel/sdist found in any release on a set of **configured
   repositories** is included in one merged index.
2. Customize: override the Jinja templates — wholesale or by extending
   well-defined blocks.

(Scope note: the unified CalVer release flow shipped earlier today concerns
only this repository's own three packages; it is unrelated to this feature.)

## Decisions

- **YAML configuration**, aggregator model: config lists N repositories, one
  merged index.
- **CLI:** `--config PATH` added; existing positional `OWNER/NAME` kept as a
  no-config shortcut. Exactly one of the two is required.
- **Template hooks:** an override directory (checked first) AND named blocks
  in the built-in templates, which stay reachable under a `builtin/` prefix
  for `{% extends %}`.
- **Implementation approach A:** plain frozen dataclass + hand-rolled
  validation in a new `config.py`; `pyyaml` becomes a runtime dependency.
  (Rejected: threading individual parameters — signature churn; pydantic —
  heavyweight for a four-key config.)

## Section 1 — Config schema and loading

New module `src/github_releases_pypi/config.py`.

```yaml
# index.yml
repositories:            # required, non-empty list of OWNER/NAME strings
  - bckohan/github-releases-pypi
  - someorg/other-project
templates: ./templates   # optional — template override directory
title: My Package Index  # optional — landing page heading
url: https://bckohan.github.io/github-releases-pypi/  # optional — index base URL
```

- `Config` frozen dataclass: `repositories: tuple[str, ...]`,
  `templates: Path | None`, `title: str`, `url: str | None`.
- `load(path: Path) -> Config` via `yaml.safe_load`. Explicit `ConfigError`
  (ValueError subclass) messages for: file unreadable / not a mapping;
  `repositories` missing, empty, or containing a non-`owner/name` string;
  `templates` directory nonexistent; `url` not https; unknown top-level keys
  (typo guard).
- Relative `templates` resolves against the config file's parent directory,
  not the CWD.
- `title` defaults to `"Package index"`. `url` may be omitted: the landing
  page then renders only the relative `simple/` link and omits the absolute
  `--index-url` example.
- `pyyaml` added to `[project] dependencies`.

## Section 2 — CLI

`build(repo?, --config?, --out, --token)`:

- Exactly one of positional `REPO` / `--config` (typer error otherwise).
- Shortcut normalization: `REPO` → `Config(repositories=(repo,),
  templates=None, title=f"{repo} package index", url=pages_url(repo))` —
  downstream code has a single path.
- One `--token` (or `GITHUB_TOKEN`) authenticates every fetch. Public repos
  work with any valid token; private repos need a token with read access to
  all configured repos.
- Existing behaviors preserved: refuse to build an empty index; URLError →
  clear error naming the failing repo.

## Section 3 — Index building (multi-repo merge)

- `fetch_releases(repo, token)` unchanged; the CLI loops configured repos and
  concatenates the release lists. `collect_projects` already merges assets
  across releases, so aggregation needs no structural change.
- **Duplicate filename policy:** if two repos ship the same filename, the
  first repo in config order wins; later duplicates are skipped with a
  stderr warning (a PEP 503 project page must not list one filename twice).
  Dedupe happens in `collect_projects` (filename-keyed check at append
  time), so release-order precedence within one repo is unaffected.
- `write_site(projects, out_dir, repo)` →
  `write_site(projects, out_dir, *, title: str, index_url: str | None)`.
  `pages_url()` stays (used by the CLI shortcut normalization).

## Section 4 — Template environment and blocks

- Module-global `_env` replaced by `build_env(templates_dir: Path | None) ->
  Environment`:
  - loader = `ChoiceLoader([FileSystemLoader(templates_dir)] if set,
    PrefixLoader({"builtin": PackageLoader(...)}), PackageLoader(...))`
  - Same autoescape/keep_trailing_newline settings as today.
- Override semantics: a file named `landing.html` / `project.html` /
  `simple_root.html` in the override dir replaces that template wholesale;
  or it can `{% extends "builtin/<name>.html" %}` and override blocks only
  (the prefix avoids self-recursion).
- Blocks added to built-ins:
  - `landing.html`, `project.html`: `title`, `head` (style/meta), `header`
    (h1/intro), `content` (main listing), `footer`.
  - `simple_root.html`: `head` only — the body is the PEP 503 anchor list
    and must remain machine-parseable (documented in README).
- Rendering output for default templates must remain byte-identical to
  today's output except where blocks require inert markers (block tags emit
  nothing by themselves); existing golden assertions in tests keep passing
  unchanged where signatures allow.

## Section 5 — Tests, docs, dogfooding

- New tests: config load happy path + every validation error; CLI `--config`
  / mutual exclusion / neither-given error; multi-repo merge incl.
  duplicate-filename dedupe and warning; wholesale template override from a
  tmp dir; block override via `{% extends "builtin/landing.html" %}`;
  `write_site` with and without `index_url`.
- Existing tests updated only for the `write_site` keyword signature.
- README: "Aggregating multiple repositories" (config example) and
  "Customizing templates" (override dir, `builtin/` extends, block list,
  simple_root caveat). Changelog entry.
- This repo's `pages.yml` keeps the single-repo shortcut form — unchanged.

## Out of scope

- Per-repo options (filters, asset patterns), release pagination beyond the
  existing first-100 behavior, `.zip` sdists, private-index auth schemes,
  config-driven output layout.
