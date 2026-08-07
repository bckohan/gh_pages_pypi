# Yank and Exclude Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers-extended-cc:subagent-driven-development (recommended) or superpowers-extended-cc:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **PROJECT RULE (AGENTS.md):** agents never commit or push — the human driver
> does. Implementers stop at "verified in working tree".

**Goal:** Two config keys — `yanked` (PEP 592 marking, with optional reason) and `exclude` (drop entirely) — both keyed by project then version.

**Architecture:** `config.py` validates both keys and exposes them through a frozen `Filters` dataclass with version-equivalence matching. `collect_projects` takes one `filters` argument: excluded files are skipped before the duplicate-filename bookkeeping; yanked files get a `yanked: str | bool` on `FileEntry`. `project.html` emits `data-yanked`; `_json_project_page` emits `"yanked"`.

**Spec:** `.agents/docs/superpowers/specs/2026-08-07-yank-exclude-design.md`

**Context for the implementer:**
- Current suite: 135 tests green, `just check-all` exit 0. The tree carries a large amount of uncommitted work (rename, dynamic versioning, the full docs manual) — touch only your task's files.
- **`config.py` must not import `index.py`** — `index.py` imports `config.py` (`MissingDigest`, `Formats`), so importing back creates a cycle. Normalization is three lines (`re.sub(r"[-_.]+", "-", name).lower()`); duplicate it in `config.py` or move it somewhere shared. State which you chose.
- `collect_projects` is already at six parameters; `filters` is the seventh and last — do NOT add two separate ones.
- Read `src/ghr_pypi/config.py` and `index.py` before writing; the code wins over this plan if they disagree.
- doc8 max line length 100 for RST; `just check-docs` and `just check-all` must stay green.

---

### Task 1: Config `yanked` / `exclude` + `Filters`

**Goal:** Both keys validate and load; `Filters` answers "is this project+version yanked/excluded?"

**Files:**
- Modify: `src/ghr_pypi/config.py`, `tests/test_config.py`
- Create: `tests/test_filters.py`

**Acceptance Criteria:**
- [ ] Both keys load; omitted → empty; project keys normalized (`Demo_Lib` → `demo-lib`)
- [ ] Reasons accept `str` and `True`; `False` rejected with a "remove the entry to un-yank" message
- [ ] Unquoted YAML `1.0` (a float key) rejected with a message telling the user to quote it
- [ ] Non-mapping / non-list / wrong-element-type shapes all raise `ConfigError`
- [ ] `Filters` matching: `1.0` matches `1.0.0`; unparseable version matches nothing; unknown project is a no-op

**Verify:** `just test tests/test_config.py tests/test_filters.py` → all pass; `just check-types` clean

**Steps:**

- [ ] **Step 1: Failing tests.** Write `tests/test_filters.py` covering the matching rules, and add config tests to `tests/test_config.py` for both keys (happy paths incl. normalization, plus one error row per validation branch). Model the error rows on the file's existing `test_load_errors` parametrize style. Run and confirm they fail.

