# Asset Digest + Missing-Digest Policy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers-extended-cc:subagent-driven-development (recommended) or superpowers-extended-cc:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **PROJECT RULE (AGENTS.md):** agents never commit or push — the human driver
> does. Implementers stop at "verified in working tree".

**Goal:** Use the GitHub releases API's per-asset `digest` field to avoid downloading assets for hashing; a YAML `missing_digest` policy (`download` default / `no-fragment` / `omit`) governs digest-less assets.

**Architecture:** `Config` gains a validated `missing_digest` enum field. `collect_projects` gains a `missing_digest` parameter and prefers `asset["digest"]` (`sha256:` prefix) over downloading; `FileEntry.sha256` becomes `str | None`; `project.html` renders the `#sha256=` fragment conditionally. The CLI threads `cfg.missing_digest` through.

**Tech Stack:** Python 3.10+, existing stack (no new deps).

**Spec:** `.agents/docs/superpowers/specs/2026-08-05-digest-policy-design.md`

**Context for the implementer:**
- Current suite: 46 tests, all green; `just check-all` green. Existing fixtures (`FIXTURE_RELEASES` in tests/test_index.py) have NO `digest` keys, so default-policy behavior is byte-identical to today and existing tests must pass UNCHANGED.
- `collect_projects` currently: draft-skip → `project_name_from_filename` → duplicate-filename dedupe (warn + skip, `seen.add`) → append `{"filename", "url", "sha256": hash_url(...)}`.
- Known corner case, accepted by design: with `omit`, an omitted digest-less file still claims its filename in `seen`, so a same-named asset in a later repo is treated as a duplicate. First-wins semantics apply to the filename slot, not the surviving entry.

---

### Task 1: Config `missing_digest` key

**Goal:** `Config.missing_digest` (default `"download"`), validated against the three allowed values.

**Files:**
- Modify: `src/github_releases_pypi/config.py`
- Modify: `tests/test_config.py`

**Acceptance Criteria:**
- [ ] All three values load; omitted key → `"download"`
- [ ] Any other value → `ConfigError` naming the allowed values
- [ ] Key accepted by the unknown-key guard

**Verify:** `just test tests/test_config.py` → all pass

**Steps:**

- [ ] **Step 1: Failing tests.** In `tests/test_config.py` add:

```python
@pytest.mark.parametrize("value", ["download", "no-fragment", "omit"])
def test_missing_digest_values(tmp_path, value):
    cfg = load(write(tmp_path, f"repositories: [a/b]\nmissing_digest: {value}\n"))
    assert cfg.missing_digest == value


def test_missing_digest_default(tmp_path):
    assert load(write(tmp_path, "repositories: [a/b]\n")).missing_digest == "download"
```

And one row to the `test_load_errors` parametrize list:

```python
        (
            "repositories: [a/b]\nmissing_digest: always\n",
            "'missing_digest' must be one of",
        ),
```

Run: `just test tests/test_config.py` → Expected: new tests FAIL (unknown key / missing attribute).

- [ ] **Step 2: Implement.** In `src/github_releases_pypi/config.py`:
  - `_KNOWN_KEYS` gains `"missing_digest"`.
  - `Config` gains field `missing_digest: str = "download"` (after `url`).
  - In `load()`, before constructing `Config`:

```python
    missing_digest = raw.get("missing_digest", "download")
    if missing_digest not in ("download", "no-fragment", "omit"):
        raise ConfigError(
            f"{path}: 'missing_digest' must be one of "
            f"download, no-fragment, omit, got {missing_digest!r}"
        )
```

  - Pass `missing_digest=missing_digest` to the `Config(...)` constructor.

- [ ] **Step 3: Verify.** `just test tests/test_config.py` → all pass; `just fix`; `just check-types` → clean.

*(Driver checkpoint: commit as "Add missing_digest config policy")*

---

### Task 2: Digest-aware `collect_projects` + conditional fragment

**Goal:** Digest-bearing assets are never downloaded; digest-less assets follow the policy; fragment renders only when a hash exists.

**Files:**
- Modify: `src/github_releases_pypi/index.py` (`FileEntry`, `collect_projects`)
- Modify: `src/github_releases_pypi/templates/project.html` (anchor line)
- Modify: `tests/test_index.py` (new tests; existing ones untouched)

