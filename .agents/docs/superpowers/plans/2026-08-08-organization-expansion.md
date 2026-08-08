# Organization Expansion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers-extended-cc:subagent-driven-development (recommended) or superpowers-extended-cc:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **PROJECT RULE (AGENTS.md):** agents never commit or push — the human driver
> does. Implementers stop at "verified in working tree".

**Goal:** `repositories: [yourorg/*]` indexes every repository the token can read in an owner, and every GitHub list endpoint is fully paginated.

**Architecture:** One `_paginate` helper in `index.py` serves both `fetch_releases` (removing its one-page limit) and a new `fetch_repositories`. `config.py` learns to recognise and validate `OWNER/PATTERN` entries plus an `exclude_repositories` key. `cli.py` expands patterns after resolving the config and before fetching releases, so `config.load` stays network-free.

**Spec:** `.agents/docs/superpowers/specs/2026-08-08-organization-expansion-design.md`

**Context for the implementer:**
- Current suite: 244 tests green, `just check-all` exit 0. The tree carries a
  large amount of uncommitted work — touch only your task's files.
- **Do NOT run `just test-all <path>`.** It splices arguments into `uv run`'s
  flag position and destroys the project venv. Use `just test` or
  `uv run pytest <path>`.
- `config.py` must never import `index.py` (`index` imports `config` — cycle).
- **Injectable openers are the house pattern for HTTP testability** — see
  `index.mirror_files(..., opener=...)` and its tests in `tests/test_index.py`.
  Follow it; do not monkeypatch `urllib.request.urlopen` globally.
- **Use `fnmatch.fnmatchcase`, never `fnmatch.fnmatch`.** The latter applies
  `os.path.normcase`, which lowercases on Windows only — this project runs
  Windows CI, and a platform-dependent match would be a real bug. Case
  insensitivity is achieved by `.casefold()`-ing both sides explicitly.
- doc8 enforces a 100-character line limit on RST.
- Read `src/ghr_pypi/index.py`, `config.py` and `cli.py` before writing; the code
  wins over this plan if they disagree.

---

### Task 1: `_paginate` and paginated `fetch_releases`

**Goal:** One paginated-GET helper, and `fetch_releases` no longer stops at 100 releases.

**Files:**
- Modify: `src/ghr_pypi/index.py` (`fetch_releases` at ~line 106)
- Modify: `tests/test_index.py`

**Acceptance Criteria:**
- [ ] `_paginate(url, token, *, opener=...)` returns every item across pages
- [ ] It stops when a page returns fewer than 100 items, including the boundary where a full page is followed by an empty one
- [ ] It requests `?per_page=100&page=N` with N starting at 1
- [ ] More than 100 pages raises `PaginationError` rather than looping or truncating
- [ ] `fetch_releases` returns releases from beyond the first page
- [ ] Existing `index` behavior is otherwise unchanged; no existing test needs editing

**Verify:** `uv run pytest tests/test_index.py -q` → all pass; `just check-types` clean

**Steps:**

- [ ] **Step 1: Write the failing tests.** Add to `tests/test_index.py`. It already imports `io`, `json` and `pytest`; add `urllib.error` if absent.

```python
def paged_opener(*pages):
    """Fake opener serving JSON pages in order, recording the URLs requested."""
    urls = []

    def opener(request, timeout=None):
        urls.append(request.full_url)
        return io.BytesIO(json.dumps(pages[len(urls) - 1]).encode())

    opener.urls = urls
    return opener


def test_paginate_single_short_page():
    opener = paged_opener([{"n": 1}, {"n": 2}])
    assert index._paginate("https://api.example/x", "tok", opener=opener) == [
        {"n": 1},
        {"n": 2},
    ]
    assert opener.urls == ["https://api.example/x?per_page=100&page=1"]


def test_paginate_full_page_then_short():
    first = [{"n": i} for i in range(100)]
    opener = paged_opener(first, [{"n": 100}])
    assert index._paginate("https://api.example/x", "tok", opener=opener) == first + [
        {"n": 100}
    ]
    assert opener.urls[-1].endswith("page=2")


def test_paginate_full_page_then_empty():
    first = [{"n": i} for i in range(100)]
    opener = paged_opener(first, [])
    assert index._paginate("https://api.example/x", "tok", opener=opener) == first
    assert len(opener.urls) == 2


def test_paginate_refuses_to_loop_forever():
    full = [{"n": i} for i in range(100)]
    opener = paged_opener(*([full] * 200))
    with pytest.raises(index.PaginationError, match="pages"):
        index._paginate("https://api.example/x", "tok", opener=opener)


def test_fetch_releases_reads_every_page():
    first = [{"tag_name": f"v{i}", "assets": []} for i in range(100)]
    opener = paged_opener(first, [{"tag_name": "v100", "assets": []}])
    releases = index.fetch_releases("a/b", "tok", opener=opener)
    assert len(releases) == 101
    assert releases[-1]["tag_name"] == "v100"
    assert opener.urls[0].startswith(f"{index.API_ROOT}/repos/a/b/releases?")
```

