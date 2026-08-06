# Asset Mirroring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers-extended-cc:subagent-driven-development (recommended) or superpowers-extended-cc:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **PROJECT RULE (AGENTS.md):** agents never commit or push — the human driver
> does. Implementers stop at "verified in working tree".

**Goal:** `mirror: true` (or `--mirror` with the single-repo shortcut) downloads every asset into `site/files/<project>/` via GitHub's authenticated API endpoint, verifies/computes hashes while streaming, and rewrites index links to relative paths — a self-contained site that works for private repositories.

**Architecture:** `Config.mirror: bool` (exclusive with an explicit `missing_digest`). `FileEntry` gains internal `api_url`; `collect_projects(defer_hash=True)` skips all hashing under mirror mode. New `mirror_files(projects, out_dir, token, *, opener=...)` reuses existing files by hash, downloads with `Authorization` + `Accept: application/octet-stream`, hard-errors (`MirrorError`) on digest mismatch, and relinks entries to `../../files/<project>/<filename>`. CLI wires `--mirror`/`cfg.mirror` and error paths.

**Tech Stack:** existing stack; no new dependencies (urllib + hashlib).

**Spec:** `.agents/docs/superpowers/specs/2026-08-05-asset-mirroring-design.md`

**Context for the implementer:**
- Current suite: 78 tests green; `just check-all` green. The tree carries earlier uncommitted (driver-pending) features — leave everything alone except this plan's files.
- IMPORTANT subtlety: `mirror_files`' `opener` default binds `urllib.request.urlopen` at def time — monkeypatching `urllib.request.urlopen` in tests will NOT affect it. Unit tests inject `opener=`; the CLI test monkeypatches `index.mirror_files` itself.
- Bandit runs in CI: any `urlopen` on a variable URL needs the https guard + `# nosec B310` comment, matching `hash_url`'s existing pattern.

---

### Task 1: Config `mirror` key

**Goal:** `Config.mirror: bool = False`, bool-validated; explicit `missing_digest` alongside `mirror: true` rejected.

**Files:**
- Modify: `src/github_releases_pypi/config.py`, `tests/test_config.py`

**Acceptance Criteria:**
- [ ] `mirror: true` / `false` load; omitted → False
- [ ] Non-bool → `ConfigError`; `mirror: true` + explicit `missing_digest` → `ConfigError`
- [ ] `mirror: true` + NO `missing_digest` key loads fine; `mirror: false` + `missing_digest` loads fine

**Verify:** `just test tests/test_config.py` → all pass

**Steps:**

- [ ] **Step 1: Failing tests.**

```python
@pytest.mark.parametrize("value,expected", [("true", True), ("false", False)])
def test_mirror_values(tmp_path, value, expected):
    cfg = load(write(tmp_path, f"repositories: [a/b]\nmirror: {value}\n"))
    assert cfg.mirror is expected


def test_mirror_default(tmp_path):
    assert load(write(tmp_path, "repositories: [a/b]\n")).mirror is False


def test_mirror_allows_missing_digest_when_off(tmp_path):
    cfg = load(
        write(tmp_path, "repositories: [a/b]\nmirror: false\nmissing_digest: omit\n")
    )
    assert cfg.mirror is False and cfg.missing_digest == "omit"
```

Error rows for `test_load_errors`:

```python
        ("repositories: [a/b]\nmirror: maybe\n", "'mirror' must be true or false"),
        ("repositories: [a/b]\nmirror: 1\n", "'mirror' must be true or false"),
        (
            "repositories: [a/b]\nmirror: true\nmissing_digest: download\n",
            "'missing_digest' has no effect when 'mirror' is enabled",
        ),
```

Run: `just test tests/test_config.py` → Expected: FAIL (unknown key / missing attribute).

- [ ] **Step 2: Implement.** In `config.py`: `_KNOWN_KEYS` gains `"mirror"`; `Config` field `mirror: bool = False` (after `formats`); in `load()` after the formats block:

```python
    mirror = raw.get("mirror", False)
    if not isinstance(mirror, bool):
        raise ConfigError(f"{path}: 'mirror' must be true or false")
    if mirror and "missing_digest" in raw:
        raise ConfigError(
            f"{path}: 'missing_digest' has no effect when 'mirror' is enabled"
        )
```

