# Release `.metadata` Assets (Producer Dogfood) — Design

**Date:** 2026-08-06
**Status:** Approved

## Problem

Link-mode indexes can only advertise PEP 658 metadata when releases upload
`<wheel>.metadata` assets — and almost no repository does. This repo should
produce them for its own releases (dogfooding both halves of the PEP 658
feature: our release workflow produces, our Pages index consumes and the
per-repo warning goes quiet) and document the copyable recipe for other
repos.

Chosen over (deferred, own brainstorm): an `extract-metadata` CLI
subcommand — that forces the single-command → subcommand CLI-shape decision.

## Decisions

- **Extraction happens in `release.yml`'s `github-release` job**, after both
  dist artifacts are downloaded into `dist/`, before the release
  create/upload steps. NOT in the build job: `.metadata` files must never
  enter the `python-package-distributions` artifact the TestPyPI/PyPI jobs
  consume (twine would choke on them).
- A `python3` heredoc step extracts each `dist/*.whl`'s unique depth-1
  `*.dist-info/METADATA` member to `<wheel>.metadata` (same rule as
  `index.extract_metadata`); a non-unique/missing member fails the job.
- The existing `gh release upload "$GITHUB_REF_NAME" dist/** --clobber`
  picks the files up with no change. Sigstore signing stays wheels+sdists
  only (its globs are untouched).
- **README**: the PEP 658 section's link-mode bullet gains the copyable
  workflow step and a pointer to this repo's `release.yml` as the living
  example.
- Changelog bullet.

## Verification

- Workflow YAML parses; `uvx zizmor --no-online-audits .github/workflows`
  no new findings; the heredoc script run locally against `uv build` output
  produces a correct `.metadata` file (byte-equal to the wheel's METADATA).
- `just check-all` green. Real proof is the next `just release`.

## Out of scope

- The `extract-metadata` CLI subcommand; signing `.metadata` files;
  demo-package `.metadata` for past releases.