- [ ] **Step 2: Run and confirm they fail.**

Run: `uv run pytest tests/test_index.py -q`
Expected: FAIL with `AttributeError: module 'ghr_pypi.index' has no attribute '_paginate'`.

- [ ] **Step 3: Implement.** In `src/ghr_pypi/index.py`, add near the other module-level exceptions (`MirrorError`):

```python
class PaginationError(Exception):
    """Raised when a paginated GitHub endpoint never returns a short page."""
```

Add above `fetch_releases`, and replace `fetch_releases`'s body:

```python
_PER_PAGE = 100
_MAX_PAGES = 100


def _paginate(
    url: str,
    token: str,
    *,
    opener: Callable[..., Any] = urllib.request.urlopen,
) -> list[dict[str, Any]]:
    """Return every item of a paginated GitHub list endpoint.

    Requests pages of ``_PER_PAGE`` until one comes back short. The
    ``_MAX_PAGES`` cap exists because a server that always returns a full page
    would otherwise spin forever; hitting it raises rather than silently
    truncating, since a short index is worse than a failed build.
    """
    items: list[dict[str, Any]] = []
    for page in range(1, _MAX_PAGES + 1):
        request = urllib.request.Request(
            f"{url}?per_page={_PER_PAGE}&page={page}",
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {token}",
            },
        )
        with opener(  # nosec B310 — https URL built from constant API_ROOT
            request, timeout=30
        ) as response:
            batch = json.load(response)
        items.extend(batch)
        if len(batch) < _PER_PAGE:
            return items
    raise PaginationError(f"{url}: more than {_MAX_PAGES} pages")


def fetch_releases(
    repo: str,
    token: str,
    *,
    opener: Callable[..., Any] = urllib.request.urlopen,
) -> list[dict[str, Any]]:
    """Return the JSON list of every release for the ``owner/name`` repository."""
    return _paginate(f"{API_ROOT}/repos/{repo}/releases", token, opener=opener)
```

`Callable` is already imported from `collections.abc` in this module.

- [ ] **Step 4: Verify.**

Run: `uv run pytest tests/test_index.py -q` → all pass
Run: `just test` → report the total count
Run: `just fix`, then `just check-types` → clean

Confirm no existing test needed editing; if one did, say which and why.

- [ ] **Step 5: Mutation check.** Change `if len(batch) < _PER_PAGE` to
  `if True` → confirm `test_paginate_full_page_then_short` and
  `test_fetch_releases_reads_every_page` FAIL. Revert and report.

*(Driver checkpoint: commit as "Paginate GitHub list endpoints")*

---

### Task 2: Config patterns and `exclude_repositories`

**Goal:** `OWNER/PATTERN` entries validate, owner-half patterns are rejected, and `exclude_repositories` loads.

**Files:**
- Modify: `src/ghr_pypi/config.py`
- Modify: `tests/test_config.py`

**Acceptance Criteria:**
- [ ] `is_pattern(name)` is True for `*`, `?` and `[`, False otherwise
- [ ] `check_repository(value, label)` accepts `a/b` and `a/b-*`, rejects `*/b`
- [ ] `repositories` accepts patterns; `*/thing` raises with the owner message
- [ ] `exclude_repositories` loads, defaults to `()`, and validates each entry
- [ ] Non-list / non-string-element `exclude_repositories` raise `ConfigError`
- [ ] The existing duplicate-literal check is unchanged (overlapping patterns are different strings, so it already does the right thing)

