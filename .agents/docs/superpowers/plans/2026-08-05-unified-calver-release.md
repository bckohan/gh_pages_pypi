# Unified CalVer Release Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers-extended-cc:subagent-driven-development (recommended) or superpowers-extended-cc:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the per-package demo release flow with one CalVer-versioned repository release that ships github-releases-pypi, demo-lib, and demo-app together.

**Architecture:** `just release` (no argument) computes `YYYY.M.D[.N]`, stamps all six version sites, commits, signs and pushes tag `v<version>`. The existing `release.yml` builds all three packages, publishes only the main package to TestPyPI/PyPI (two-artifact split keeps demos off PyPI), creates one GitHub Release with all dists + sigstore signatures, and triggers the Pages rebuild. `demo-release.yml` and the `demo-release` recipe are deleted, as are the old per-package releases/tags.

**Tech Stack:** just, uv, GitHub Actions, gh CLI, sigstore, PyPI trusted publishing.

**Spec:** `.agents/docs/superpowers/specs/2026-08-05-unified-calver-release-design.md`

**Context for the implementer:**
- The justfile sets `set script-interpreter := ['uv', 'run', '--project', '.', '--script']`, so `[script]` recipes are Python run in the project env. It also exports `PYTHONPATH := source_directory()`, so `import github_releases_pypi` resolves to `src/`.
- The repo's working tree currently holds ~31 uncommitted files from the package rename — Task 0 commits them so later commits are clean.
- No files under `src/` change in this plan. The 13 existing tests must keep passing; they are the regression net. There is no unit-testable new Python module — the "tests" for justfile/YAML work are the explicit verify commands in each task.

---

### Task 0: Commit the pending package-rename work

**Goal:** Start from a clean tree so each subsequent task commits only its own changes.

**Files:**
- Modify: none (commits the existing working-tree changes: rename of gh-releases-pypi → github-releases-pypi across 31 files)

**Acceptance Criteria:**
- [ ] `git status --short` is empty afterward
- [ ] Commit contains the renames (`src/github_releases_pypi/`, demo package dirs) and `uv.lock`

**Verify:** `git status --short | wc -l` → `0`; `just test` → `13 passed`

**Steps:**

- [ ] **Step 1: Commit everything currently in the tree**

```bash
git add -A
git commit -m "Rename package to github-releases-pypi

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

- [ ] **Step 2: Verify clean tree and passing tests**

Run: `git status --short | wc -l` → Expected: `0`
Run: `just test` → Expected: `13 passed`

---

### Task 1: Unified `release` recipe in the justfile

**Goal:** `just release` computes CalVer, stamps all six version sites, tests, commits, signs tag `v<version>`, pushes; `validate_version` checks all six sites; `demo-release` is gone.

**Files:**
- Modify: `justfile` (replace `validate_version` at ~line 239, `release` at ~line 253; delete `demo-release` at ~line 259)

**Acceptance Criteria:**
- [ ] `just _stamp-version` stamps exactly six files and prints the version
- [ ] `just validate_version v<version>` passes on the stamped tree, fails on a mismatched one
- [ ] `demo-release` recipe no longer exists
- [ ] Stamping is all-or-nothing: a missing version line aborts before any write

**Verify:** `just _stamp-version && git diff --name-only | wc -l` → `6`, then `just validate_version v$(date +%Y.%-m.%-d)` prints the version, then `git checkout -- pyproject.toml src packages` reverts.

**Steps:**

- [ ] **Step 1: Replace `validate_version` with the six-site check**

Replace the existing `validate_version` recipe (keeping its `[script]` attribute) with:

```just
# validate the given version tag against every package version site
[script]
validate_version VERSION:
    import re
    import tomllib
    from pathlib import Path
    from packaging.version import Version
    import github_releases_pypi
    raw_version = "{{ VERSION }}".lstrip("v")
    version_obj = Version(raw_version)
    assert str(version_obj) == raw_version, f"unnormalized version: {raw_version}"
    for pyproject in (
        "pyproject.toml",
        "packages/demo-lib/pyproject.toml",
        "packages/demo-app/pyproject.toml",
    ):
        actual = tomllib.load(open(pyproject, "rb"))["project"]["version"]
        assert actual == raw_version, f"{pyproject} has {actual}, expected {raw_version}"
    assert github_releases_pypi.__version__ == raw_version, (
        f"github_releases_pypi.__version__ is {github_releases_pypi.__version__}, "
        f"expected {raw_version}"
    )
    for init in (
        "packages/demo-lib/src/github_releases_pypi_demo_lib/__init__.py",
        "packages/demo-app/src/github_releases_pypi_demo_app/__init__.py",
    ):
        match = re.search(r'(?m)^__version__ = "(.*)"$', Path(init).read_text())
        assert match, f"no __version__ line in {init}"
        assert match.group(1) == raw_version, (
            f"{init} has {match.group(1)}, expected {raw_version}"
        )
    print(raw_version)