**Acceptance Criteria:**
- [ ] Asset with `digest: "sha256:<hex>"` → `sha256 == "<hex>"`, `hash_url` never called for it
- [ ] Non-`sha256:` digest treated as absent (policy applies)
- [ ] `download` (default): digest-less assets hashed as today; existing tests pass unchanged
- [ ] `no-fragment`: entry kept with `sha256 None`; rendered anchor has no `#sha256=`
- [ ] `omit`: entry dropped with stderr warning naming the file and policy

**Verify:** `just test tests/test_index.py` → all pass

**Steps:**

- [ ] **Step 1: Failing tests.** Append to `tests/test_index.py`:

```python
DIGEST_RELEASE = [
    {
        "tag_name": "v9.0.0",
        "assets": [
            {
                "name": "digested-9.0.0-py3-none-any.whl",
                "browser_download_url": "https://github.com/o/r/releases/download/v9.0.0/digested-9.0.0-py3-none-any.whl",
                "digest": "sha256:feedbeef",
            },
            {
                "name": "legacy-9.0.0-py3-none-any.whl",
                "browser_download_url": "https://github.com/o/r/releases/download/v9.0.0/legacy-9.0.0-py3-none-any.whl",
            },
        ],
    },
]


def never_hash(url):
    raise AssertionError(f"hash_url called for {url}")


def test_digest_used_without_download():
    projects = index.collect_projects(
        [DIGEST_RELEASE[0] | {"assets": DIGEST_RELEASE[0]["assets"][:1]}],
        hash_url=never_hash,
    )
    assert projects["digested"][0]["sha256"] == "feedbeef"


def test_non_sha256_digest_falls_back_to_download():
    release = {
        "tag_name": "v9.0.1",
        "assets": [
            {
                "name": "oddhash-9.0.1-py3-none-any.whl",
                "browser_download_url": "https://github.com/o/r/releases/download/v9.0.1/oddhash-9.0.1-py3-none-any.whl",
                "digest": "blake2:abc123",
            },
        ],
    }
    projects = index.collect_projects([release], hash_url=fake_hash)
    assert projects["oddhash"][0]["sha256"] == "cafef00d"


def test_missing_digest_download_default():
    projects = index.collect_projects(DIGEST_RELEASE, hash_url=fake_hash)
    assert projects["legacy"][0]["sha256"] == "cafef00d"
    assert projects["digested"][0]["sha256"] == "feedbeef"


def test_missing_digest_no_fragment(tmp_path):
    projects = index.collect_projects(
        DIGEST_RELEASE, hash_url=never_hash, missing_digest="no-fragment"
    )
    assert projects["legacy"][0]["sha256"] is None
    index.write_site(projects, tmp_path, title="T", index_url=None)
    page = (tmp_path / "simple" / "legacy" / "index.html").read_text()
    assert "#sha256=" not in page
    assert 'legacy-9.0.0-py3-none-any.whl</a>' in page
    digested_page = (tmp_path / "simple" / "digested" / "index.html").read_text()
    assert "#sha256=feedbeef" in digested_page


def test_missing_digest_omit(capsys):
    projects = index.collect_projects(
        DIGEST_RELEASE, hash_url=never_hash, missing_digest="omit"
    )
    assert "legacy" not in projects
    assert "digested" in projects
    err = capsys.readouterr().err
    assert "legacy-9.0.0-py3-none-any.whl has no digest, omitted" in err
```

Run: `just test tests/test_index.py` → Expected: new tests FAIL (`collect_projects` has no `missing_digest` param; digest ignored).

- [ ] **Step 2: Implement `index.py`.**
  - `FileEntry.sha256` type → `str | None` (docstring: "sha256 hash, or None when unavailable and the policy allows it").
  - `collect_projects` signature → `def collect_projects(releases, hash_url=hash_url, missing_digest="download"):`; docstring gains: "Assets carrying an API ``digest`` are never downloaded; ``missing_digest`` governs the rest: ``download`` (hash them), ``no-fragment`` (index without a hash), ``omit`` (exclude with a warning)."
  - Replace the append block: after the dedupe `seen.add(asset["name"])`, compute:

```python
            digest = asset.get("digest")
            sha256: str | None
            if (
                isinstance(digest, str)
                and digest.startswith("sha256:")
                and digest[len("sha256:") :]
            ):
                sha256 = digest[len("sha256:") :]
            elif missing_digest == "no-fragment":
                sha256 = None
            elif missing_digest == "omit":
                print(
                    f"warning: {asset['name']} has no digest, omitted "
                    "(missing_digest=omit)",
                    file=sys.stderr,
                )
                continue
            else:
                sha256 = hash_url(asset["browser_download_url"])
            projects.setdefault(normalize(project), []).append(
                {
                    "filename": asset["name"],
                    "url": asset["browser_download_url"],
                    "sha256": sha256,
                }
            )
```

- [ ] **Step 3: Template.** In `src/github_releases_pypi/templates/project.html`, change the anchor line inside the `content` block to:

```html
{% for file in files %}    <a href="{{ file.url }}{% if file.sha256 %}#sha256={{ file.sha256 }}{% endif %}">{{ file.filename }}</a><br/>
```

- [ ] **Step 4: Verify.** `just test tests/test_index.py` → all pass; `just test` → whole suite green (existing tests unchanged); `just fix`; `just check-types` → clean.

*(Driver checkpoint: commit as "Use API asset digests; add missing_digest policy")*

---

### Task 3: CLI wiring + docs + full gate

**Goal:** `cfg.missing_digest` reaches `collect_projects`; README/changelog document the key; full gate green.

**Files:**
- Modify: `src/github_releases_pypi/cli.py` (one call site)
- Modify: `tests/test_cli.py` (one test)
- Modify: `README.md` (config section), `doc/source/changelog.rst` (one bullet)

**Acceptance Criteria:**
- [ ] Config `missing_digest: no-fragment` flows through the CLI to a rendered page without `#sha256=`
- [ ] README documents the key, its three values, and the mid-2025 digest-backfill caveat
- [ ] `just check-all` → exit 0

**Verify:** `just test` → all pass; `just check-all` → exit 0

**Steps:**

- [ ] **Step 1: Failing test.** Append to `tests/test_cli.py`:

```python
def test_cli_missing_digest_policy_flows_through(tmp_path, monkeypatch):
    legacy_release = [
        {
            "tag_name": "v1.0.0",
            "assets": [
                {
                    "name": "legacy-1.0.0-py3-none-any.whl",
                    "browser_download_url": "https://github.com/a/b/releases/download/v1.0.0/legacy-1.0.0-py3-none-any.whl",
                },
            ],
        },
    ]
    monkeypatch.setattr(index, "fetch_releases", lambda repo, token: legacy_release)

    def never_hash(url):
        raise AssertionError("hash_url called despite no-fragment policy")

    monkeypatch.setattr(index, "hash_url", never_hash)
    cfg = config_file(
        tmp_path, "repositories: [a/b]\nmissing_digest: no-fragment\n"
    )
    out = tmp_path / "site"
    result = runner.invoke(
        app, ["--config", str(cfg), "--out", str(out), "--token", "x"]
    )
    assert result.exit_code == 0, all_output(result)
    page = (out / "simple" / "legacy" / "index.html").read_text()
    assert "#sha256=" not in page
```

Run: `just test tests/test_cli.py` → Expected: FAIL (hash_url called — policy not wired).

- [ ] **Step 2: Wire the CLI.** In `cli.py`, the `collect_projects` call becomes:

```python
        projects = index.collect_projects(
            releases, hash_url=index.hash_url, missing_digest=cfg.missing_digest
        )
```

(keep the monkeypatch comment above it).

- [ ] **Step 3: README.** In the "Aggregating multiple repositories" section, extend the YAML example with the key and add after the duplicate-filename paragraph:

```markdown
GitHub's API supplies a sha256 digest for release assets uploaded since
mid-2025, which the builder uses directly — those files are never
downloaded. `missing_digest` controls what happens to older assets that
lack a digest:

| value | behavior |
| --- | --- |
| `download` (default) | download and hash the file |
| `no-fragment` | link it without a `#sha256=` fragment (pip skips integrity verification) |
| `omit` | leave it out of the index, with a warning |
```

And add `missing_digest: download   # optional — see below` to the YAML example block.

- [ ] **Step 4: Changelog.** Add bullet to the 2026.8.5 entry:

```rst
* Use GitHub's asset digests instead of downloading to hash; ``missing_digest`` config policy for digest-less assets.
```

- [ ] **Step 5: Full gate.** `just fix`; `just test` → all pass; `just check-all` → exit 0.

*(Driver checkpoint: commit as "Wire and document the missing_digest policy")*

---

## After the plan

Driver: commit the checkpoints; the feature rides into the next `just release`.