**Verify:** `uv run pytest tests/test_config.py -q` → all pass; `just check-types` clean

**Steps:**

- [ ] **Step 1: Write the failing tests** in `tests/test_config.py`, reusing the file's existing config-writing helper:

```python
@pytest.mark.parametrize("name,expected", [
    ("plain", False), ("has-dash", False),
    ("*", True), ("lib-*", True), ("lib-?", True), ("lib-[ab]", True),
])
def test_is_pattern(name, expected):
    assert is_pattern(name) is expected


def test_repositories_accept_patterns(tmp_path):
    cfg = write(tmp_path, "repositories: [yourorg/*, yourorg/lib-*, other/one]\n")
    assert load(cfg).repositories == ("yourorg/*", "yourorg/lib-*", "other/one")


def test_repositories_reject_a_pattern_in_the_owner(tmp_path):
    cfg = write(tmp_path, "repositories: ['*/thing']\n")
    with pytest.raises(ConfigError, match="may not use a pattern in the owner"):
        load(cfg)


def test_exclude_repositories_defaults_to_empty(tmp_path):
    cfg = write(tmp_path, "repositories: [a/b]\n")
    assert load(cfg).exclude_repositories == ()


def test_exclude_repositories_loads(tmp_path):
    cfg = write(tmp_path, "repositories: [a/*]\nexclude_repositories: [a/secret-*]\n")
    assert load(cfg).exclude_repositories == ("a/secret-*",)


@pytest.mark.parametrize("body,message", [
    ("repositories: [a/b]\nexclude_repositories: nope\n",
     "'exclude_repositories' must be a list"),
    ("repositories: [a/b]\nexclude_repositories: [5]\n",
     "is not OWNER/NAME"),
    ("repositories: [a/b]\nexclude_repositories: ['*/x']\n",
     "may not use a pattern in the owner"),
])
def test_exclude_repositories_errors(tmp_path, body, message):
    with pytest.raises(ConfigError, match=message):
        load(write(tmp_path, body))
```

Import `is_pattern` alongside the module's existing imports. If the file's
config-writing helper is not named `write`, use whatever it is called.

- [ ] **Step 2: Run and confirm they fail.**

Run: `uv run pytest tests/test_config.py -q`
Expected: `ImportError` for `is_pattern`, plus failures on the new keys.

- [ ] **Step 3: Implement in `src/ghr_pypi/config.py`.** Add `"exclude_repositories"` to `_KNOWN_KEYS`, and beside `check_slug`:

```python
_PATTERN_CHARS = "*?["


def is_pattern(name: str) -> bool:
    """Return True when a repository name half is an ``fnmatch`` pattern.

    The character set is exactly what ``fnmatch`` treats as special — testing
    only for ``*`` and ``?`` would silently read ``yourorg/lib-[ab]`` as a
    literal repository name.
    """
    return any(char in name for char in _PATTERN_CHARS)


def check_repository(value: Any, label: str) -> None:
    """Raise ``ConfigError`` unless ``value`` is ``OWNER/NAME`` or ``OWNER/PATTERN``.

    The owner half may never be a pattern: there is no GitHub endpoint for
    "every organization I can see".
    """
    check_slug(value, label)
    if is_pattern(value.split("/")[0]):
        raise ConfigError(f"{label} {value!r} may not use a pattern in the owner")
```

In `load`, change the `repositories` element check from `check_slug` to
`check_repository` (keeping the same `f"{path}: repository"` label), and add
after it:

```python
    exclude_repositories = raw.get("exclude_repositories") or []
    if not isinstance(exclude_repositories, list):
        raise ConfigError(f"{path}: 'exclude_repositories' must be a list of patterns")
    for pattern in exclude_repositories:
        check_repository(pattern, f"{path}: exclude_repositories entry")
```

Add `exclude_repositories: tuple[str, ...] = ()` to `Config`, and
`exclude_repositories=tuple(exclude_repositories)` to its construction.

