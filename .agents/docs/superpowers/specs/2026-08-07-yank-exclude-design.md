# Yank and Exclude — Design

**Date:** 2026-08-07
**Status:** Approved

## Problem

A released version can turn out to be broken. PEP 592 lets an index mark a
file *yanked* — still installable by exact pin, but skipped by resolvers,
with an optional reason. Separately, some assets should not be in the index
at all. Neither is expressible today; the only recourse is deleting the
release, which breaks anyone pinned to it.

## Decisions

- **Two new optional config keys**, `yanked` and `exclude`, both keyed by
  project then version (not by filename glob) — a yank applies to every
  artifact of that version, matching how releases are reasoned about.
- **Yank reasons via a version → reason mapping**; a reason is a string, or
  `true` for "yanked, no reason". `false` is rejected.
- **Both rules travel as one `Filters` frozen dataclass** rather than two
  more `collect_projects` parameters (its signature is already at six and
  was flagged in review).

## Config

```yaml
yanked:
  demo-lib:
    "1.0.0": "sdist built from a dirty tree"
    "1.0.1": true
exclude:
  demo-lib:
    - "0.9.0"
```

Validation (all raising `ConfigError`, message prefixed with the config
path like every other key):

- `yanked` must be a mapping; each value must be a mapping; each reason must
  be a string or `true` (`false` → "remove the entry to un-yank").
- `exclude` must be a mapping; each value must be a list of strings.
- Version keys must be strings (YAML `1.0` parses as a float — reject with a
  message telling the user to quote it; this is the most likely mistake).
- Project keys are PEP 503-normalized on load, so `Demo_Lib` and `demo-lib`
  are the same project — and two keys in the same block that normalize to
  the same name are **rejected** (amendment: silently merging last-wins
  would discard a whole block of the user's config, and `repositories`
  already rejects duplicates). A non-string project key is also rejected
  rather than crashing in normalization. Note `config.py` must not
  import `index.py` (index imports config — avoid a cycle); duplicate the
  three-line normalize or move it to a shared spot. Implementer's call,
  stated in the report.

`Config` gains `yanked: Mapping[str, Mapping[str, str | bool]]` and
`exclude: Mapping[str, tuple[str, ...]]`, both defaulting to empty, plus a
`filters` property (or a module function) returning the `Filters` instance.

## Matching

`Filters` exposes two lookups taking a normalized project and the version
string from `index.version_from_filename`:

- Versions compare equal when both parse as `packaging.Version` and are
  equal (so `1.0` matches `1.0.0`), else by exact string.
- A file whose version cannot be parsed from its filename (`None`) matches
  nothing and is always kept.

## Behavior

- **exclude**: in `collect_projects`, a matching file is skipped *before*
  the duplicate-filename `seen` bookkeeping, so it never claims a filename
  slot another repository's copy could fill. No warning (exclusion is
  intentional and could be noisy); the build summary already reports the
  project count.
- **yank**: `FileEntry` gains `yanked: str | bool` (default `False`).
  Yanked files are otherwise ordinary — hashed, mirrored, metadata-extracted
  as usual.

## Emission

- `project.html` anchor gains, when `file.yanked` is truthy, a
  `data-yanked` attribute whose value is the reason (empty string when the
  reason is `True`). Presence alone marks the file yanked per PEP 592.
- `_json_project_page` file entries gain `"yanked": true` or
  `"yanked": "<reason>"`; the key is omitted when not yanked (PEP 691
  defaults it to false).
- PEP 700 `versions` still lists yanked versions; excluded versions are
  absent because their files never entered the index.
- Template caveat: a wholesale `project.html` override must copy the
  conditional attribute, like the hash fragment and metadata attributes.

## Tests

- Config: both keys load; every validation error shape; unquoted `1.0`
  (float) rejected with the quoting hint; project-key normalization.
- Matching: `1.0` vs `1.0.0` equal; unparseable version never matches;
  unknown project is a no-op.
- exclude: file absent from the index; does NOT claim a dedupe slot (a
  same-named file from a later release is still indexed).
- yank: HTML carries `data-yanked` with and without a reason; JSON carries
  `"yanked": true` / the reason string; absent when not yanked; the yanked
  version still appears in `versions`.
- Existing suite unchanged (both keys default to empty).

## Docs

- Reference `configuration.rst`: both keys, full detail, all new errors.
- New how-to: "How do I yank a bad release?" (covering exclude as the
  harder-edged alternative), linked from the how-to index.
- Changelog entry.

## Out of scope

- Filename-glob granularity (yanking one platform wheel of a version);
  yanking whole projects; time-based rules.