Pass `mirror=mirror` to `Config(...)`.

- [ ] **Step 3: Verify.** `just test tests/test_config.py` → all pass; `just fix`; `just check-types`; `just test` → suite green.

*(Driver checkpoint: commit as "Add mirror config key")*

---

### Task 2: `FileEntry.api_url` + `defer_hash`

**Goal:** entries carry the asset's API URL; `defer_hash=True` skips all hashing/policy (sha256 = digest or None).

**Files:**
- Modify: `src/github_releases_pypi/index.py`, `tests/test_index.py`

**Acceptance Criteria:**
- [ ] `FileEntry.api_url: str` populated from asset `url` ("" when absent); never appears in HTML/JSON output
- [ ] `defer_hash=True`: digest-less asset → sha256 None, `hash_url` never called, `missing_digest` ignored
- [ ] Existing tests pass unchanged

**Verify:** `just test tests/test_index.py` → all pass

**Steps:**

- [ ] **Step 1: Failing tests.**

```python
def test_collect_projects_captures_api_url():
    release = {
        "tag_name": "v5.0.0",
        "assets": [
            {
                "name": "apiurl-5.0.0-py3-none-any.whl",
                "browser_download_url": "https://github.com/o/r/releases/download/v5.0.0/apiurl-5.0.0-py3-none-any.whl",
                "url": "https://api.github.com/repos/o/r/releases/assets/123",
                "digest": "sha256:beef",
            },
        ],
    }
    entry = index.collect_projects([release], hash_url=never_hash)["apiurl"][0]
    assert entry["api_url"] == "https://api.github.com/repos/o/r/releases/assets/123"


def test_collect_projects_defer_hash():
    projects = index.collect_projects(
        DIGEST_RELEASE, hash_url=never_hash, defer_hash=True
    )
    assert projects["digested"][0]["sha256"] == "feedbeef"
    assert projects["legacy"][0]["sha256"] is None


def test_collect_projects_defer_hash_ignores_policy():
    projects = index.collect_projects(
        DIGEST_RELEASE, hash_url=never_hash, defer_hash=True, missing_digest="omit"
    )
    assert "legacy" in projects  # omit does not apply under defer_hash
```

Run → Expected: FAIL (no param / KeyError api_url).

- [ ] **Step 2: Implement.** In `index.py`:
  - `FileEntry` gains `api_url: str` (docstring: "the asset's API endpoint, used for authenticated mirror downloads; not emitted").
  - `collect_projects(releases, hash_url=hash_url, missing_digest="download", defer_hash=False)`; docstring gains: "With ``defer_hash`` no hashing happens at all — sha256 is the API digest or None and ``missing_digest`` does not apply (mirroring computes hashes from the downloaded bytes)."
  - In the digest/policy chain, fold the defer condition into the
    no-fragment branch (identical body, proven-equivalent truth table):

```python
            elif defer_hash or missing_digest == "no-fragment":
                sha256 = None
```

  and the appended entry gains `"api_url": asset.get("url", ""),`.

- [ ] **Step 3: Verify.** `just test tests/test_index.py` → all pass; `just test` → suite green (JSON emitters pick keys explicitly — api_url cannot leak; the existing JSON tests prove it); `just fix`; `just check-types`.

*(Driver checkpoint: commit as "Carry asset API URLs; defer hashing under mirror mode")*

---

### Task 3: `mirror_files`

**Goal:** download/reuse every file under `out/files/<project>/`, verify or compute hashes, relink entries relatively.

**Files:**
- Modify: `src/github_releases_pypi/index.py`, `tests/test_index.py`

**Acceptance Criteria:**
- [ ] Existing file with matching hash (or no expected hash) reused — zero downloads
- [ ] Corrupted existing file re-downloaded; digest mismatch on download → `MirrorError`, partial file removed
- [ ] Requests hit `api_url` with `Accept: application/octet-stream` + `Authorization: Bearer <token>`; non-https `api_url` → ValueError
- [ ] Entry URLs rewritten to `../../files/<project>/<filename>`; sha256 always set afterward

**Verify:** `just test tests/test_index.py` → all pass