- [ ] **Step 4: Verify.**

Run: `uv run pytest tests/test_config.py -q` → all pass
Run: `just test` → report the count
Run: `just fix`, then `just check-types` → clean

*(Driver checkpoint: commit as "Accept repository patterns in config")*

---

### Task 3: `fetch_repositories` and CLI expansion

**Goal:** Patterns expand against the GitHub API, in place, with exclusions and reporting.

**Files:**
- Modify: `src/ghr_pypi/index.py`, `src/ghr_pypi/cli.py`
- Modify: `tests/test_index.py`, `tests/test_cli.py`

**Acceptance Criteria:**
- [ ] `fetch_repositories(owner, token, *, opener=...)` returns `owner/name` strings from `/orgs/`, falling back to `/users/` on 404, re-raising any other HTTP error
- [ ] A pattern expands to sorted matches spliced **where the pattern stood**, so an explicit entry written before a pattern stays before all of its matches
- [ ] One listing per owner even with two patterns for that owner
- [ ] `exclude_repositories` removes from expansions and never removes an explicit entry
- [ ] Matching is case-insensitive and uses `fnmatchcase` on casefolded strings
- [ ] A pattern matching nothing exits 1 with `no repositories matched '<pattern>'`
- [ ] Each expansion reports `expanded '<pattern>' to N repositories` on stderr
- [ ] Overlapping patterns de-duplicate, first occurrence winning
- [ ] A pattern in a positional `REPO` argument is accepted; in `$GITHUB_REPOSITORY` it is rejected

**Verify:** `just test` → all pass (report the count)

**Steps:**

- [ ] **Step 1: Write the failing `fetch_repositories` tests** in `tests/test_index.py`, reusing `paged_opener` from Task 1:

```python
def test_fetch_repositories_lists_an_org():
    opener = paged_opener([{"full_name": "org/one"}, {"full_name": "org/two"}])
    assert index.fetch_repositories("org", "tok", opener=opener) == [
        "org/one",
        "org/two",
    ]
    assert "/orgs/org/repos" in opener.urls[0]


def test_fetch_repositories_falls_back_to_a_user():
    calls = []

    def opener(request, timeout=None):
        calls.append(request.full_url)
        if "/orgs/" in request.full_url:
            raise urllib.error.HTTPError(request.full_url, 404, "nope", {}, None)
        return io.BytesIO(json.dumps([{"full_name": "someone/pkg"}]).encode())

    assert index.fetch_repositories("someone", "tok", opener=opener) == ["someone/pkg"]
    assert "/users/someone/repos" in calls[-1]


def test_fetch_repositories_reraises_other_http_errors():
    def opener(request, timeout=None):
        raise urllib.error.HTTPError(request.full_url, 403, "forbidden", {}, None)

    with pytest.raises(urllib.error.HTTPError):
        index.fetch_repositories("org", "tok", opener=opener)
```

- [ ] **Step 2: Implement `fetch_repositories`** in `src/ghr_pypi/index.py`, below `fetch_releases`:

```python
def fetch_repositories(
    owner: str,
    token: str,
    *,
    opener: Callable[..., Any] = urllib.request.urlopen,
) -> list[str]:
    """Return every ``owner/name`` repository the token can read.

    Tries the organization endpoint and falls back to the user endpoint on 404.
    The user endpoint lists only *public* repositories — GitHub has no endpoint
    for another account's private ones — so private repositories on a personal
    account have to be listed explicitly.
    """
    try:
        payload = _paginate(f"{API_ROOT}/orgs/{owner}/repos", token, opener=opener)
    except urllib.error.HTTPError as error:
        if error.code != 404:
            raise
        payload = _paginate(f"{API_ROOT}/users/{owner}/repos", token, opener=opener)
    return [repo["full_name"] for repo in payload]
```

- [ ] **Step 3: Write the failing CLI expansion tests** in `tests/test_cli.py`. Add `from ghr_pypi.cli import _expand_patterns` to the existing imports.

