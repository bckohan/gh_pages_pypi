# Dynamic CalVer Versioning Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers-extended-cc:subagent-driven-development (recommended) or superpowers-extended-cc:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **PROJECT RULE (AGENTS.md):** agents never commit or push — the human driver
> does. Implementers stop at "verified in working tree".

**Goal:** Replace six hand-stamped version sites with build-time dynamic versioning: `PACKAGE_VERSION` drives hatchling, git tags are the source of truth, and `just release` tags without stamping or committing.

**Architecture:** Each of the three packages gets a `_version.py` with `get_version()` (env var, else `YYYY.M.D.dev0`) wired via `[tool.hatch.version] source = "code"`; demos switch setuptools → hatchling. Runtime `__version__` becomes `importlib.metadata.version(...)`. The justfile gains `print-version`, exports `PACKAGE_VERSION` in `build`, rewrites `validate_version`, deletes `_stamp-version`, and simplifies `release` to tag-and-push. `release.yml` exports `PACKAGE_VERSION` from the verified tag.

**Spec:** `.agents/docs/superpowers/specs/2026-08-06-dynamic-versioning-design.md`

**Context for the implementer (verified empirically — do not re-litigate):**
- `uv.lock` records **no** `version =` line for dynamic-version packages, so the lock does not churn daily and `pages.yml`'s `uv run --locked` keeps working.
- Hatchling executes `_version.py` **standalone**, not as a package submodule — a build succeeds even when `__init__.py` raises on import. So `__init__.py` calling `importlib.metadata.version()` is safe at build time.
- Current suite: 127 tests green, `just check-all` exit 0. The tree carries the uncommitted `ghr-pypi` rename plus the user's in-flight release.yml tag-glob change and ASCII banner — leave all of that alone.
- Use the portable `date +%m | sed 's/^0//'` form for unpadded month/day (macOS dev + Linux CI).

---

### Task 1: `_version.py` modules, dynamic pyprojects, runtime `__version__`

**Goal:** All three packages compute their version at build time from `PACKAGE_VERSION`; runtime `__version__` reports the installed version.

**Files:**
- Create: `src/ghr_pypi/_version.py`, `packages/demo-lib/src/ghr_pypi_demo_lib/_version.py`, `packages/demo-app/src/ghr_pypi_demo_app/_version.py`, `tests/test_version.py`
- Modify: `pyproject.toml`, `packages/demo-lib/pyproject.toml`, `packages/demo-app/pyproject.toml`, the three `__init__.py` files, `uv.lock` (via `uv sync`)

**Acceptance Criteria:**
- [ ] `PACKAGE_VERSION=x uv build --wheel` produces `*-x-*.whl` for all three packages; unset → `YYYY.M.D.dev0`
- [ ] No `version = "..."` remains in any pyproject `[project]` table; no `__version__ = "<literal>"` remains
- [ ] `uv.lock` has no `version` line for the three workspace packages
- [ ] Existing 127 tests still pass; new version tests pass

**Verify:** `just test` → 129 passing; `PACKAGE_VERSION=2026.1.2 uv build --wheel && ls dist/` shows the stamped version

**Steps:**

- [ ] **Step 1: Write the failing tests.** Create `tests/test_version.py`:

```python
import re

from packaging.version import Version

from ghr_pypi._version import get_version


def test_get_version_uses_env(monkeypatch):
    monkeypatch.setenv("PACKAGE_VERSION", "2026.8.6.1")
    assert get_version() == "2026.8.6.1"


def test_get_version_dev_fallback(monkeypatch):
    monkeypatch.delenv("PACKAGE_VERSION", raising=False)
    fallback = get_version()
    assert re.fullmatch(r"\d{4}\.\d{1,2}\.\d{1,2}\.dev0", fallback), fallback
    assert str(Version(fallback)) == fallback
```

Run: `just test tests/test_version.py` → Expected: FAIL (`ModuleNotFoundError: ghr_pypi._version`).

- [ ] **Step 2: Create the three `_version.py` files.** Identical content in each (self-contained so every sdist is complete):

```python
"""Build-time version source: ``PACKAGE_VERSION`` or a dated dev version."""

import os
from datetime import datetime, timezone


def get_version() -> str:
    """Return ``PACKAGE_VERSION`` when set, else a dated dev version."""
    now = datetime.now(timezone.utc)
    return os.environ.get("PACKAGE_VERSION", f"{now.year}.{now.month}.{now.day}.dev0")
```