- [ ] **Step 2: Implement in `config.py`.**
  - Add `"yanked"` and `"exclude"` to `_KNOWN_KEYS`.
  - A module-level `_normalize(name)` (the three-line PEP 503 form — do not import `index`).
  - A frozen `Filters` dataclass holding the two normalized structures, with two methods, e.g. `yank_reason(project, version) -> str | bool` (returns `False` when not yanked) and `is_excluded(project, version) -> bool`. Version comparison: both sides through `packaging.version.Version` inside `try/except InvalidVersion`, falling back to exact string equality; a `None` version matches nothing.
  - Validation for both keys, raising `ConfigError` with the `{path}: ` prefix like every sibling. Cover: not a mapping; inner value not a mapping (`yanked`) / not a list (`exclude`); version key not a string (mention quoting); reason not `str`/`True`; `False` reason (dedicated message); exclude element not a string.
  - `Config` gains both fields (immutable — store as nested tuples/`MappingProxy`-friendly structures or plain dicts built once; the dataclass is `frozen` but dict values are still mutable, so prefer building the `Filters` at load time and storing THAT on `Config` if it is simpler — implementer's call, state it).

- [ ] **Step 3: Verify.** `just test tests/test_config.py tests/test_filters.py`; `just fix`; `just check-types`; `just test` (whole suite — report the count).

*(Driver checkpoint: commit as "Add yanked and exclude config keys")*

---

### Task 2: Apply filters in `collect_projects` + emission

**Goal:** Excluded files never enter the index; yanked files are marked in HTML and JSON.

**Files:**
- Modify: `src/ghr_pypi/index.py`, `src/ghr_pypi/templates/project.html`, `src/ghr_pypi/cli.py`, `tests/test_index.py`

**Acceptance Criteria:**
- [ ] `collect_projects(..., filters=...)` — excluded files skipped BEFORE the `seen` bookkeeping (prove it: a same-named file in a later release is still indexed)
- [ ] `FileEntry.yanked: str | bool` default `False`; yanked files otherwise processed normally
- [ ] HTML anchor gains `data-yanked="<reason>"` (empty string when the reason is `True`), absent when not yanked
- [ ] JSON gains `"yanked": true` / `"yanked": "<reason>"`, key absent when not yanked
- [ ] Yanked version still appears in PEP 700 `versions`; excluded version absent
- [ ] CLI passes the filters through; existing 135 tests unchanged

**Verify:** `just test` → all pass (report count)

**Steps:**

- [ ] **Step 1: Failing tests** in `tests/test_index.py`: a release fixture with two versions; assert exclusion (absent from `projects`, absent from `versions`, and the dedupe-slot proof), yank with a string reason and with `True`, the rendered HTML attribute in both forms, the JSON key in both forms, and absence of both when not yanked.

- [ ] **Step 2: `index.py`.**
  - `FileEntry` gains `yanked: str | bool` (docstring: PEP 592 — `False` when not yanked, else `True` or the reason string).
  - `collect_projects` gains a final `filters` parameter defaulting to an empty `Filters()`; import `Filters` from `config` alongside the existing imports.
  - Inside the asset loop, after the project name and version are known and **before** the `seen` duplicate check: if `filters.is_excluded(project, version)` → `continue`.
  - Compute `yanked = filters.yank_reason(project, version)` and put it on the appended entry.
  - `_json_project_page`: when `file["yanked"]` is truthy, add `entry["yanked"] = file["yanked"]` (a `True` stays `true`; a string stays the string).

- [ ] **Step 3: Template.** In `project.html`, extend the anchor's conditional attributes with, when `file.yanked` is truthy, `data-yanked="{{ file.yanked if file.yanked is string else '' }}"`. Keep the existing `#sha256=` fragment and metadata attributes intact and their conditions unchanged.

- [ ] **Step 4: CLI.** Pass the config's filters into `collect_projects`. Match however Task 1 exposed them (`cfg.filters` or constructing `Filters` from `cfg`).

- [ ] **Step 5: Verify.** `just test`; `just fix`; `just check-types`.

*(Driver checkpoint: commit as "Apply yank and exclude filters to the index")*

---

### Task 3: Docs + full gate

**Goal:** Reference and how-to cover both keys; gate green.

**Files:**
- Modify: `doc/source/reference/configuration.rst`, `doc/source/how-to/index.rst`, `doc/source/changelog.rst`, `README.md`
- Create: `doc/source/how-to/yank-a-release.rst`

**Acceptance Criteria:**
- [ ] `configuration.rst` documents both keys in the existing per-key format (type, default, constraints, behavior, YAML example) and adds every new `ConfigError` message to its Validation errors section
- [ ] New how-to answers "How do I yank a bad release?" and covers `exclude` as the harder-edged alternative, including the template-override caveat
- [ ] README's config example mentions both keys
- [ ] `just check-all` → exit 0 (captured directly, not through a pipe)

**Verify:** `just check-all > /tmp/gate.log 2>&1; echo EXIT=$?` → `EXIT=0`

**Steps:**

- [ ] **Step 1: `configuration.rst`.** Add `yanked` and `exclude` to the summary table and one subsection each, following the page's existing structure exactly. Add every new error message verbatim to the Validation errors section, in the order `config.load` raises them. Extend the complete annotated example.

- [ ] **Step 2: `how-to/yank-a-release.rst`.** Question title, short answer, the YAML, what pip does with a yanked file (skipped in resolution unless the requirement pins that exact version, reason surfaced to the user), how it differs from `exclude` (yank keeps installs pinned to it working; exclude breaks them), the wholesale-template-override caveat, and a pointer to the reference. Add it to the how-to toctree — match whatever ordering/style the index uses.

- [ ] **Step 3: README.** Add both keys to the commented config example (they sit inside the `<!-- docs-index-start -->` region, so they appear in the docs index too — keep lines short).

- [ ] **Step 4: Changelog** bullet.

- [ ] **Step 5: Gate.** `just fix`; `just test`; `just check-all` capturing the true exit code. Fix any linkcheck failure by correcting the URL — never by disabling linkcheck.

*(Driver checkpoint: commit as "Document yank and exclude")*

---

## After the plan

Driver: commit the checkpoints. Yanking is now a config edit plus a rebuild —
no release deletion, and anyone pinned to the yanked version keeps working.