```python
def fake_listing(monkeypatch, **owners):
    """Stub index.fetch_repositories, recording how many times each owner is listed."""
    calls = []

    def lister(owner, token, **kwargs):
        calls.append(owner)
        return list(owners[owner])

    monkeypatch.setattr(index, "fetch_repositories", lister)
    return calls


def test_expand_splices_matches_in_place(monkeypatch):
    fake_listing(monkeypatch, org=["org/beta", "org/alpha"])
    assert _expand_patterns(("first/explicit", "org/*"), (), "tok") == (
        "first/explicit",
        "org/alpha",
        "org/beta",
    )


def test_expand_lists_each_owner_once(monkeypatch):
    calls = fake_listing(monkeypatch, org=["org/lib-a", "org/app-b"])
    assert _expand_patterns(("org/lib-*", "org/app-*"), (), "tok") == (
        "org/lib-a",
        "org/app-b",
    )
    assert calls == ["org"]


def test_expand_is_case_insensitive(monkeypatch):
    fake_listing(monkeypatch, org=["org/LibOne"])
    assert _expand_patterns(("org/lib*",), (), "tok") == ("org/LibOne",)


def test_expand_applies_exclusions(monkeypatch):
    fake_listing(monkeypatch, org=["org/keep", "org/secret-x"])
    assert _expand_patterns(("org/*",), ("org/secret-*",), "tok") == ("org/keep",)


def test_expand_never_excludes_an_explicit_entry(monkeypatch):
    fake_listing(monkeypatch, org=["org/other"])
    assert _expand_patterns(("org/secret-x", "org/*"), ("org/secret-*",), "tok") == (
        "org/secret-x",
        "org/other",
    )


def test_expand_deduplicates_overlapping_patterns(monkeypatch):
    fake_listing(monkeypatch, org=["org/lib-a"])
    assert _expand_patterns(("org/*", "org/lib-*"), (), "tok") == ("org/lib-a",)


def test_expand_rejects_a_pattern_matching_nothing(monkeypatch):
    fake_listing(monkeypatch, org=["org/one"])
    with pytest.raises(ConfigError, match="no repositories matched 'org/zzz-\\*'"):
        _expand_patterns(("org/zzz-*",), (), "tok")


def test_expand_reports_each_expansion(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        index, "fetch_repositories", lambda owner, token, **kw: ["org/one"]
    )
    monkeypatch.setattr(index, "fetch_releases", fetch_stub(FIXTURE_RELEASES))
    monkeypatch.setattr(index, "hash_url", lambda url: "cafef00d")
    result = runner.invoke(app, ["index", "org/*", "--token", "x"])
    assert result.exit_code == 0, all_output(result)
    assert "expanded 'org/*' to 1 repositories" in all_output(result)


def test_resolve_rejects_a_pattern_in_the_environment():
    with pytest.raises(ConfigError, match="may not be a pattern"):
        resolve(env_repo="org/*")


def test_resolve_accepts_a_pattern_argument():
    assert resolve(["org/*"]).repositories == ("org/*",)
```

- [ ] **Step 4: Implement the expansion** in `src/ghr_pypi/cli.py`. Add `from fnmatch import fnmatchcase` and import `check_repository, is_pattern` from `ghr_pypi.config` alongside the existing names.

```python
def _expand_patterns(
    repositories: tuple[str, ...],
    exclude: tuple[str, ...],
    token: str,
) -> tuple[str, ...]:
    """Expand ``OWNER/PATTERN`` entries by listing each owner's repositories.

    Matches are sorted and spliced where their pattern stood, because duplicate
    filenames across repositories resolve first-occurrence-wins — order is
    behavior, not presentation. Exclusions apply to expansions only: a
    repository named explicitly is always indexed.
    """
    listings: dict[str, list[str]] = {}
    resolved: list[str] = []
    for entry in repositories:
        owner, name = entry.split("/")
        if not is_pattern(name):
            resolved.append(entry)
            continue
        if owner not in listings:
            listings[owner] = index.fetch_repositories(owner, token)
        matched = sorted(
            found
            for found in listings[owner]
            if fnmatchcase(found.split("/", 1)[1].casefold(), name.casefold())
            and not any(
                fnmatchcase(found.casefold(), pattern.casefold())
                for pattern in exclude
            )
        )
        if not matched:
            raise ConfigError(f"no repositories matched {entry!r}")
        typer.echo(f"expanded {entry!r} to {len(matched)} repositories", err=True)
        resolved.extend(matched)
    seen: set[str] = set()
    unique: list[str] = []
    for entry in resolved:
        if entry.casefold() not in seen:
            seen.add(entry.casefold())
            unique.append(entry)
    return tuple(unique)
```