- [ ] **Step 3: Main `pyproject.toml`.** In `[project]`, replace the `version = "2026.8.6.1"` line with `dynamic = ["version"]`. Add above the existing `[tool.hatch.build.targets.wheel]` block:

```toml
[tool.hatch.version]
source = "code"
path = "src/ghr_pypi/_version.py"
expression = "get_version()"
```

- [ ] **Step 4: Demo pyprojects.** For each of `packages/demo-lib/pyproject.toml` and `packages/demo-app/pyproject.toml`: switch the build system to hatchling, make the version dynamic, and add the hatch blocks. demo-lib becomes:

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "ghr-pypi-demo-lib"
dynamic = ["version"]
```

(keep every other `[project]` key as-is), plus at the end of the file:

```toml
[tool.hatch.version]
source = "code"
path = "src/ghr_pypi_demo_lib/_version.py"
expression = "get_version()"

[tool.hatch.build.targets.wheel]
packages = ["src/ghr_pypi_demo_lib"]
```

demo-app is identical with `ghr_pypi_demo_app` / `ghr-pypi-demo-app`.

- [ ] **Step 5: Runtime `__version__`.** In `src/ghr_pypi/__init__.py`, after the module docstring, replace the `__version__` literal so the block reads:

```python
from importlib.metadata import version

__title__ = "ghr-pypi"
__version__ = version("ghr-pypi")
__author__ = "Brian Kohan"
__license__ = "MIT"
__copyright__ = "Copyright 2026 Brian Kohan"
```

In `packages/demo-lib/src/ghr_pypi_demo_lib/__init__.py`:

```python
"""Tiny greeting library for the GitHub Pages PyPI demo."""

from importlib.metadata import version

__version__ = version("ghr-pypi-demo-lib")
```

In `packages/demo-app/src/ghr_pypi_demo_app/__init__.py`, replace its `__version__` literal with `version("ghr-pypi-demo-app")` and add the `from importlib.metadata import version` import alongside the existing imports (ruff's isort will order it).

- [ ] **Step 6: Re-sync and verify.**

Run: `uv sync --all-groups` → rebuilds the three editable installs.
Run: `grep -n 'version' uv.lock | grep -A0 -B2 'ghr-pypi'` — confirm no `version =` line for the three workspace packages (they should show only `name` + `source`).
Run: `just test` → Expected: 129 passing (127 + 2 new).
Run: `PACKAGE_VERSION=2026.1.2 uv build --wheel && ls dist/` → `ghr_pypi-2026.1.2-py3-none-any.whl`; then `PACKAGE_VERSION=2026.1.2 uv build --wheel --project packages/demo-lib --out-dir dist` and the same for demo-app → both stamped `2026.1.2`. Then `rm -rf dist`.
Run: `just fix`; `just check-types`.

*(Driver checkpoint: commit as "Compute package versions dynamically at build time")*

---

### Task 2: justfile — `print-version`, `build`, `validate_version`, `release`

**Goal:** Git tags become the version source; `_stamp-version` is gone; `release` tags and pushes without stamping or committing.

**Files:**
- Modify: `justfile`

**Acceptance Criteria:**
- [ ] `just print-version` on an untagged HEAD emits `YYYY.M.D.devN`; at a tagged commit emits the tag without `v`
- [ ] `just build` stamps the printed version into the wheel
- [ ] `just validate_version vX` passes only when HEAD is at that tag; rejects unnormalized versions
- [ ] `_stamp-version` no longer exists; `release` performs no file edits and no commit

**Verify:** `just print-version` prints a PEP 440 dev version; `grep -c _stamp-version justfile` → 0

**Steps:**

- [ ] **Step 1: Add `print-version`.** Insert above `validate_version`:

```just
# print the version: the exact tag at HEAD, else YYYY.M.D.devN
print-version:
    #!/usr/bin/env bash
    set -euo pipefail
    cd "{{ justfile_directory() }}"

    # A tagged HEAD reports its tag verbatim so the tag, the built wheel and any
    # later print-version at that commit all agree. Amended per Task 2 review:
    # `git describe --exact-match` returns the OLDER tag when two tags point at
    # HEAD (newly reachable now that releases add no commit), so pick the
    # highest version deterministically.
    exact_tag="$(git tag --points-at HEAD --sort=-v:refname | head -n1)"
    if [ -n "$exact_tag" ]; then
        echo "${exact_tag#v}"
        exit 0
    fi

    date_part="$(date +%Y).$(date +%m | sed 's/^0//').$(date +%d | sed 's/^0//')"
    today_iso="$(date +%Y-%m-%d)"

    tag_today="$(
      git for-each-ref --sort=-creatordate \
        --format='%(refname:short) %(creatordate:short)' refs/tags \
      | awk -v d="$today_iso" '$2==d { print $1; exit }'
    )"

    if [ -n "${tag_today:-}" ]; then
        n_part="$(git rev-list --count "${tag_today}..HEAD")"
    else
        n_part="$(git rev-list --count --since='today 00:00' HEAD)"
    fi

    echo "${date_part}.dev${n_part}"
