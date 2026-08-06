# Asset Digest + Missing-Digest Policy — Design

**Date:** 2026-08-05
**Status:** Approved

## Problem

`collect_projects` downloads every wheel/sdist asset on every build solely to
compute the `#sha256=` fragment — on a large index, regenerating after one new
release re-downloads everything. GitHub's releases API now returns a
`digest: "sha256:..."` field per asset (backfilled only for assets uploaded
since mid-2025), which provides the hash for free.

## Decisions

- **Digest present → always used.** No download, no re-verification option.
  A digest with a non-`sha256` algorithm prefix is treated as absent.
- **One YAML config key governs digest-less assets only** (performance vs
  security trade-off): `missing_digest`, enum, default `download`.
- **YAML-only.** The single-repo CLI shortcut always uses the default
  (`download`); no CLI flag.
- **Approach A**: policy threaded as a parameter through `collect_projects`;
  `FileEntry.sha256` becomes optional; template renders the fragment
  conditionally. (Rejected: strategy objects — three fixed policies don't
  justify indirection; pre-pass annotation — second asset walk to avoid a
  signature change we control.)

## Config

```yaml
missing_digest: download   # default — download & hash digest-less assets
# missing_digest: no-fragment  # link digest-less assets without #sha256=
# missing_digest: omit         # exclude digest-less assets, warn on stderr
```

- Validated in `config.load`: must be one of the three strings; `ConfigError`
  otherwise. Stored on `Config` as `missing_digest: str = "download"`.
- With `download`, output for pre-digest assets is byte-identical to today.

## collect_projects

Signature: `collect_projects(releases, hash_url=hash_url,
missing_digest="download")`.

Per asset (after the existing draft/non-package/duplicate checks, which are
unchanged):

1. `digest = asset.get("digest")`; if it is a string starting with
   `"sha256:"` with a non-empty remainder, use the remainder as the hash —
   **no download**. An empty remainder (`"sha256:"`) is treated as absent.
2. Otherwise apply the policy:
   - `download`: `sha256 = hash_url(browser_download_url)` (today's path).
   - `no-fragment`: `sha256 = None`.
   - `omit`: skip the asset entirely; stderr warning
     `warning: <filename> has no digest, omitted (missing_digest=omit)`.

`FileEntry.sha256: str | None`. The duplicate-filename dedupe still keys on
filename and still fires before any hashing.

## Rendering

`project.html`'s anchor becomes (inside the existing `content` block, so
block overrides are unaffected):

```html
<a href="{{ file.url }}{% if file.sha256 %}#sha256={{ file.sha256 }}{% endif %}">{{ file.filename }}</a>
```

PEP 503: the hash fragment is SHOULD, not MUST — a fragment-less link is
valid; pip installs without integrity verification.

## CLI

`build` passes `missing_digest=cfg.missing_digest` into `collect_projects`.
Shortcut path relies on the `Config` default. No other CLI changes.

## Tests

- Digest-present asset: hash taken from `digest`, `hash_url` never called
  (spy), `sha256:` prefix stripped.
- Non-sha256 digest (e.g. `"blake2:..."`) treated as absent → policy applies.
- Each policy value end-to-end: `download` hashes; `no-fragment` renders an
  anchor without `#sha256=`; `omit` drops the file and warns.
- Config: `missing_digest` accepted for all three values, default `download`,
  invalid value → `ConfigError`.
- CLI: config with `missing_digest: no-fragment` flows through to the
  rendered project page.
- Existing tests: fixtures have no `digest` keys, so default behavior is
  unchanged — suite must stay green without edits (except where fixtures are
  deliberately extended).

## Docs

- README "Aggregating multiple repositories": document `missing_digest` with
  a three-row value table and the mid-2025 backfill caveat.
- Changelog bullet.

## Out of scope

- Re-verifying digests, ETag caching of release listings, pagination,
  reusing the previously published site as a hash cache.