In `_resolve_config`, change the positional-argument check from `check_slug` to
`check_repository`, and reject a pattern from the environment right after the
existing `check_slug(env_repo, ...)` call:

```python
        if is_pattern(env_repo):
            raise ConfigError(f"GITHUB_REPOSITORY {env_repo!r} may not be a pattern")
```

(The spec said "same message" here; a distinct one is correct, because the
environment may not carry a pattern in *either* half.)

In the `build_index` body, after the `_resolve_config` call succeeds and before
the `releases = []` loop:

```python
    try:
        cfg = replace(
            cfg,
            repositories=_expand_patterns(
                cfg.repositories, cfg.exclude_repositories, token
            ),
        )
    except ConfigError as error:
        typer.echo(f"error: {error}", err=True)
        raise typer.Exit(1) from error
    except (urllib.error.URLError, index.PaginationError) as error:
        typer.echo(f"error: listing repositories failed: {error}", err=True)
        raise typer.Exit(1) from error
```

Add `index.PaginationError` to the `except` clause already wrapping the
release-fetch loop, so a runaway releases endpoint is reported the same way.

- [ ] **Step 5: Verify.**

Run: `uv run pytest tests/test_cli.py tests/test_index.py -q` → all pass
Run: `just test` → report the count
Run: `just fix`, then `just check-types` → clean

- [ ] **Step 6: Mutation check.** One at a time, reverting each:

1. Replace `fnmatchcase` with `fnmatch.fnmatch` → confirm
   `test_expand_is_case_insensitive` still passes on macOS/Linux, and **say so**
   — this one is a platform trap the suite cannot catch here. Note it in your
   report rather than claiming coverage.
2. Change `resolved.extend(matched)` to `resolved[:0] = matched` (prepend) →
   confirm `test_expand_splices_matches_in_place` FAILS.
3. Delete the `if not matched: raise` branch → confirm
   `test_expand_rejects_a_pattern_matching_nothing` FAILS.
4. Move the exclusion filter so it also applies to literal entries → confirm
   `test_expand_never_excludes_an_explicit_entry` FAILS.

Report all four results.

*(Driver checkpoint: commit as "Expand repository patterns against the GitHub API")*

---

### Task 4: Docs and full gate

**Goal:** Patterns, exclusions and full pagination are documented, and the four places claiming a 100-release limit are corrected.

**Files:**
- Modify: `doc/source/reference/configuration.rst`, `doc/source/reference/cli.rst`, `doc/source/index.rst`, `doc/source/how-to/aggregate-repositories.rst`, `doc/source/how-to/build-failed.rst`, `doc/source/how-to/index.rst`, `doc/source/changelog.rst`, `README.md`, `direction.md`
- Create: `doc/source/how-to/index-an-organization.rst`

**Acceptance Criteria:**
- [ ] No document still claims only one page of releases is read
- [ ] `configuration.rst` documents patterns under `repositories`, the new `exclude_repositories` key, and every new error message verbatim
- [ ] `cli.rst` documents that a pattern argument must be quoted
- [ ] The new how-to covers the user-account public-only limitation and the per-repository API cost
- [ ] The `index.rst` "more than 100 releases" bullet is deleted, not reworded
- [ ] The implemented `direction.md` bullet is removed
- [ ] `just check-all` → exit 0

**Verify:** `just check-all > /tmp/gate.log 2>&1; echo EXIT=$?` → `EXIT=0`

**Steps:**

- [ ] **Step 1: Remove the one-page limit claims.** These four say it today:
  - `doc/source/index.rst:121` — a bullet under "When not to use it". **Delete the whole bullet**; it is no longer a reason not to use the tool.
  - `doc/source/how-to/aggregate-repositories.rst:54` — "The build reads one page of releases per repository…". Rewrite around what is now true.
  - `doc/source/how-to/build-failed.rst:37` — a bullet under empty-index causes. Delete or replace with the real remaining cause (a repository with no release assets at all).
  - `README.md:329-330` — "returns at most 100 releases per page and the tool reads one page."