```

- [ ] **Step 2: Replace `validate_version`.** Its entire `[script]` body becomes:

```just
# validate a version tag: PEP 440 normalized and matching the checked-out commit
[script]
validate_version VERSION:
    import subprocess
    from packaging.version import Version
    raw_version = "{{ VERSION }}".lstrip("v")
    version_obj = Version(raw_version)
    assert str(version_obj) == raw_version, f"unnormalized version: {raw_version}"
    printed = subprocess.run(
        ["just", "print-version"], capture_output=True, text=True, check=True
    ).stdout.strip()
    assert printed == raw_version, (
        f"print-version reports {printed}, expected {raw_version}: "
        "is HEAD at the tagged commit?"
    )
    print(raw_version)
```

- [ ] **Step 3: Delete `_stamp-version`** entirely (its comment line through the final `print(version)`).

- [ ] **Step 4: Rewrite `release`.** Keep the `release: install check-all` header; the body becomes:

```just
    #!/usr/bin/env bash
    set -euo pipefail
    cd "{{ justfile_directory() }}"
    [ "$(git branch --show-current)" = "main" ] || { echo "error: release must run from main" >&2; exit 1; }
    [ -z "$(git status --porcelain)" ] || { echo "error: working tree not clean" >&2; exit 1; }
    git fetch --tags origin
    git merge-base --is-ancestor HEAD origin/main || { echo "error: HEAD is not on origin/main; push first" >&2; exit 1; }

    base="$(date +%Y).$(date +%m | sed 's/^0//').$(date +%d | sed 's/^0//')"
    version="$base"
    serial=0
    while git rev-parse -q --verify "refs/tags/v${version}" >/dev/null; do
        serial=$((serial + 1))
        version="${base}.${serial}"
    done

    uv run --no-sync pytest tests/ -q
    git tag -s "v${version}" -m "${version} Release"
    git push origin "v${version}" || { git tag -d "v${version}"; exit 1; }
    echo "Released ${version} — watch it at: gh run watch"
```

Also update its comment line to: `# CalVer-release: verify, sign a tag and push it — triggers release.yml`

Amendments from the Task 2 review (all guard against the same new hazard —
two tags on one commit, possible now that a release adds no commit):
- a final guard, after the merge-base check, refusing to re-tag an already
  released HEAD (`git describe --tags --exact-match HEAD` → error);
- the `|| git tag -d` on push, so a failed push leaves no orphan local tag
  that would silently burn a serial and break the retry;
- `build` resolves the version as arg → inherited `PACKAGE_VERSION` → 
  `print-version` (CI sets the env var; the recipe previously clobbered it)
  and fails loudly if the result is empty;
- `doc/source/conf.py` reads `os.environ.get("PACKAGE_VERSION") or
  ghr_pypi.__version__`, which sidesteps uv's content-keyed build cache and
  makes `just docs`/`docs-live` show the right version.

- [ ] **Step 5: Export `PACKAGE_VERSION` in `build`.** Replace the `build` recipe with:

```just
# build docs and package at the current (or given) version
build VERSION="":
    #!/usr/bin/env bash
    set -euo pipefail
    cd "{{ justfile_directory() }}"
    PACKAGE_VERSION="{{ VERSION }}"
    export PACKAGE_VERSION="${PACKAGE_VERSION:-$(just --quiet print-version)}"
    just build-docs-html
    uv build
```