**Steps:**

- [ ] **Step 1: Failing tests.** (test helpers at module level in `tests/test_index.py`; `import hashlib`, `import io` at top)

```python
def make_opener(payload=b"wheel-bytes", requests_log=None):
    class FakeResponse(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    def opener(request, timeout=None):
        if requests_log is not None:
            requests_log.append(request)
        return FakeResponse(payload)

    return opener


MIRROR_RELEASE = [
    {
        "tag_name": "v7.0.0",
        "assets": [
            {
                "name": "mirrored-7.0.0-py3-none-any.whl",
                "browser_download_url": "https://github.com/o/r/releases/download/v7.0.0/mirrored-7.0.0-py3-none-any.whl",
                "url": "https://api.github.com/repos/o/r/releases/assets/7",
            },
        ],
    },
]


def mirror_projects():
    return index.collect_projects(
        MIRROR_RELEASE, hash_url=never_hash, defer_hash=True
    )


def test_mirror_files_downloads_and_relinks(tmp_path):
    projects = mirror_projects()
    log = []
    index.mirror_files(projects, tmp_path, "tok", opener=make_opener(requests_log=log))
    entry = projects["mirrored"][0]
    dest = tmp_path / "files" / "mirrored" / "mirrored-7.0.0-py3-none-any.whl"
    assert dest.read_bytes() == b"wheel-bytes"
    assert entry["sha256"] == hashlib.sha256(b"wheel-bytes").hexdigest()
    assert entry["url"] == "../../files/mirrored/mirrored-7.0.0-py3-none-any.whl"
    assert len(log) == 1
    assert log[0].get_full_url() == "https://api.github.com/repos/o/r/releases/assets/7"
    assert log[0].get_header("Accept") == "application/octet-stream"
    assert log[0].get_header("Authorization") == "Bearer tok"


def test_mirror_files_reuses_matching_existing(tmp_path):
    projects = mirror_projects()
    dest = tmp_path / "files" / "mirrored" / "mirrored-7.0.0-py3-none-any.whl"
    dest.parent.mkdir(parents=True)
    dest.write_bytes(b"already-here")
    projects["mirrored"][0]["sha256"] = hashlib.sha256(b"already-here").hexdigest()
    log = []
    index.mirror_files(projects, tmp_path, "tok", opener=make_opener(requests_log=log))
    assert log == []  # no download
    assert dest.read_bytes() == b"already-here"


def test_mirror_files_adopts_existing_hash(tmp_path):
    projects = mirror_projects()  # sha256 is None (no digest)
    dest = tmp_path / "files" / "mirrored" / "mirrored-7.0.0-py3-none-any.whl"
    dest.parent.mkdir(parents=True)
    dest.write_bytes(b"already-here")
    log = []
    index.mirror_files(projects, tmp_path, "tok", opener=make_opener(requests_log=log))
    assert log == []
    assert (
        projects["mirrored"][0]["sha256"]
        == hashlib.sha256(b"already-here").hexdigest()
    )


def test_mirror_files_redownloads_corrupted(tmp_path):
    projects = mirror_projects()
    dest = tmp_path / "files" / "mirrored" / "mirrored-7.0.0-py3-none-any.whl"
    dest.parent.mkdir(parents=True)
    dest.write_bytes(b"corrupted")
    projects["mirrored"][0]["sha256"] = hashlib.sha256(b"wheel-bytes").hexdigest()
    log = []
    index.mirror_files(projects, tmp_path, "tok", opener=make_opener(requests_log=log))
    assert len(log) == 1
    assert dest.read_bytes() == b"wheel-bytes"


def test_mirror_files_digest_mismatch(tmp_path):
    projects = mirror_projects()
    projects["mirrored"][0]["sha256"] = "deadbeef"  # advertised digest, wrong
    with pytest.raises(index.MirrorError, match="mirrored-7.0.0-py3-none-any.whl"):
        index.mirror_files(projects, tmp_path, "tok", opener=make_opener())
    assert not (
        tmp_path / "files" / "mirrored" / "mirrored-7.0.0-py3-none-any.whl"
    ).exists()


def test_mirror_files_rejects_non_https(tmp_path):
    projects = mirror_projects()
    projects["mirrored"][0]["api_url"] = "http://api.github.com/insecure"
    with pytest.raises(ValueError, match="non-https"):
        index.mirror_files(projects, tmp_path, "tok", opener=make_opener())


def test_write_site_after_mirror(tmp_path):
    projects = mirror_projects()
    index.mirror_files(projects, tmp_path, "tok", opener=make_opener())
    index.write_site(projects, tmp_path, title="T", index_url=None)
    page = (tmp_path / "simple" / "mirrored" / "index.html").read_text()
    assert 'href="../../files/mirrored/mirrored-7.0.0-py3-none-any.whl#sha256=' in page
    data = json.loads((tmp_path / "simple" / "mirrored" / "index.json").read_text())
    assert data["files"][0]["url"] == "../../files/mirrored/mirrored-7.0.0-py3-none-any.whl"
```