```

(The demo `__version__` strings are checked textually rather than imported so the
recipe works in CI environments where the demo packages aren't installed.)

- [ ] **Step 2: Add the `_stamp-version` recipe**

Directly below `validate_version`, add:

```just
# stamp today's CalVer (serial-suffixed if already tagged) into every version site
[script]
_stamp-version:
    import re
    import subprocess
    import sys
    from datetime import date
    from pathlib import Path

    VERSION_FILES = [
        (Path("pyproject.toml"), r'(?m)^version = ".*"$', 'version = "{}"'),
        (Path("packages/demo-lib/pyproject.toml"), r'(?m)^version = ".*"$', 'version = "{}"'),
        (Path("packages/demo-app/pyproject.toml"), r'(?m)^version = ".*"$', 'version = "{}"'),
        (Path("src/github_releases_pypi/__init__.py"), r'(?m)^__version__ = ".*"$', '__version__ = "{}"'),
        (Path("packages/demo-lib/src/github_releases_pypi_demo_lib/__init__.py"), r'(?m)^__version__ = ".*"$', '__version__ = "{}"'),
        (Path("packages/demo-app/src/github_releases_pypi_demo_app/__init__.py"), r'(?m)^__version__ = ".*"$', '__version__ = "{}"'),
    ]

    today = date.today()
    base = f"{today.year}.{today.month}.{today.day}"
    tags = subprocess.run(
        ["git", "tag", "--list", f"v{base}*"],
        capture_output=True, text=True, check=True,
    ).stdout.split()
    version, serial = base, 0
    while f"v{version}" in tags:
        serial += 1
        version = f"{base}.{serial}"

    contents = []
    for path, pattern, _ in VERSION_FILES:
        text = path.read_text()
        if not re.search(pattern, text):
            sys.exit(f"error: no version line found in {path}")
        contents.append(text)

    for (path, pattern, template), text in zip(VERSION_FILES, contents):
        path.write_text(re.sub(pattern, template.format(version), text, count=1))

    print(version)
```

- [ ] **Step 3: Replace `release` and delete `demo-release`**

Replace the `release VERSION` recipe and delete the entire `demo-release` recipe
(everything from its comment line through its final `echo`). New `release`:

```just
# CalVer-release the repo: stamp all packages, test, commit, sign tag, push — triggers release.yml
release: install check-all
    #!/usr/bin/env bash
    set -euo pipefail
    cd "{{ justfile_directory() }}"
    [ "$(git branch --show-current)" = "main" ] || { echo "error: release must run from main" >&2; exit 1; }
    [ -z "$(git status --porcelain)" ] || { echo "error: working tree not clean" >&2; exit 1; }
    git fetch --tags origin
    version=$(just _stamp-version)
    uv lock
    uv run --no-sync pytest tests/ -q
    git add -u
    git commit -m "Release ${version}"
    git tag -s "v${version}" -m "${version} Release"
    git push --atomic origin main "v${version}"
    echo "Released ${version} — watch it at: gh run watch"