NOTE (from Task 1's review): `build-docs-html` must be invoked from *inside*
the body, not as a `just` dependency — dependencies run before the body, so a
dependency would build docs before `PACKAGE_VERSION` is exported. That
matters because `build-docs-html` installs the project into an isolated env
(`just run ... --isolated`), and `conf.py` reads the installed version.

- [ ] **Step 6: Verify.**

Run: `just --summary | tr ' ' '\n' | grep -c '^print-version$'` → `1`
Run: `grep -c '_stamp-version' justfile` → `0` (grep exits 1)
Run: `just print-version` → a `YYYY.M.D.devN` string; confirm `python -c "from packaging.version import Version; import sys; v=sys.argv[1]; assert str(Version(v))==v" "$(just print-version)"` succeeds.
Run: `just validate_version "v$(just print-version)"` → prints the version, exit 0.
Negative: `just validate_version v1999.1.1` → AssertionError, non-zero.
Run: `just build && ls dist/` → wheel + sdist named with the printed version; then `rm -rf dist`.
Run: `just fix`; `just test` → 129 passing.

*(Driver checkpoint: commit as "Derive release versions from git tags")*

---

### Task 3: release.yml, docs, full gate

**Goal:** CI stamps the tag version into every built artifact; docs describe the new scheme.

**Files:**
- Modify: `.github/workflows/release.yml`, `.readthedocs.yaml`, `CONTRIBUTING.md`, `AGENTS.md`, `doc/source/changelog.rst`

**Acceptance Criteria:**
- [ ] Verify Tag exports `PACKAGE_VERSION`; `just build` and both demo `uv build` steps inherit it
- [ ] Read the Docs tag builds report the tag version, not a dev date (see Step 1b)
- [ ] Docs state that tags are the source of truth and no version files are edited
- [ ] `just check-all` → exit 0

**Verify:** YAML parses; `uvx zizmor --no-online-audits .github/workflows` no new findings; `just check-all` exit 0

**Steps:**

- [ ] **Step 1: release.yml.** In the build job's "Verify Tag" step, immediately after the existing `echo "RELEASE_VERSION=${RELEASE_VERSION}" >> $GITHUB_ENV` line, add:

```bash
          # hatchling reads this to stamp every wheel/sdist built below
          echo "PACKAGE_VERSION=${RELEASE_VERSION}" >> $GITHUB_ENV
```

No other workflow changes — the demo `uv build` steps inherit the job environment.

- [ ] **Step 1b: `.readthedocs.yaml`** (from Task 1's code review). `doc/source/conf.py` sets `release = ghr_pypi.__version__`, which is now the *installed metadata* version — so an RTD build of tag `v2026.8.5` would render docs labelled with the RTD build date. Replace the `post_install` sync line with a conditional export (a branch build's identifier, e.g. `main`, is not a valid version and must NOT be exported):

```yaml
    post_install:
      - pip install uv
      - |
        if [ "${READTHEDOCS_GIT_IDENTIFIER#v}" != "$READTHEDOCS_GIT_IDENTIFIER" ]; then
          export PACKAGE_VERSION="${READTHEDOCS_GIT_IDENTIFIER#v}"
        fi
        UV_PROJECT_ENVIRONMENT=$READTHEDOCS_VIRTUALENV_PATH uv sync --all-extras --group docs --link-mode=copy
```

(the `#v` test exports only when the identifier starts with `v`, i.e. a release tag.)

- [ ] **Step 2: CONTRIBUTING.md.** Replace the Versioning section body with:

```markdown
`ghr-pypi` uses [CalVer](https://calver.org): `YYYY.M.D`, with a `.N` serial
suffix for repeat releases on the same day. Versions are **not** stored in
any file — a signed git tag is the source of truth and the build stamps it
into the artifacts. Working-tree builds report `YYYY.M.D.devN`; run
`just print-version` to see the current version.
```

- [ ] **Step 3: AGENTS.md.** In the Release section, change the comment on the `just release` line to `# verify, sign tag vYYYY.M.D[.N], push` and replace the following sentence with:

```markdown
One tag ships everything: the tag is the version, hatchling stamps it into
ghr-pypi and both demo packages at build time, and the workflow publishes to
TestPyPI/PyPI plus a single GitHub Release that the Pages index serves.
```

- [ ] **Step 4: Changelog** bullet under the current entry:

```rst
* Versions are computed at build time from git tags; no version strings are
  stored in the repository.
```

- [ ] **Step 5: Full gate.** `uv run --no-sync python -c "import yaml; yaml.safe_load(open('.github/workflows/release.yml'))"`; `uvx zizmor --no-online-audits .github/workflows`; `just fix`; `just test`; `just check-all > /tmp/gate.log 2>&1; echo EXIT=$?` → `EXIT=0`.

*(Driver checkpoint: commit as "Document dynamic versioning; stamp tag version in CI")*

---

## After the plan

Driver: commit the checkpoints. The next `just release` proves it end to end —
the tag alone determines the published version, with no release commit.
