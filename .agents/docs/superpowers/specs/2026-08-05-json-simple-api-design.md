# PEP 691 JSON Simple API — Design

**Date:** 2026-08-05
**Status:** Approved

## Problem

The index is HTML-only (PEP 503). PEP 691 defines a JSON serialization of
the Simple API (`application/vnd.pypi.simple.v1+json`) that uv prefers and
that webserver/CDN targets can serve at the canonical URLs via `Accept`
content negotiation. Static hosts can't negotiate, but the JSON files are
still useful (tooling, future-proofing) and cost nothing to emit.

This is phase 1 of the serving-target-spectrum direction (see
`direction.md`): JSON output first; mirroring, PEP 658 metadata, and
target-artifact generation are separate later phases.

## Decisions

- **Config:** `formats:` — optional list, elements `html` / `json`, no
  duplicates, non-empty; default `[html, json]` (both). Stored as
  `tuple[str, ...]`.
- **API version 1.1** (PEP 691 + PEP 700): `versions`, `files[].size`
  (required by 1.1), `files[].upload-time` when known. Concrete payoff:
  uv's `--exclude-newer` works off `upload-time`.
- **JSON via `json.dumps`, not Jinja.** The shape is spec-fixed; template
  overrides do not apply to JSON (documented).
- **Landing page only when `html` is in formats** — a JSON-only index is
  headless by intent.
- Layout: `simple/index.json` and `simple/<project>/index.json` beside the
  HTML files. On webservers, an `Accept`-based rule serves them at the
  canonical URLs; on static hosts they're parallel files.

## Config

```yaml
formats: [html, json]   # optional — default: both
```

Validation in `config.load`: must be a list; elements from {`html`,
`json`}; non-empty; no duplicates; `ConfigError` otherwise (message echoes
the offending value). `Config.formats: tuple[str, ...] = ("html", "json")`.
A `Formats = Literal["html", "json"]` alias mirrors the `MissingDigest`
pattern.

## Data plumbing (`index.py`)

- `FileEntry` gains:
  - `size: int` — from the asset's `size` field; GitHub always sends it;
    absent (hand-built fixtures) → 0.
  - `upload_time: str | None` — the asset's `created_at` (RFC 3339,
    already the PEP 700 wire format); absent → None.
  `collect_projects` populates both. Existing HTML templates ignore them.
- New helper `version_from_filename(filename: str) -> str | None`:
  - wheel: second `-` segment (`name-version-...`);
  - `.tar.gz` sdist: remainder after `name-` (i.e. `rsplit("-", 1)[1]` of
    the stem);
  - other: None (unreachable for indexed files).
- Versions for a project: unique `version_from_filename` results across its
  files; sorted by `packaging.Version` where parseable, unparseable ones
  string-sorted after the parseable block.

## JSON emission (`index.py`)

- `simple/<project>/index.json`:

```json
{
  "meta": {"api-version": "1.1"},
  "name": "<normalized project>",
  "versions": ["1.0.0", "1.1.0"],
  "files": [
    {
      "filename": "...whl",
      "url": "https://github.com/.../...whl",
      "hashes": {"sha256": "..."},
      "size": 12345,
      "upload-time": "2026-08-05T03:07:33Z"
    }
  ]
}
```

- `hashes` is `{}` when the missing-digest policy left `sha256` None.
- `upload-time` key omitted when unknown (PEP 700: optional).
- `simple/index.json`:

```json
{"meta": {"api-version": "1.1"}, "projects": [{"name": "demo-lib"}, ...]}
```

- Serialized with `json.dumps(..., sort_keys=True)` + trailing newline;
  UTF-8.

## write_site / CLI

- `write_site(projects, out_dir, *, title, index_url, templates_dir=None,
  formats=("html", "json"))`:
  - `html` in formats → today's landing + HTML tree.
  - `json` in formats → the two JSON layers above.
- CLI passes `formats=cfg.formats`; shortcut path uses the default.

## Tests

- Config: all three formats shapes load ([html], [json], [html, json]);
  default; empty list / unknown element / duplicates / non-list →
  `ConfigError`.
- `version_from_filename`: wheel, sdist, odd names.
- JSON content: api-version, normalized name, sorted versions, file fields,
  `hashes: {}` under no-fragment, `upload-time` omitted when unknown,
  root projects list.
- Formats matrix: `[html]` output has no .json files and is byte-identical
  to today; `[json]` writes no index.html/landing; both writes both.
- CLI: config `formats: [json]` flows through (no landing.html in out dir).
- Existing tests pass unchanged (default emits HTML exactly as today plus
  new .json files — existing assertions are substring-based on the HTML).

## Docs

- README: `formats` key in the config example + a short "JSON Simple API"
  paragraph: what's emitted, the per-target negotiation story (nginx
  `Accept` rule → canonical URLs; static hosts → parallel files), JSON not
  templated.
- Changelog bullet.

## Out of scope

- Content-negotiation artifacts (nginx snippets, `_headers`), mirroring,
  PEP 658 metadata, PEP 592 yanked — later phases per `direction.md`.