(Hardened per Task 1 code review: clean-tree guard — `git commit` commits the
whole index, so pre-staged content must be blocked; branch guard; `git fetch
--tags` closes the stale-local-tag serial collision; `git add -u` on a
guaranteed-clean tree stages exactly the stamped files + uv.lock; `--atomic`
prevents a pushed release commit with a rejected tag.)
```

- [ ] **Step 4: Verify recipes parse and demo-release is gone**

Run: `just --summary | tr ' ' '\n' | grep -c '^release$'` → Expected: `1`
Run: `grep -c 'demo-release' justfile` → Expected: `0` (exit 1)

- [ ] **Step 5: Dry-run the stamp + validate cycle, then revert**

Run: `just _stamp-version` → Expected: prints e.g. `2026.8.5`
Run: `git diff --name-only | sort` → Expected: exactly these six files:
```
packages/demo-app/pyproject.toml
packages/demo-app/src/github_releases_pypi_demo_app/__init__.py
packages/demo-lib/pyproject.toml
packages/demo-lib/src/github_releases_pypi_demo_lib/__init__.py
pyproject.toml
src/github_releases_pypi/__init__.py
```
Run: `just validate_version v<printed version>` → Expected: prints the version, exit 0
Negative check: `just validate_version v1999.1.1` → Expected: AssertionError, exit non-zero
Revert: `git checkout -- pyproject.toml src packages` then `git status --short | wc -l` → `0`

- [ ] **Step 6: Commit**

```bash
git add justfile
git commit -m "Replace per-package demo-release with unified CalVer release recipe

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 2: One release workflow

**Goal:** `release.yml` builds and ships all three packages in one GitHub Release (demos excluded from PyPI) and triggers the Pages rebuild; `demo-release.yml` is deleted.

**Files:**
- Modify: `.github/workflows/release.yml` (build job ~line 69-75; github-release job ~line 126-170; tag comment line 14)
- Modify: `.github/workflows/pages.yml` (header comment lines 1-5 only)
- Delete: `.github/workflows/demo-release.yml`

**Acceptance Criteria:**
- [ ] Build job uploads `python-package-distributions` (main only) and `demo-package-distributions` (demos only)
- [ ] TestPyPI/PyPI jobs are byte-for-byte unchanged (they only ever see the main artifact)
- [ ] github-release job merges both artifacts into `dist/`, signs, creates one release, then dispatches `pages.yml`; it has `actions: write`
- [ ] `demo-release.yml` no longer exists

**Verify:** `uv run python -c "import yaml; yaml.safe_load(open('.github/workflows/release.yml'))"` → no output; `ls .github/workflows/demo-release.yml` → No such file; `uvx zizmor --no-online-audits .github/workflows` → no findings (matches pre-change baseline)

**Steps:**

- [ ] **Step 1: Update the tag comment in release.yml**

Line 14, change:
```yaml
      - "v[0-9]*.[0-9]*.[0-9]*" # only publish on version tags (e.g. v1.0.0)
```
to:
```yaml
      - "v[0-9]*.[0-9]*.[0-9]*" # CalVer tags, e.g. v2026.8.5 or v2026.8.5.1
```

- [ ] **Step 2: Build and store demo dists in the build job**

After the "Store the distribution packages" step (ends ~line 75), add:

```yaml
      - name: Build the demo packages
        run: |
          uv build --project packages/demo-lib --out-dir demo-dist
          uv build --project packages/demo-app --out-dir demo-dist
      - name: Store the demo distributions
        uses: actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a
        with:
          name: demo-package-distributions
          path: demo-dist/
```

