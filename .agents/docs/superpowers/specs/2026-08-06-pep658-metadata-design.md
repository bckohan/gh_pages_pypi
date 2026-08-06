# PEP 658/714 Core Metadata — Design

**Date:** 2026-08-06
**Status:** Approved

## Problem

Resolvers (uv especially) can resolve dependencies without downloading whole
wheels when the index serves each wheel's core METADATA per PEP 658/714.
The metadata file must live at `<file-url>.metadata`, which we control only
for files we host — so mirror mode can produce it, while link mode can only
advertise metadata assets the release itself uploaded, and should tell the
user (per repository) when wheels lack them.

Phase 3 of the serving-target-spectrum direction (`direction.md`).

## Decisions

- **`metadata: bool = True` config key.** No CLI flag. `false` disables
  extraction, advertising, and warnings.
- **Mirror mode:** extract `*.dist-info/METADATA` from each locally
  mirrored wheel (stdlib `zipfile`, zero downloads), write
  `<filename>.metadata` beside the wheel, advertise its sha256. Corrupt or
  METADATA-less wheels warn and are served without metadata. Sdists out of
  scope.
- **Link mode:** advertise release-uploaded `<wheel>.metadata` assets
  (their `browser_download_url` is exactly `<file-url>.metadata`); hash
  from the asset's API digest when present, else advertised as available
  (`true`). Warn **per repository** (summary line, not per file) when a
  repo's wheels lack metadata assets; repos fully covered stay silent.
- **Emission uses both spellings** (PyPI-compatible): HTML
  `data-core-metadata` + `data-dist-info-metadata` (`sha256=<hash>` or
  `true`); JSON `core-metadata` + `dist-info-metadata` (`{"sha256": ...}`
  or `true`). Only emitted when metadata is known — otherwise output is
  byte-identical to today.

## Config

```yaml
metadata: true   # optional — default true; PEP 658 metadata where possible
```

Validation: must be a bool (`'metadata' must be true or false`). No
interaction constraints (meaningful in both modes).

## Data flow

- **Repo attribution:** the CLI tags each fetched release dict with
  `release["_source_repo"] = <owner/name>` before concatenation (key absent
  from GitHub's payload). `FileEntry` gains `source_repo: str` (internal,
  never emitted, like `api_url`), populated from that tag ("" default).
- **Pairing (in `collect_projects`):** gated on a `metadata: bool = True`
  parameter (the CLI passes `cfg.metadata`) — when False the pairing map is
  never built and every entry's `core_metadata` stays False, so `metadata:
  false` disables advertising in BOTH modes, not just extraction/warnings
  (amendment from final integration review: without this gate, mirror +
  `metadata: false` advertised local `.metadata` URLs that 404).
  `.metadata` assets don't parse as wheels/sdists so they never become
  index files. A pairing map
  `<name>.metadata → digest-or-None` is built from each release's assets
  (before the unsafe-name guard skips them from indexing, metadata assets
  must pass the same guard to be paired). `FileEntry` gains
  `core_metadata: str | bool` — `False` none, `True` available unhashed,
  `str` = sha256. Wheels only (`.whl` entries); sdists always `False`.
  Dedupe: the winning wheel's own release provides its pairing.
- **Mirror extraction (new `extract_metadata(projects, out_dir)` in
  `index.py`, called by the CLI after `mirror_files` when
  `cfg.metadata`):** for each `.whl` entry, open the mirrored wheel, read
  the single `*.dist-info/METADATA` member, write
  `files/<project>/<filename>.metadata`, set `core_metadata` to its
  sha256. On failure (bad zip, missing member): stderr warning naming the
  file; entry left without metadata. Reuses nothing — extraction from a
  local zip is cheap and deterministic.
- **Link-mode warning (in the CLI, when `cfg.metadata and not
  cfg.mirror`):** group `.whl` entries by `source_repo`; for each repo
  where some wheels lack `core_metadata`, print
  `warning: <repo>: N of M wheels have no .metadata asset; resolvers must
  download full wheels for dependency metadata`.

## Emission

- `project.html` anchor gains, when `file.core_metadata` is truthy, both
  attributes with value `sha256=<hash>` (str) or `true` (True).
- `_json_project_page` file entries gain `core-metadata` and
  `dist-info-metadata` keys with `{"sha256": <hash>}` or `true` — omitted
  entirely when `False`.
- Template caveat documented: wholesale `project.html` overrides should
  copy the built-in's conditional attributes.

## Tests

- Config bool validation + default.
- Pairing: wheel + digest-bearing metadata asset → sha256; digest-less →
  True; no asset → False; sdist ignored; unsafe-named metadata asset not
  paired.
- Extraction: minimal wheel built in-test via `zipfile` → `.metadata`
  file written beside it, hash advertised in HTML (both attrs) and JSON
  (both keys); corrupt wheel → warning, no metadata, build continues.
- Per-repo warning: two tagged repos, one fully covered (silent), one with
  gaps (one line, correct counts); `metadata: false` silences everything.
- Output unchanged when no metadata anywhere (existing tests).

## Docs

- README "Dependency metadata (PEP 658)" section after "Mirroring assets":
  what resolvers gain, mirror extraction, link-mode pass-through +
  per-repo warning, `metadata: false`, template caveat.
- Changelog bullet.

## Out of scope

- Sdist metadata (PEP 643), uploading `.metadata` assets to releases
  (producer-side), metadata-based search/UI features, target-artifact
  generation (phase 4).
