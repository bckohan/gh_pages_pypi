# Dynamic CalVer Versioning — Design

**Date:** 2026-08-06
**Status:** Approved

## Problem

Releases currently stamp six version sites (three `pyproject.toml` `version`
lines, three `__version__` literals), commit them, then tag. The stamping is
mechanical churn, the sites can drift, and every release adds a commit whose
only content is version strings.

Adopt the dynamic strategy used in gmon3 (`~/Downloads/gmon3tar.bz2`): the
build backend computes the version from an environment variable at build
time, and git tags are the single source of truth. CalVer only — gmon3's
`+branch.hash` local segment is deliberately dropped.

## Empirical findings (verified before design)

- `uv.lock` records **no** `version =` line for a package with a dynamic
  version — only `name` and `source`. So the lock does not churn daily and
  `pages.yml`'s `uv run --locked` keeps working. (Tested with a scratch
  hatchling package: `uv lock --check` passed with a different
  `PACKAGE_VERSION` set.)
- `PACKAGE_VERSION=x uv build --wheel` produces `dyn-x-py3-none-any.whl`;
  unset, it falls back to the date.

## Decisions

- **All three packages use hatchling** with
  `[tool.hatch.version] source = "code"` pointing at their own
  `_version.py` (demos switch from setuptools — one mechanism repo-wide,
  and each sdist stays self-contained).
- **Dev version shape: `YYYY.M.D.devN`** (PEP 440 pre-release), N counting
  commits since today's tag or midnight. Chosen over gmon3's bare `.N`
  because `2026.8.6.1` would sort *above* the released `2026.8.6`; `.devN`
  always sorts below it.
- **`__version__` = `importlib.metadata.version("ghr-pypi")`** — the
  installed version. Calling `get_version()` at runtime would recompute
  today's date and misreport an installed wheel.
- **No release commit.** `just release` tags and pushes only.

## Version source

Each package gets its own `_version.py`:

```python
import os
from datetime import datetime, timezone


def get_version() -> str:
    """Return PACKAGE_VERSION when set, else a dated dev version."""
    now = datetime.now(timezone.utc)
    return os.environ.get("PACKAGE_VERSION", f"{now.year}.{now.month}.{now.day}.dev0")
```

- `src/ghr_pypi/_version.py`
- `packages/demo-lib/src/ghr_pypi_demo_lib/_version.py`
- `packages/demo-app/src/ghr_pypi_demo_app/_version.py`

Each pyproject: drop the static `version`, add `dynamic = ["version"]` and

```toml
[tool.hatch.version]
source = "code"
path = "src/<module>/_version.py"
expression = "get_version()"
```

Demo pyprojects additionally switch `[build-system]` to hatchling and gain
`[tool.hatch.build.targets.wheel] packages = ["src/<module>"]`.

All three read the same env var, so one tag versions everything — preserving
the unified-release property.

## Runtime `__version__`

```python
from importlib.metadata import version

__version__ = version("ghr-pypi")
```

(and the demo equivalents with their own distribution names). The six
hand-stamped literals are removed.

## justfile

- **`print-version`** (new, bash): if `git describe --tags --exact-match
  HEAD` succeeds, echo the tag without its leading `v` and exit. Otherwise
  `YYYY.M.D.devN` (unpadded month/day) where N is
  `git rev-list --count <today's tag>..HEAD` when a tag was created today,
  else `git rev-list --count --since="today 00:00" HEAD`.
- **`build VERSION=""`**: exports `PACKAGE_VERSION` (the argument, else
  `just print-version`) then runs the existing docs+`uv build`.
- **`validate_version VERSION`**: no longer reads files. Asserts the version
  parses per PEP 440 and normalizes to itself, and that
  `just print-version` equals it — which verifies the checkout is at the
  tagged commit. Prints the bare version (CI consumes stdout).
- **`_stamp-version`: deleted.**
- **`release`**: guards — on `main`, clean tree, `git fetch --tags origin`,
  and HEAD present on `origin/main` (new: refuse to tag an unpushed
  commit) — then compute the next CalVer tag from existing `v*` tags (the
  date+serial logic `_stamp-version` used), run the test suite, create the
  signed tag, and `git push origin <tag>`. No stamping, no commit, no
  `uv lock`.

## release.yml

The Verify Tag step gains one line: after computing `RELEASE_VERSION`, also
`echo "PACKAGE_VERSION=${RELEASE_VERSION}" >> "$GITHUB_ENV"`, so `just
build` and both demo `uv build` steps stamp the tag version instead of the
dev fallback. No other workflow changes.

## Lockfile

`uv lock` after the change removes the three `version =` lines from
`uv.lock`. One-time update, committed with the feature.

## Tests

- `get_version()` returns `PACKAGE_VERSION` when set (monkeypatched env).
- Fallback matches `^\d{4}\.\d{1,2}\.\d{1,2}\.dev0$` and is PEP 440 parseable
  when the env var is absent.
- Existing suite must stay green; nothing else references the removed
  literals.

## Docs

- CONTRIBUTING "Versioning": tags are the source of truth, dev builds report
  `YYYY.M.D.devN`, `just print-version` shows the current version.
- AGENTS.md release block: `just release` no longer stamps or commits.
- Changelog entry.

## Out of scope

- Branch/hash local version segments; changing the CalVer scheme itself;
  backfilling versions of existing releases.