(Do NOT touch the existing `python-package-distributions` artifact — the
TestPyPI/PyPI jobs download it by name and must keep receiving only the main
package's dists. That artifact split is the guard that keeps the demos off PyPI.)

- [ ] **Step 3: Extend the github-release job**

Add `actions: write` to its permissions:
```yaml
    permissions:
      contents: write # IMPORTANT: mandatory for making GitHub Releases
      id-token: write # IMPORTANT: mandatory for sigstore
      actions: write # dispatch the pages workflow after the release exists
```

After its existing "Download all the dists" step, add (same `path: dist/`, so
both artifacts merge into one directory that the existing sigstore and
`gh release upload dist/**` steps already cover):
```yaml
      - name: Download the demo distributions
        uses: actions/download-artifact@3e5f45b2cfb9172054b4087a40e8e0b5a5461e7c
        with:
          name: demo-package-distributions
          path: dist/
```

At the end of the job, after "Upload artifact signatures to GitHub Release", add:
```yaml
      # Releases created with GITHUB_TOKEN do not fire `release` events in
      # other workflows (GitHub suppresses them to prevent recursion), so
      # trigger the Pages rebuild explicitly.
      - name: Rebuild the Pages index
        env:
          GH_TOKEN: ${{ github.token }}
          GH_REPO: ${{ github.repository }}
        run: gh workflow run pages.yml
```

Amendments from Task 2 code review (job must converge on re-run, since the
tail dispatch step is the most transient-failure-prone and `gh release
create` is not idempotent): prefix the create command with `gh release view
"$GITHUB_REF_NAME" --repo "$GITHUB_REPOSITORY" ||` inside the same folded
block; add `--clobber` to the signature-upload `gh release upload`; comment
above the second download-artifact step that the `dist/` merge is safe only
while package filenames stay distinct.

- [ ] **Step 4: Delete demo-release.yml and fix the pages.yml comment**

```bash
git rm .github/workflows/demo-release.yml
```

In `.github/workflows/pages.yml`, change header comment lines 2-5 from:
```yaml
# deploys it to GitHub Pages. Runs on releases (created or deleted by hand),
# on any push to main (e.g. to pick up index script changes), on manual
# dispatch, and is triggered explicitly by demo-release.yml (releases created
# with GITHUB_TOKEN do not fire `release` events).
```
to:
```yaml
# deploys it to GitHub Pages. Runs on releases (created or deleted by hand),
# on any push to main (e.g. to pick up index script changes), on manual
# dispatch, and is triggered explicitly by release.yml (releases created
# with GITHUB_TOKEN do not fire `release` events).
```

- [ ] **Step 5: Verify**

Run: `uv run python -c "import yaml; yaml.safe_load(open('.github/workflows/release.yml'))"` → Expected: exit 0, no output
Run: `ls .github/workflows/demo-release.yml` → Expected: No such file or directory
Run: `uvx zizmor --no-online-audits .github/workflows` → Expected: same findings as before the change (run it on the base commit first if unsure; no NEW findings allowed)
Run: `grep -n 'demo-package-distributions' .github/workflows/release.yml | wc -l` → Expected: `2` (upload + download)

- [ ] **Step 6: Commit**

```bash
git add .github/workflows
git commit -m "Ship all packages in one release; delete demo-release workflow

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 3: Delete the old per-package releases and tags

**Goal:** Remove `demo-lib-v2026.8.4` and `demo-app-v2026.8.4` (GitHub Releases + git tags, remote and local) so the index only ever reflects unified releases.

**Files:** none (GitHub + git state only; no commit in this task)

**Acceptance Criteria:**
- [ ] `gh release list` shows no releases
- [ ] No `demo-*` tags locally or on origin

**Verify:** `gh release list | wc -l` → `0`; `git tag -l 'demo-*' | wc -l` → `0`; `git ls-remote --tags origin | wc -l` → `0`

**Steps:**

- [ ] **Step 1: Delete the releases and their remote tags**

```bash
gh release delete demo-lib-v2026.8.4 --yes --cleanup-tag
gh release delete demo-app-v2026.8.4 --yes --cleanup-tag
```

- [ ] **Step 2: Delete the local tags**

```bash
git tag -d demo-lib-v2026.8.4 demo-app-v2026.8.4
```

- [ ] **Step 3: Verify**

Run: `gh release list | wc -l` → Expected: `0`
Run: `git tag -l 'demo-*' | wc -l` → Expected: `0`
Run: `git ls-remote --tags origin | wc -l` → Expected: `0`

Note: until the first unified release is cut, `pages.yml` fails by design
(empty index). That is the documented fresh-repo behavior, not a regression.

---

### Task 4: Documentation sweep + full gate

**Goal:** Every doc describes the unified CalVer flow; full check suite passes.

**Files:**
- Modify: `AGENTS.md` (Release section, ~line 62-65)
- Modify: `README.md` (line ~52 workflow pointer; lines ~89-94 demo release instructions)
- Modify: `CONTRIBUTING.md` (Versioning + Issuing Releases sections, ~lines 92-104)

**Acceptance Criteria:**
- [ ] `grep -rn 'demo-release' --exclude-dir=.agents --exclude-dir=.git .` finds nothing
- [ ] No doc claims semver
- [ ] `just check-all` passes

**Verify:** `grep -rn 'demo-release\|semantic versioning' README.md CONTRIBUTING.md AGENTS.md doc/ | wc -l` → `0`; `just check-all` → exit 0

**Steps:**

- [ ] **Step 1: AGENTS.md Release section**

Replace:
````markdown
### Release
```bash
just release 1.2.3   # validates version, tags, and pushes tag to GitHub
```
````
with:
````markdown
### Release
```bash
just release      # CalVer-stamp all packages, sign tag vYYYY.M.D[.N], push
```
One tag ships everything: github-releases-pypi to TestPyPI/PyPI plus a single
GitHub Release containing all three packages' dists, which the Pages index
serves.
````

- [ ] **Step 2: README.md**

Line ~52 — change the workflow pointer:
```markdown
2. Publish your packages' wheels/sdists as GitHub Release assets (see the
   `github-release` job in [`release.yml`](.github/workflows/release.yml)
   for a tag-triggered example).
