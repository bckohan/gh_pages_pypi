# Asset Mirroring — Design

**Date:** 2026-08-05
**Status:** Approved

## Problem

The index links to GitHub's asset URLs, which requires the assets to be
publicly downloadable and keeps GitHub in the serving path. Mirroring
downloads the assets at build time and serves them as part of the site:
self-contained output for any host (nginx, Cloudflare, Pages), and the only
build-side answer for **private repositories** (pip/uv cannot drive GitHub's
authenticated asset redirect — see `direction.md`).

Phase 2 of the serving-target-spectrum direction.

## Decisions

- **`mirror: true` config key + `--mirror` CLI flag** (shortcut path only;
  `--config` + `--mirror` is an error — set it in the config).
- **Incremental via out-dir reuse:** a file already present at its mirror
  path with the expected hash is not re-downloaded. CI persists
  `site/files/` with `actions/cache` (documented recipe); in-place builds
  (nginx) get incrementality for free.
- **Hash everything, verify digests:** every mirrored file is hashed while
  streaming to disk. If the API supplied a digest and it disagrees with the
  downloaded bytes → hard build error. Every mirrored file gets a
  `#sha256=` fragment.
- **`missing_digest` is rejected alongside `mirror: true`** (explicitly
  setting both → `ConfigError`) — it has no effect under mirroring.
- **Downloads use the API asset endpoint** (asset `url` field) with
  `Authorization: Bearer <token>` + `Accept: application/octet-stream`,
  following the 302 to the signed URL. Works for public and private repos.
- This repo's own `pages.yml` stays link-mode.

## Config / CLI

```yaml
mirror: true   # optional — default false; download assets into the site
```

- `Config.mirror: bool = False`; validation: must be a bool; explicit
  `missing_digest` key together with `mirror: true` → `ConfigError`
  (`'missing_digest' has no effect when 'mirror' is enabled`).
- CLI: `--mirror` boolean option. With positional REPO → shortcut Config
  gains `mirror=True`. With `--config` → error
  (`error: with --config, set 'mirror' in the config file`).

## Data flow

- `FileEntry` gains `api_url: str` (the asset's API `url`); emitters pick
  keys explicitly so it never appears in HTML or JSON output.
- `collect_projects(..., defer_hash=False)`: under mirror mode the CLI
  passes `defer_hash=True` — sha256 comes from the API digest when present,
  else None; `hash_url` is never called and `missing_digest` never applies.
  (Existing link-mode behavior is untouched.)
- New `mirror_files(projects, out_dir, token, *, opener=urllib.request.urlopen)`
  runs after `collect_projects` and before `write_site`. Per file entry:
  1. `dest = out_dir / "files" / <project> / <filename>`.
  2. **Reuse:** if `dest` exists — hash it; if it matches the entry's
     sha256, skip the download. If the entry has no sha256 (no digest),
     adopt the existing file's hash and skip.
  3. **Download:** GET `api_url` with the two headers above (opener
     injectable for tests), stream to `dest` in chunks, hashing while
     writing. If the entry had a sha256 (API digest) and the computed hash
     differs → raise `MirrorError` naming the file, both hashes; the
     partial file is removed. Otherwise set the entry's sha256 to the
     computed hash.
  4. **Rewrite:** entry `url` becomes `../../files/<project>/<filename>` —
     relative, correct from `simple/<project>/index.html` and `.json`, and
     host-relocatable.
- `MirrorError(RuntimeError)`; the CLI catches it (and URLError from the
  download) via the existing "downloading a release asset failed" error
  path, extended to print the MirrorError message verbatim.

## Layout

```
site/files/<normalized-project>/<filename>   ← mirrored assets
site/simple/<project>/index.html|.json       ← links ../../files/...
```

Dedupe is unchanged and fires before mirroring, so each filename is
mirrored at most once. Empty-index refusal unchanged.

## Tests

- Layout + relative URLs present in both HTML and JSON output.
- Incremental: second run with a populated out dir downloads zero files
  (download-counter spy); corrupted existing file (hash mismatch) is
  re-downloaded.
- Digest-mismatch on download → `MirrorError`, partial file removed.
- No-digest file: hash adopted from downloaded (or existing) bytes;
  fragment present.
- API endpoint usage: injected opener asserts the request URL is the
  asset's `api_url` and carries both headers.
- Config: `mirror` bool validation; explicit missing_digest+mirror
  rejection; `--mirror` flag on shortcut; `--config` + `--mirror` error.
- Existing tests unchanged (mirror defaults off).

## Docs

- README "Mirroring assets" section: what it does, private-repo story,
  `actions/cache` recipe for `site/files/`, mirror/missing_digest
  exclusivity, relocatable relative links.
- Changelog bullet.

## Out of scope

- Target size-limit warnings (Pages 1GB / CF Pages 25MB), PEP 658 metadata
  extraction (phase 3 — composes with mirroring), the token-holding
  redirector artifact, pruning files/ entries for assets no longer in any
  release (documented caveat: stale mirrored files persist until manually
  cleared; revisit with the manifest work).