Re-read each surrounding passage; several were written to justify the limit and need more than a sentence swap.

- [ ] **Step 2: `doc/source/reference/configuration.rst`.** Under `repositories`, document that an entry's name half may be an `fnmatch` pattern (`*`, `?`, `[seq]`), that the owner half may not, that matching is case-insensitive, that matches are sorted and spliced in place (and why order matters), and that a pattern matching nothing is an error. Add an `exclude_repositories` key section in the page's existing per-key format, stating that it applies to expansions only and that a non-matching exclusion is deliberately not an error. Add both to the summary table and extend the complete annotated example. Add every new message to the Validation errors section, verbatim from `src/ghr_pypi/config.py`:
  - `{path}: repository {value!r} may not use a pattern in the owner`
  - `{path}: 'exclude_repositories' must be a list of patterns`
  - `{path}: exclude_repositories entry {value!r} is not OWNER/NAME`
  - `{path}: exclude_repositories entry {value!r} may not use a pattern in the owner`

Get the exact wording from the code, not from this plan.

- [ ] **Step 3: `doc/source/reference/cli.rst`.** In the `REPO...` option entry and the "One or more repositories" section, document patterns and the quoting requirement:

```rst
   ghr-pypi index 'yourorg/*' --out site
```

Say plainly that the quotes are required so the shell does not try to glob the
pattern. Add the two runtime errors — `no repositories matched '<pattern>'` and
`GITHUB_REPOSITORY '<value>' may not be a pattern` — to the exit-1 list.

- [ ] **Step 4: Create `doc/source/how-to/index-an-organization.rst`**, titled as a question the way its siblings are ("How do I index a whole organization?"). Cover: the config and command line forms; that every repository the token can read is included, forks and archived ones too, with `exclude_repositories` as the escape hatch; **the user-account limitation** — `/users/{owner}/repos` lists only public repositories, so private repositories on a personal account must be listed explicitly, and why a `/user/repos` code path was not added; and the cost, roughly one API call per repository plus one per 100 releases in any of them. Add it to the toctree in `doc/source/how-to/index.rst`, matching the existing ordering convention.

- [ ] **Step 5: `README.md`.** Add patterns to the config example in the aggregation section, keeping lines short — that region sits inside the `<!-- docs-index-start -->` markers and is included verbatim into `doc/source/index.rst`.

- [ ] **Step 6: `doc/source/changelog.rst`.** Add to the current unreleased section, matching the file's bullet style:

```rst
* ``repositories`` entries may use an ``fnmatch`` pattern in the name half —
  ``yourorg/*`` indexes every repository the token can read in that owner — with
  a new ``exclude_repositories`` key to subtract from expansions.
* Every GitHub list endpoint is now paginated: repositories with more than 100
  releases are read in full.
```

- [ ] **Step 7: `direction.md`.** Delete the bullet `* Simple config for "all accessible repositories in an organization"`. Leave the rest untouched. The file is gitignored, so verify by reading it back.

- [ ] **Step 8: Gate.**

```
just fix
just test
just check-all > /tmp/gate.log 2>&1; echo EXIT=$?
```

Expect `EXIT=0`. Also run a strict HTML build, which must be warning-free:

```
uv run --no-default-groups --group docs sphinx-build -b html -a -E -n ./doc/source /tmp/oe-docs
```

Fix any linkcheck failure by correcting the URL — never by disabling linkcheck.
The justfile invokes linkcheck with a leading `-`, so link failures do not fail
the gate: read `doc/build/output.txt` yourself and report what it says.

Then prove the stale claims are gone:

```bash
grep -rn "one page\|100 releases\|per page" --include='*.rst' --include='*.md' doc/source README.md
```

Judge every hit; report what you left and why.

*(Driver checkpoint: commit as "Document organization expansion and pagination")*

---

## After the plan

Driver: commit the checkpoints. Adding a repository to the organization now
adds it to the index on the next build, with no config edit.
