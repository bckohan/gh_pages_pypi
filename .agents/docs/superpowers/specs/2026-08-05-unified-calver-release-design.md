# Unified CalVer Release — Design

**Date:** 2026-08-05
**Status:** Approved

## Problem

The repository has two disjoint release flows:

- `just release VERSION` (semver, never used): signs and pushes `vX.Y.Z`, and
  `release.yml` lints, tests, builds the main package, publishes to
  TestPyPI/PyPI via trusted publishing, and creates a GitHub Release with
  sigstore signatures.
- `just demo-release <pkg>` (CalVer per package): stamps one demo package's
  pyproject, tags `demo-<pkg>-v2026.8.4`, and `demo-release.yml` builds that
  package, creates a per-package GitHub Release, and triggers the Pages
  rebuild.

We want **one repository release** per version that ships all three packages
(github-releases-pypi, demo-lib, demo-app), **all stamped with the same
CalVer version**.

## Decisions

- **PyPI publishing stays.** The unified release still publishes
  github-releases-pypi (only) to TestPyPI and PyPI, now with CalVer versions.
- **Auto-computed CalVer.** `just release` takes no argument; version is
  `YYYY.M.D` (no zero padding), with a `.N` serial suffix when the same base
  version was already tagged that day.
- **Old per-package releases are deleted** — the two `demo-*-v2026.8.4`
  GitHub Releases and their git tags. The index reflects only unified
  releases from then on.
- **One workflow.** `release.yml` is extended; `demo-release.yml` and the
  `demo-release` recipe are deleted. (Chosen over a per-package build matrix
  — needless plumbing for three fast builds — and over two tag-triggered
  workflows, which would race to create the same release.)

## Section 1 — Versioning and the local `release` recipe

`just release` (no version argument) replaces both `release VERSION` and
`demo-release`:

1. Prerequisites: existing `install check-all`.
2. Compute the version: `YYYY.M.D` from today's date; if tag `v<base>` (or
   `v<base>.N`) already exists, increment `.N` until free — the serial scheme
   demo-release uses today, applied to `v*` tags.
3. Stamp the version into **six places in one script**:
   - `pyproject.toml` (root), `packages/demo-lib/pyproject.toml`,
     `packages/demo-app/pyproject.toml` — `version = "..."` lines
   - `src/github_releases_pypi/__init__.py`,
     `packages/demo-lib/src/github_releases_pypi_demo_lib/__init__.py`,
     `packages/demo-app/src/github_releases_pypi_demo_app/__init__.py` —
     `__version__ = "..."` lines

   The script fails (and changes nothing) if any expected version line is
   missing. This also fixes the existing latent inconsistency where the demo
   `__init__.py` versions (1.0.0) drifted from their pyprojects (2026.8.4)
   because demo-release only stamped pyproject.
4. Run the test suite, commit as `Release <version>`, create a **signed** tag
   `v<version>` (demo releases lose their unsigned-tag exception), push main
   and the tag.

`validate_version` is extended: given a tag it verifies the version parses
per PEP 440, normalizes to itself, and matches all three pyprojects and all
three `__version__` strings. CI uses it to reject inconsistent tags.

Demo-app's dependency constraint `github-releases-pypi-demo-lib>=1.0.0` is
left alone — it resolves correctly and avoids a seventh stamp site.

## Section 2 — CI: one workflow, one release

`demo-release.yml` is deleted. In `release.yml` (trigger `v[0-9]*.[0-9]*.[0-9]*`
already matches `v2026.8.5` and `v2026.8.5.1`):

- **build job:** unchanged main-package build (`just build`), then also build
  demo-lib and demo-app. Upload two artifacts:
  - `python-package-distributions` — main package dists only; flows to the
    TestPyPI/PyPI jobs unchanged.
  - `demo-package-distributions` — demo dists only.

  The two-artifact split is the guard that keeps demo packages off PyPI:
  `pypa/gh-action-pypi-publish` publishes everything in `dist/`, so the demos
  must never land in the artifact the publish jobs download.
- **publish-to-testpypi / publish-to-pypi jobs:** untouched.
- **github-release job:** download both artifacts, sigstore-sign all dists,
  create one GitHub Release `v<version>` with all six dist files plus
  signatures, then trigger `pages.yml` via `gh workflow run` (releases
  created with `GITHUB_TOKEN` don't fire `release` events). The job gains
  `actions: write` for the dispatch.

Consequence: the Pages index also serves **github-releases-pypi itself**
(the index builder collects every wheel/sdist asset of every release) — the
repo dogfoods its own tool end to end.

## Section 3 — Cleanup and docs

- Delete GitHub Releases `demo-lib-v2026.8.4` and `demo-app-v2026.8.4` and
  their tags (local and origin). Until the first unified release, the index
  is empty and `pages.yml` fails by design — its documented fresh-repo
  behavior; expected transient state.
- AGENTS.md: Release section documents `just release` (CalVer, stamps all
  packages, one unified release).
- README.md / doc/: sweep for the per-package release flow (`demo-release`)
  and describe the unified flow instead.
- justfile comments updated to match.

## Section 4 — Testing and verification

- **No `src/` changes.** `collect_projects` already handles one release
  containing many projects' assets; the existing 13 tests cover it.
- The stamping script is the bug-prone part (missed version line, partial
  stamp). Verify by running its logic against the repo and checking all six
  files changed, plus `validate_version` against the stamped tree; the
  recipe's `check-all` gate runs the full suite.
- **End-to-end proof** is the first real `just release`: release.yml →
  TestPyPI/PyPI publish + one GitHub Release → pages.yml serving all three
  packages. Triggered by the user when ready; everything before the push is
  reversible.

## Out of scope

- Publishing the demo packages to PyPI.
- Changing index-builder behavior (pagination, `.zip` sdists, etc.).
- Renaming or restructuring the demo packages.
