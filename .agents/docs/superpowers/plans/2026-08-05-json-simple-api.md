# PEP 691 JSON Simple API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers-extended-cc:subagent-driven-development (recommended) or superpowers-extended-cc:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **PROJECT RULE (AGENTS.md):** agents never commit or push — the human driver
> does. Implementers stop at "verified in working tree".

**Goal:** Emit a PEP 691/700 JSON Simple API (api-version 1.1) alongside — or instead of — the HTML index, controlled by a `formats:` config list defaulting to both.

**Architecture:** `Config.formats: tuple[Formats, ...]` (Literal alias, validated). `FileEntry` gains `size`/`upload_time` (free from the GitHub asset API). New `version_from_filename` helper + version sorting via `packaging`. `write_site` gains `formats=("html", "json")` and writes `simple/index.json` + `simple/<project>/index.json` via `json.dumps` (never Jinja). Landing page only when `html` is included. CLI threads `cfg.formats`.

**Tech Stack:** existing stack + `packaging>=23` as a new runtime dependency (version sorting).

**Spec:** `.agents/docs/superpowers/specs/2026-08-05-json-simple-api-design.md`

**Context for the implementer:**
- Current suite: 60 tests green; `just check-all` green. Existing tests assert HTML substrings and never enumerate output files, so emitting extra `.json` files under the default keeps them green; `FileEntry` gains keys existing tests don't inspect.
- `FIXTURE_RELEASES` assets have no `size`/`created_at` keys — `collect_projects` must default them (`size` 0, `upload_time` None) so existing fixtures keep working untouched.
- `packaging` is currently only a dev-env presence (justfile scripts); it must become a `[project]` runtime dependency.

---

### Task 1: Config `formats` key

**Goal:** `Config.formats: tuple[Formats, ...] = ("html", "json")`, validated (non-empty list, elements html/json, no duplicates).

**Files:**
- Modify: `src/github_releases_pypi/config.py`
- Modify: `tests/test_config.py`

**Acceptance Criteria:**
- [ ] `[html]`, `[json]`, `[html, json]` load; omitted key → `("html", "json")`
- [ ] Empty list / non-list / unknown element / duplicates → `ConfigError` echoing the offending value
- [ ] `Formats = Literal["html", "json"]` alias exported (mirrors `MissingDigest`)

**Verify:** `just test tests/test_config.py` → all pass; `just check-types` → clean

**Steps:**

- [ ] **Step 1: Failing tests.** Add to `tests/test_config.py`:

```python
@pytest.mark.parametrize(
    "value,expected",
    [
        ("[html]", ("html",)),
        ("[json]", ("json",)),
        ("[html, json]", ("html", "json")),
        ("[json, html]", ("json", "html")),
    ],
)
def test_formats_values(tmp_path, value, expected):
    cfg = load(write(tmp_path, f"repositories: [a/b]\nformats: {value}\n"))
    assert cfg.formats == expected


def test_formats_default(tmp_path):
    assert load(write(tmp_path, "repositories: [a/b]\n")).formats == ("html", "json")
```

And error rows in `test_load_errors`:

```python
        ("repositories: [a/b]\nformats: []\n", "'formats' must be a non-empty list"),
        ("repositories: [a/b]\nformats: html\n", "'formats' must be a non-empty list"),
        (
            "repositories: [a/b]\nformats: [xml]\n",
            "'formats' entries must be html or json, got 'xml'",
        ),
        (
            "repositories: [a/b]\nformats: [html, html]\n",
            "'formats' contains duplicates",
        ),
```

Run: `just test tests/test_config.py` → Expected: FAIL (unknown key / missing attribute).

- [ ] **Step 2: Implement.** In `config.py`:
  - Add `"formats"` to `_KNOWN_KEYS`.
  - Add `Formats = Literal["html", "json"]` next to `MissingDigest`.
  - `Config` field (after `missing_digest`): `formats: tuple[Formats, ...] = ("html", "json")`.
  - In `load()`, before the `Config(...)` construction:

```python
    raw_formats = raw.get("formats", ["html", "json"])
    if not isinstance(raw_formats, list) or not raw_formats:
        raise ConfigError(f"{path}: 'formats' must be a non-empty list")
    for fmt in raw_formats:
        if fmt not in ("html", "json"):
            raise ConfigError(
                f"{path}: 'formats' entries must be html or json, got {fmt!r}"
            )
    if len(set(raw_formats)) != len(raw_formats):
        raise ConfigError(f"{path}: 'formats' contains duplicates")
    formats = cast(tuple[Formats, ...], tuple(raw_formats))
```

  - Pass `formats=formats` to `Config(...)`.