```

Lines ~89-94 — replace:
```markdown
Cut a new demo release (CalVer-bumps the package, tests, commits, tags,
pushes — the workflows do the rest):

​```sh
just demo-release demo-lib
​```
```
with:
```markdown
Cut a new release (CalVer-stamps every package — the tool and both demos —
tests, commits, tags, pushes; the workflows do the rest):

​```sh
just release
​```
```

- [ ] **Step 3: CONTRIBUTING.md Versioning + Issuing Releases**

Replace:
```markdown
## Versioning

`github-releases-pypi` strictly adheres to [semantic versioning](https://semver.org).
```
with:
```markdown
## Versioning

`github-releases-pypi` uses [CalVer](https://calver.org): `YYYY.M.D`, with a
`.N` serial suffix for repeat releases on the same day. The tool and the demo
packages always share the release version.
```

And change the release shortcut block from `just release x.x.x` to:
```markdown
​```sh
just release
​```
```

- [ ] **Step 4: Sweep and verify**

Run: `grep -rn 'demo-release\|semantic versioning' README.md CONTRIBUTING.md AGENTS.md doc/` → Expected: no matches
Run: `just check-all` → Expected: exit 0
Run: `just test` → Expected: `13 passed`

- [ ] **Step 5: Commit**

```bash
git add AGENTS.md README.md CONTRIBUTING.md
git commit -m "Document the unified CalVer release flow

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

## After the plan

The first real `just release` (user-triggered, when ready) is the end-to-end
proof: release.yml → TestPyPI/PyPI publish + one GitHub Release (six dists +
signatures) → pages.yml serving github-releases-pypi, demo-lib, and demo-app
from the Pages index.