(`tests/test_index.py` needs `import pytest` if not already imported.)
Run → Expected: FAIL (`mirror_files` doesn't exist).

- [ ] **Step 2: Implement in `index.py`.** Add `import hashlib` if not present (it is — used by `hash_url`); `from collections.abc import Callable` already imported.

```python
class MirrorError(RuntimeError):
    """Raised when a mirrored download does not match its advertised digest."""


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def mirror_files(
    projects: Projects,
    out_dir: Path,
    token: str,
    *,
    opener: Callable[..., Any] = urllib.request.urlopen,
) -> None:
    """Download every file into ``out_dir/files`` and relink entries.

    Files already present with the expected sha256 are reused (when no
    digest was advertised, the existing file's hash is adopted). Downloads
    go through the asset's authenticated API endpoint, hash while
    streaming, and a mismatch with the advertised digest raises
    ``MirrorError``. Entry URLs are rewritten to site-relative paths.
    """
    for project, files in projects.items():
        project_dir = out_dir / "files" / project
        for entry in files:
            relative_url = f"../../files/{project}/{entry['filename']}"
            dest = project_dir / entry["filename"]
            if dest.is_file():
                existing = _hash_file(dest)
                if entry["sha256"] is None or existing == entry["sha256"]:
                    entry["sha256"] = existing
                    entry["url"] = relative_url
                    continue
            if not entry["api_url"].startswith("https://"):
                raise ValueError(
                    f"refusing to fetch non-https URL: {entry['api_url']}"
                )
            project_dir.mkdir(parents=True, exist_ok=True)
            request = urllib.request.Request(
                entry["api_url"],
                headers={
                    "Accept": "application/octet-stream",
                    "Authorization": f"Bearer {token}",
                },
            )
            digest = hashlib.sha256()
            try:
                with opener(  # nosec B310 — scheme validated above
                    request, timeout=30
                ) as response, dest.open("wb") as sink:
                    for chunk in iter(lambda: response.read(65536), b""):
                        digest.update(chunk)
                        sink.write(chunk)
            except BaseException:
                dest.unlink(missing_ok=True)
                raise
            computed = digest.hexdigest()
            if entry["sha256"] is not None and computed != entry["sha256"]:
                dest.unlink(missing_ok=True)
                raise MirrorError(
                    f"{entry['filename']}: downloaded sha256 {computed} does not "
                    f"match advertised digest {entry['sha256']}"
                )
            entry["sha256"] = computed
            entry["url"] = relative_url
```

- [ ] **Step 3: Verify.** `just test tests/test_index.py` → all pass; `just test` → suite green; `just fix`; `just check-types`; `uvx bandit -c pyproject.toml -r src` → no findings.

**Amendments from Task 3 code review (hostile-input hardening):**
- `collect_projects` gains an unsafe-asset-name guard (warn-and-skip) right
  after reading `asset["name"]`: names containing `/`, `\`, `:`, or starting
  with `.` are skipped — pathlib's `/` operator discards the left operand for
  absolute paths, so a hostile filename could otherwise write outside
  `out_dir` (also protects `write_site`'s project directories).
- `mirror_files` adds a containment check anchored to the fixed files root
  (`dest.resolve().is_relative_to((out_dir / "files").resolve())` plus the
  parent equality → `MirrorError`) since it accepts arbitrary `Projects`
  dicts — anchoring to `project_dir` alone is a no-op when the project KEY
  is hostile. Non-numeric Content-Length is treated as absent rather than
  escaping as ValueError.
- Downloads stream to `<name>.part` and `replace()` onto `dest` only after
  ALL verification (Content-Length and digest) passes — a killed build can
  no longer leave a truncation that a later digest-less run adopts as truth,
  and a mid-stream failure no longer destroys a good cached file.
- Content-Length verified when present → `MirrorError` "truncated download".
- Asset-level errors consolidated as `MirrorError` (missing api_url,
  non-https, truncation, digest mismatch) — one exception surface for the
  CLI.
- Extra tests: mid-stream failure (cache survives, no `.part` remains),
  truncated response, unsafe-name skip (relative + absolute).

*(Driver checkpoint: commit as "Add mirror_files: authenticated downloads, verification, relative links")*

---

### Task 4: CLI `--mirror`

**Goal:** `--mirror` on the shortcut path; `cfg.mirror` drives defer_hash + mirroring; MirrorError/URLError surfaced.

**Files:**
- Modify: `src/github_releases_pypi/cli.py`, `tests/test_cli.py`

**Acceptance Criteria:**
- [ ] `--mirror` with positional REPO → mirroring runs (defer_hash + mirror_files with the token)
- [ ] `--mirror` with `--config` → exit 1, "with --config, set 'mirror' in the config file"
- [ ] Config `mirror: true` also triggers mirroring
- [ ] `MirrorError` → `error: <message>`, exit 1

**Verify:** `just test tests/test_cli.py` → all pass

**Steps:**

- [ ] **Step 1: Failing tests.**

```python
def test_cli_mirror_flag(tmp_path, monkeypatch):
    monkeypatch.setattr(index, "fetch_releases", lambda repo, token: FIXTURE_RELEASES)
    calls = []

    def fake_mirror(projects, out_dir, token, **kwargs):
        calls.append((out_dir, token))
        for files in projects.values():
            for entry in files:
                entry["sha256"] = "cafef00d"
                entry["url"] = f"../../files/x/{entry['filename']}"

    monkeypatch.setattr(index, "mirror_files", fake_mirror)

    def never_hash(url):
        raise AssertionError("hash_url called despite mirror mode")

    monkeypatch.setattr(index, "hash_url", never_hash)
    out = tmp_path / "site"
    result = runner.invoke(
        app,
        ["bckohan/github-releases-pypi", "--out", str(out), "--token", "tok", "--mirror"],
    )
    assert result.exit_code == 0, all_output(result)
    assert calls == [(out, "tok")]
    page = (out / "simple" / "github-releases-pypi-demo-lib" / "index.html").read_text()
    assert "../../files/x/" in page


def test_cli_mirror_with_config_errors(tmp_path):
    cfg = config_file(tmp_path, "repositories: [a/b]\n")
    result = runner.invoke(
        app,
        ["--config", str(cfg), "--out", str(tmp_path), "--token", "x", "--mirror"],
    )
    assert result.exit_code == 1
    assert "with --config, set 'mirror' in the config file" in all_output(result)


def test_cli_mirror_from_config(tmp_path, monkeypatch):
    monkeypatch.setattr(index, "fetch_releases", lambda repo, token: FIXTURE_RELEASES)
    calls = []

    def fake_mirror(projects, out_dir, token, **kwargs):
        calls.append(token)
        for files in projects.values():
            for entry in files:
                entry["sha256"] = "cafef00d"
                entry["url"] = f"../../files/x/{entry['filename']}"

    monkeypatch.setattr(index, "mirror_files", fake_mirror)
    cfg = config_file(tmp_path, "repositories: [a/b]\nmirror: true\n")
    result = runner.invoke(
        app, ["--config", str(cfg), "--out", str(tmp_path / "s"), "--token", "tok"]
    )
    assert result.exit_code == 0, all_output(result)
    assert calls == ["tok"]


def test_cli_mirror_error_surfaces(tmp_path, monkeypatch):
    monkeypatch.setattr(index, "fetch_releases", lambda repo, token: FIXTURE_RELEASES)

    def boom(projects, out_dir, token, **kwargs):
        raise index.MirrorError("bad.whl: downloaded sha256 x does not match y")

    monkeypatch.setattr(index, "mirror_files", boom)
    result = runner.invoke(
        app,
        ["bckohan/github-releases-pypi", "--out", str(tmp_path), "--token", "t", "--mirror"],
    )
    assert result.exit_code == 1
    assert "bad.whl" in all_output(result)
```

Run → Expected: FAIL (no --mirror option).

- [ ] **Step 2: Implement.** In `cli.py`:
  - New option (after `token`):

```python
    mirror: Annotated[
        bool,
        typer.Option(
            "--mirror",
            help="Download assets into the site instead of linking to GitHub "
            "(with --config, set 'mirror' in the config file instead)",
        ),
    ] = False,
```

  - After the config/shortcut split: in the `--config` branch, first check
    `if mirror:` → echo `"error: with --config, set 'mirror' in the config file"`, exit 1.
    In the shortcut branch, the `Config(...)` gains `mirror=mirror`.
  - `collect_projects` call gains `defer_hash=cfg.mirror`.
  - After the empty-index check, before `write_site`:

```python
    if cfg.mirror:
        try:
            index.mirror_files(projects, out, token)
        except index.MirrorError as error:
            typer.echo(f"error: {error}", err=True)
            raise typer.Exit(1) from error
        except urllib.error.URLError as error:
            typer.echo(
                f"error: downloading a release asset failed: {error}", err=True
            )
            raise typer.Exit(1) from error
```

- [ ] **Step 3: Verify.** `just test tests/test_cli.py` → all pass; `just test` → suite green; `just fix`; `just check-types`.

*(Driver checkpoint: commit as "Add --mirror / mirror config wiring")*

---

### Task 5: Docs + full gate

**Goal:** README "Mirroring assets" section; changelog; full gate green.

**Files:**
- Modify: `README.md` (new section after "JSON Simple API"), `doc/source/changelog.rst`

**Acceptance Criteria:**
- [ ] README covers: what mirroring does, private-repo story, `--mirror` + config examples, actions/cache recipe, missing_digest exclusivity, relative/relocatable links, stale-file caveat
- [ ] `just check-all` → exit 0

**Verify:** `just check-all` → exit 0; `just test` → all pass

**Steps:**

- [ ] **Step 1: README section** (after "JSON Simple API"):

```markdown
## Mirroring assets

With `mirror: true` (or `--mirror` on the single-repository form), the
builder downloads every asset into `site/files/<project>/` and the index
links to those local copies with relative URLs — the site is fully
self-contained and relocatable, and GitHub is out of the serving path.

This is also the way to index **private repositories**: downloads go
through GitHub's authenticated asset API using your `--token`, and the
resulting site can be served behind whatever auth your host provides
(pip and uv understand basic auth and netrc). Direct links to a private
repo's assets would not be fetchable by pip.

​```sh
github-releases-pypi yourorg/private-repo --out site --token $TOKEN --mirror
​```

Every mirrored file is hashed while downloading; when GitHub's API
advertises a digest it is verified and a mismatch fails the build. The
`missing_digest` option does not apply (and is rejected) under mirroring —
every file gets a real hash. Files already present in `site/files/` with
the right hash are not re-downloaded, so repeat builds only fetch new
assets. In GitHub Actions, persist them between runs:

​```yaml
- uses: actions/cache@v4
  with:
    path: site/files
    key: mirrored-assets-${{ github.run_id }}
    restore-keys: mirrored-assets-
​```

Note: files removed from releases are not pruned from `site/files/` —
clear the directory (or the cache) to drop them.
```

- [ ] **Step 2: Changelog bullet** under 2026.8.5:

```rst
* ``mirror`` mode: download assets into the site (private-repo support,
  self-contained output, incremental re-builds).
```

- [ ] **Step 3: Full gate.** `just fix`; `just test` → all pass; `just check-all` → exit 0 (real run).

*(Driver checkpoint: commit as "Document asset mirroring")*

---

## After the plan

Driver: commit the checkpoints. Phase 3 per `direction.md`: PEP 658 metadata
(composes with mirroring — the bytes are already local).