- [ ] **Step 3: Verify.** `just test tests/test_config.py` → all pass; `just fix`; `just check-types` → clean; `just test` → whole suite green.

*(Driver checkpoint: commit as "Add formats config key")*

---

### Task 2: FileEntry size/upload_time + `version_from_filename`

**Goal:** `collect_projects` captures each asset's `size` and `created_at`; a helper parses versions from filenames; `packaging` becomes a runtime dep.

**Files:**
- Modify: `src/github_releases_pypi/index.py`
- Modify: `pyproject.toml` (`"packaging>=23"` in `[project] dependencies`), `uv.lock` via `uv sync --all-extras`
- Modify: `tests/test_index.py`

**Acceptance Criteria:**
- [ ] `FileEntry` has `size: int` (absent asset key → 0) and `upload_time: str | None` (absent → None)
- [ ] `version_from_filename`: wheel → second dash segment; `.tar.gz` → tail after the stem's last dash; other → None
- [ ] Existing tests pass unchanged

**Verify:** `just test tests/test_index.py` → all pass

**Steps:**

- [ ] **Step 1: Failing tests.** Append to `tests/test_index.py`:

```python
def test_version_from_filename():
    assert index.version_from_filename("demo_lib-1.0.0-py3-none-any.whl") == "1.0.0"
    assert index.version_from_filename("demo_lib-1.0.0.tar.gz") == "1.0.0"
    assert index.version_from_filename("demo-lib-2.0rc1.tar.gz") == "2.0rc1"
    assert index.version_from_filename("release-notes.txt") is None
    assert index.version_from_filename("noversion.whl") is None


def test_collect_projects_captures_size_and_upload_time():
    release = {
        "tag_name": "v3.0.0",
        "assets": [
            {
                "name": "sized-3.0.0-py3-none-any.whl",
                "browser_download_url": "https://github.com/o/r/releases/download/v3.0.0/sized-3.0.0-py3-none-any.whl",
                "digest": "sha256:beef",
                "size": 4321,
                "created_at": "2026-08-05T03:07:33Z",
            },
        ],
    }
    entry = index.collect_projects([release], hash_url=never_hash)["sized"][0]
    assert entry["size"] == 4321
    assert entry["upload_time"] == "2026-08-05T03:07:33Z"


def test_collect_projects_defaults_size_and_upload_time():
    entry = index.collect_projects(FIXTURE_RELEASES, hash_url=fake_hash)[
        "github-releases-pypi-demo-lib"
    ][0]
    assert entry["size"] == 0
    assert entry["upload_time"] is None
```

Run: `just test tests/test_index.py` → Expected: FAIL (no helper; KeyError on new fields).

- [ ] **Step 2: Dependency.** Add `"packaging>=23"` to `[project] dependencies` in pyproject.toml; run `uv sync --all-extras`.

- [ ] **Step 3: Implement.** In `index.py`:
  - `FileEntry` gains:

```python
    size: int
    upload_time: str | None
```

    (docstring: sizes come from the GitHub asset API, 0 when unknown;
    `upload_time` is the asset's RFC 3339 ``created_at``, None when unknown.)
  - New helper below `project_name_from_filename`:

```python
def version_from_filename(filename: str) -> str | None:
    """Return the version encoded in a wheel or sdist filename, else None."""
    if filename.endswith(".whl"):
        parts = filename[: -len(".whl")].split("-")
        return parts[1] if len(parts) > 1 else None
    if filename.endswith(".tar.gz"):
        stem = filename[: -len(".tar.gz")]
        if "-" in stem:
            return stem.rsplit("-", 1)[1]
    return None
```

  - In `collect_projects`, the appended entry gains:

```python
                    "size": int(asset.get("size") or 0),
                    "upload_time": asset.get("created_at"),
```

- [ ] **Step 4: Verify.** `just test tests/test_index.py` → all pass; `just test` → whole suite green; `just fix`; `just check-types` → clean.

*(Driver checkpoint: commit as "Capture asset size/upload time; parse versions from filenames")*

---

### Task 3: JSON emission + `write_site` formats

**Goal:** `write_site` writes the PEP 691/700 JSON tree and/or the HTML tree per `formats`; landing only with `html`.

**Files:**
- Modify: `src/github_releases_pypi/index.py`
- Modify: `tests/test_index.py`

**Acceptance Criteria:**
- [ ] `simple/<project>/index.json`: api-version 1.1, normalized name, sorted `versions`, files with filename/url/hashes/size (+ `upload-time` only when known; `hashes: {}` when sha256 is None)
- [ ] `simple/index.json`: api-version 1.1 + `projects` name list
- [ ] `formats=("html",)` → no `.json` files, HTML identical to today; `formats=("json",)` → no `.html` files anywhere (no landing); default → both
- [ ] Existing `test_write_site` passes unchanged

**Verify:** `just test tests/test_index.py` → all pass

**Steps:**

- [ ] **Step 1: Failing tests.** Append to `tests/test_index.py` (module import: add `import json` at the top of the test file):

```python
def test_write_site_json_project_page(tmp_path):
    projects = index.collect_projects(FIXTURE_RELEASES, hash_url=fake_hash)
    index.write_site(projects, tmp_path, title="T", index_url=None)
    data = json.loads(
        (tmp_path / "simple" / "github-releases-pypi-demo-lib" / "index.json").read_text()
    )
    assert data["meta"] == {"api-version": "1.1"}
    assert data["name"] == "github-releases-pypi-demo-lib"
    assert data["versions"] == ["1.0.0"]
    files = {f["filename"]: f for f in data["files"]}
    whl = files["github_releases_pypi_demo_lib-1.0.0-py3-none-any.whl"]
    assert whl["hashes"] == {"sha256": "cafef00d"}
    assert whl["size"] == 0
    assert "upload-time" not in whl


def test_write_site_json_root(tmp_path):
    projects = index.collect_projects(FIXTURE_RELEASES, hash_url=fake_hash)
    index.write_site(projects, tmp_path, title="T", index_url=None)
    data = json.loads((tmp_path / "simple" / "index.json").read_text())
    assert data["meta"] == {"api-version": "1.1"}
    assert {"name": "github-releases-pypi-demo-lib"} in data["projects"]
    assert {"name": "github-releases-pypi-demo-app"} in data["projects"]


def test_write_site_json_empty_hashes_and_upload_time(tmp_path):
    projects = index.collect_projects(
        DIGEST_RELEASE, hash_url=never_hash, missing_digest="no-fragment"
    )
    index.write_site(projects, tmp_path, title="T", index_url=None)
    data = json.loads((tmp_path / "simple" / "legacy" / "index.json").read_text())
    assert data["files"][0]["hashes"] == {}


def test_write_site_formats_html_only(tmp_path):
    projects = index.collect_projects(FIXTURE_RELEASES, hash_url=fake_hash)
    index.write_site(projects, tmp_path, title="T", index_url=None, formats=("html",))
    assert not list(tmp_path.rglob("*.json"))
    assert (tmp_path / "index.html").exists()
    assert (tmp_path / "simple" / "index.html").exists()


def test_write_site_formats_json_only(tmp_path):
    projects = index.collect_projects(FIXTURE_RELEASES, hash_url=fake_hash)
    index.write_site(projects, tmp_path, title="T", index_url=None, formats=("json",))
    assert not list(tmp_path.rglob("*.html"))
    assert (tmp_path / "simple" / "index.json").exists()
    assert (
        tmp_path / "simple" / "github-releases-pypi-demo-lib" / "index.json"
    ).exists()
```

Run: `just test tests/test_index.py` → Expected: FAIL (no formats param, no .json output).

- [ ] **Step 2: Implement in `index.py`.**
  - Imports: `import json`; `from packaging.version import InvalidVersion, Version`.
  - Helpers (above `write_site`):

```python
def _sorted_versions(files: list[FileEntry]) -> list[str]:
    raw = {v for f in files if (v := version_from_filename(f["filename"]))}
    parseable: list[tuple[Version, str]] = []
    unparseable: list[str] = []
    for version in raw:
        try:
            parseable.append((Version(version), version))
        except InvalidVersion:
            unparseable.append(version)
    return [v for _, v in sorted(parseable)] + sorted(unparseable)


def _json_project_page(project: str, files: list[FileEntry]) -> str:
    entries = []
    for file in files:
        entry: dict[str, Any] = {
            "filename": file["filename"],
            "url": file["url"],
            "hashes": {"sha256": file["sha256"]} if file["sha256"] else {},
            "size": file["size"],
        }
        if file["upload_time"]:
            entry["upload-time"] = file["upload_time"]
        entries.append(entry)
    return (
        json.dumps(
            {
                "meta": {"api-version": "1.1"},
                "name": project,
                "versions": _sorted_versions(files),
                "files": entries,
            },
            sort_keys=True,
        )
        + "\n"
    )


def _json_root(projects: Projects) -> str:
    return (
        json.dumps(
            {
                "meta": {"api-version": "1.1"},
                "projects": [{"name": name} for name in projects],
            },
            sort_keys=True,
        )
        + "\n"
    )
```

  - `write_site` signature gains `formats: tuple[str, ...] = ("html", "json")`; body becomes:

```python
    env = build_env(templates_dir) if "html" in formats else None
    simple = out_dir / "simple"
    simple.mkdir(parents=True, exist_ok=True)
    project_page = env.get_template("project.html") if env else None
    for project, files in projects.items():
        project_dir = simple / project
        project_dir.mkdir(parents=True, exist_ok=True)
        if project_page:
            (project_dir / "index.html").write_text(
                project_page.render(project=project, files=files), encoding="utf-8"
            )
        if "json" in formats:
            (project_dir / "index.json").write_text(
                _json_project_page(project, files), encoding="utf-8"
            )
    if "json" in formats:
        (simple / "index.json").write_text(_json_root(projects), encoding="utf-8")
    if env:
        (simple / "index.html").write_text(
            env.get_template("simple_root.html").render(projects=projects),
            encoding="utf-8",
        )
        (out_dir / "index.html").write_text(
            env.get_template("landing.html").render(
                title=title, index_url=index_url, projects=projects
            ),
            encoding="utf-8",
        )
```

  - Docstring: "Write the landing page and PEP 503/691 simple index under
    ``out_dir``. ``formats`` selects the HTML tree, the JSON tree
    (api-version 1.1), or both; the landing page is written only when
    ``html`` is included."

- [ ] **Step 3: Verify.** `just test tests/test_index.py` → all pass; `just test` → whole suite green (existing tests untouched); `just fix`; `just check-types` → clean.

*(Driver checkpoint: commit as "Emit PEP 691/700 JSON Simple API")*

---

### Task 4: CLI wiring + docs + full gate

**Goal:** `cfg.formats` reaches `write_site`; README/changelog updated; full gate green.

**Files:**
- Modify: `src/github_releases_pypi/cli.py` (write_site call)
- Modify: `tests/test_cli.py` (one test)
- Modify: `README.md`, `doc/source/changelog.rst`

**Acceptance Criteria:**
- [ ] Config `formats: [json]` via CLI → out dir has JSON tree, zero `.html` files
- [ ] README documents `formats` + the per-target negotiation story + JSON-not-templated note
- [ ] `just check-all` → exit 0

**Verify:** `just test` → all pass; `just check-all` → exit 0

**Steps:**

- [ ] **Step 1: Failing test.** Append to `tests/test_cli.py`:

```python
def test_cli_formats_json_only(tmp_path, monkeypatch):
    monkeypatch.setattr(index, "fetch_releases", lambda repo, token: FIXTURE_RELEASES)
    monkeypatch.setattr(index, "hash_url", lambda url: "cafef00d")
    cfg = config_file(tmp_path, "repositories: [a/b]\nformats: [json]\n")
    out = tmp_path / "site"
    result = runner.invoke(
        app, ["--config", str(cfg), "--out", str(out), "--token", "x"]
    )
    assert result.exit_code == 0, all_output(result)
    assert (out / "simple" / "index.json").exists()
    assert not list(out.rglob("*.html"))
```

Run: `just test tests/test_cli.py` → Expected: FAIL (html files present — formats not wired).

- [ ] **Step 2: Wire.** In `cli.py`, the `write_site` call gains `formats=cfg.formats`.

- [ ] **Step 3: README.** Add `formats: [html, json]                  # optional — default: both` to the YAML config example, and after the `missing_digest` table add:

```markdown
## JSON Simple API

With `json` in `formats` (the default), the builder also writes a
[PEP 691](https://peps.python.org/pep-0691/) JSON index — `simple/index.json`
and `simple/<project>/index.json`, api-version 1.1 with
[PEP 700](https://peps.python.org/pep-0700/) `versions`, `size`, and
`upload-time` fields (uv's `--exclude-newer` uses `upload-time`).

On a full webserver you can serve the JSON at the canonical URLs via
`Accept`-header content negotiation (`application/vnd.pypi.simple.v1+json`);
on static hosts the files sit alongside the HTML. The JSON shape is
spec-defined and is NOT affected by template overrides.

`formats: [json]` emits a JSON-only, headless index (no landing page);
`formats: [html]` reproduces today's HTML-only output.
```

- [ ] **Step 4: Changelog.** Bullet under 2026.8.5 (wrap for doc8's 100-col limit):

```rst
* Emit a PEP 691/700 JSON Simple API alongside the HTML index, controlled by
  the ``formats`` config key.
```

- [ ] **Step 5: Full gate.** `just fix`; `just test` → all pass; `just check-all` → exit 0 (real run).

*(Driver checkpoint: commit as "Wire and document the formats config key")*

---

## After the plan

Driver: commit the checkpoints; the feature rides into the next `just release`.
Next phases per `direction.md`: asset mirroring, then PEP 658 metadata.
