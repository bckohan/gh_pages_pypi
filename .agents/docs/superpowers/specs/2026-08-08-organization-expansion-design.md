# Organization Expansion — Design

**Date:** 2026-08-08
**Status:** Approved

## Problem

Indexing an organization means listing every repository by hand and editing the
config whenever one is added. There is no way to say "everything in `yourorg`
that this token can read".

## Decisions

- **Patterns live in `repositories`.** An entry whose *name half* contains any
  of `*`, `?` or `[` is expanded by listing the owner's repositories. Matching
  is `fnmatch`, so the detection set must be exactly the characters `fnmatch`
  treats as special — detecting on `*`/`?` alone would silently read
  `yourorg/lib-[ab]` as a literal repository name. No new key for the common
  case, and `yourorg/lib-*` comes free.
- **`exclude_repositories` subtracts from expansions only.** A repository named
  explicitly is always indexed.
- **Expansion happens in the CLI, not in `config.load`**, which must stay
  network-free.
- **`fetch_releases` becomes paginated too**, on the same shared helper. Reading
  one page was a documented limitation; there is no reason for it.
- **Everything readable is included** — forks and archived repositories too. An
  archived project's wheels are still installable, and a hidden filter is worse
  than an explicit exclusion.

## Config

```yaml
repositories:
  - yourorg/*              # every repo the token can read in yourorg
  - yourorg/lib-*          # or a name prefix
  - someoneelse/one-repo   # composes with explicit entries
exclude_repositories:
  - yourorg/secret-*
```

The same works on the command line, where the pattern **must be quoted** so the
shell does not try to glob it:

```sh
ghr-pypi index 'yourorg/*' --out site
```

(An unquoted `yourorg/*` normally matches no local path and is passed through,
but that is shell-dependent and must not be documented as the way to do it.)

### Validation (in `config.load` and the CLI's resolver, no network)

- A pattern in the **owner half** is rejected: there is no API for "every
  organization I can see". Message:
  `{label} {value!r} may not use a pattern in the owner`
- `$GITHUB_REPOSITORY` may never be a pattern — same message, with
  `GITHUB_REPOSITORY` as the label.
- `exclude_repositories` must be a list of strings, each an `OWNER/NAME`
  pattern, validated by the existing `check_slug` plus the owner-half rule.
- The existing duplicate-literal check still applies to literal entries.
  Patterns are exempt: two patterns may legitimately overlap.

`Config` gains `exclude_repositories: tuple[str, ...] = ()`.

## Pagination

Both listings share one helper in `index.py`:

```python
def _paginate(url: str, token: str) -> list[dict[str, Any]]:
    """Return every item of a paginated GitHub list endpoint."""
```

It requests `{url}?per_page=100&page=N` for N = 1, 2, … accumulating results
until a page returns fewer than 100 items, and carries the existing
`Accept`/`Authorization` headers, timeout and `# nosec B310` justification.

A hard page cap of **100 pages (10,000 items)** guards against a server that
never returns a short page — an infinite loop in a build tool is worse than a
truncated index. Hitting it is an error, not a silent stop.

`fetch_releases` is rewritten on top of it, **removing the one-page limit**.
That limit is currently documented in four places (`doc/source/index.rst`'s
"When not to use it", `how-to/aggregate-repositories.rst`,
`how-to/build-failed.rst`, and `README.md`); all four must be updated, and the
`index.rst` entry deleted outright since it is no longer a reason not to use
the tool.

## Expansion

`index.fetch_repositories(owner: str, token: str) -> list[str]` returns every
`owner/name` the token can read, via `_paginate`.

- `GET /orgs/{owner}/repos` first.
- On **404**, retry against `GET /users/{owner}/repos`, so a personal account
  works.

The CLI expands after resolving the config and before the release-fetch loop:

1. For each `repositories` entry, a literal passes through unchanged; a pattern
   is expanded by listing its owner once (cached per owner, so `yourorg/lib-*`
   and `yourorg/app-*` cost one listing) and `fnmatch`-ing the name half,
   **case-insensitively**, matching the existing case-insensitive duplicate rule.
2. Matches are sorted and spliced in place of the pattern, so explicit entries
   keep their relative position. Order matters: duplicate filenames across
   repositories resolve first-occurrence-wins.
3. `exclude_repositories` patterns remove matches **from expansions only**.
4. The whole list is de-duplicated case-insensitively, first occurrence winning.
   This is silent, unlike the config-level duplicate-literal error.
5. A pattern matching **zero** repositories after exclusions is an error:
   `no repositories matched {pattern!r}`. It means a typo'd owner or a token
   without access, and this tool already refuses to build an empty index rather
   than silently produce nothing.

Each expansion reports `expanded 'yourorg/*' to 47 repositories` on stderr, so
the cost is visible.

An `exclude_repositories` pattern that matches nothing is **not** an error —
unlike a `repositories` pattern. You may reasonably pre-exclude a repository
that does not exist yet. The cost is that a typo there is silent; that is
accepted deliberately.

## The user-account limitation

`GET /users/{owner}/repos` lists **only public repositories**. GitHub has no
endpoint for another user's private repositories, and your own require
`GET /user/repos`, which does not work for Actions' `github.token` or for App
installation tokens.

So `someuser/*` finds public repositories only. Private repositories on a
personal account must be listed explicitly. This is documented prominently
rather than worked around, because a `/user/repos` code path would work for
exactly one kind of token and fail confusingly for the others.

## Cost

An organization of 300 repositories costs 3 listing calls plus at least 300
release calls — inside the 5,000/hour authenticated limit, but slow, and every
repository is fetched whether or not it has releases. Pagination adds a call per
extra 100 releases in any one repository. Documented in the how-to.

## Tests

- `_paginate`: one short page; a full page then a short one; a full page then an
  empty one (the boundary where the item count is an exact multiple of 100);
  the page cap tripping as an error.
- `fetch_releases`: returns releases from beyond the first page — the
  regression that this change exists to fix.
- `fetch_repositories`: single page; multi-page; the 404 fallback to `/users/`;
  a 404 from both surfacing as an error.
- Pattern matching: `*` matches all; `lib-*` matches a prefix; case-insensitive;
  a literal entry is not treated as a pattern.
- Splicing: an explicit entry before a pattern stays before all of its matches
  (assert the resulting order, since duplicate resolution depends on it).
- One listing call per owner even with two patterns for that owner.
- `exclude_repositories` removes from an expansion and does **not** remove an
  identically-named explicit entry.
- Zero matches → error naming the pattern; zero matches for an exclusion → fine.
- Validation: owner-half pattern rejected from the config, from a positional
  argument, and from `$GITHUB_REPOSITORY`; `exclude_repositories` shape errors.
- Dedupe across overlapping patterns keeps the first occurrence.

## Docs

- `reference/configuration.rst`: patterns under `repositories`, the new
  `exclude_repositories` key, every new error message.
- `reference/cli.rst`: the quoting requirement.
- A how-to, "How do I index a whole organization?", covering the user-account
  limitation and the per-repository API cost.
- The one-page release limit removed from `doc/source/index.rst`,
  `how-to/aggregate-repositories.rst`, `how-to/build-failed.rst` and
  `README.md`.
- Changelog.

## Out of scope

- `GET /user/repos` for private repositories on personal accounts.
- Patterns in the owner half.
- Skipping forks, archived repositories, or repositories with no releases — the
  escape hatch is `exclude_repositories`.
- Caching the repository listing between builds.
