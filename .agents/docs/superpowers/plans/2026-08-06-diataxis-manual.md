# Diátaxis Documentation Manual Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers-extended-cc:subagent-driven-development (recommended) or superpowers-extended-cc:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **PROJECT RULE (AGENTS.md):** agents never commit or push — the human driver
> does. Implementers stop at "verified in working tree".

**Goal:** A complete Diátaxis manual — three standalone deployment tutorials, FAQ-framed how-to guides, exhaustive reference (YAML config, CLI, source), and explanation on an index that includes the README body.

**Architecture:** `myst-parser` lets `index.rst` include the README between HTML-comment markers (single source of truth). `sphinxcontrib-typer` generates the CLI reference from the live typer app. Content lives under `doc/source/{tutorials,how-to,reference}/`.

**Spec:** `.agents/docs/superpowers/specs/2026-08-06-diataxis-manual-design.md`

**Context for every implementer:**
- **Accuracy over prose.** Every config key, default, error message, CLI option, workflow filename and behavioral claim MUST be verified against the actual source (`src/ghr_pypi/config.py`, `cli.py`, `index.py`, `.github/workflows/*.yml`, `justfile`) — read them, do not rely on this plan or on memory. If the plan and the code disagree, the code wins; say so in your report.
- Docs are RST (except the included README). doc8 enforces **max line length 100**; keep lines shorter.
- `just check-all` runs sphinx **linkcheck** — every external URL must resolve. Prefer linking to stable, canonical URLs (peps.python.org, docs.github.com, developers.cloudflare.com, nginx.org). Do not invent URLs.
- The tree carries a lot of uncommitted work; touch only your task's files.
- Verify with `just check-docs` (doc8) and `just build-docs-html`; the final task runs the full gate.

---

### Task 1: Scaffolding — dependencies, conf.py, skeleton, index

**Goal:** The docs build with the new extensions, the four-part skeleton exists with working toctrees, and `index.rst` renders the README body plus a docs-only explanation section.

**Files:**
- Modify: `pyproject.toml` (docs dependency group), `uv.lock`, `doc/source/conf.py`, `doc/source/index.rst`, `README.md`
- Create: `doc/source/tutorials/index.rst`, `doc/source/how-to/index.rst`, `doc/source/reference/api.rst`

**Acceptance Criteria:**
- [ ] `myst-parser` and `sphinxcontrib-typer` in the docs group; both enabled in `conf.py`
- [ ] `index.rst` includes the README body via `:parser: myst_parser.sphinx_` between markers, and the rendered HTML contains README prose
- [ ] README's repo-relative links converted to absolute `https://github.com/bckohan/ghr-pypi/blob/main/...` URLs (so they work on GitHub AND in docs)
- [ ] Toctree: tutorials, how-to, reference, changelog — no orphan-page warnings
- [ ] `just build-docs-html` succeeds; `just check-docs` clean

**Verify:** `just build-docs-html` → success; `grep -c 'Aggregating multiple repositories' doc/build/html/index.html` → ≥1

**Steps:**

- [ ] **Step 1: Dependencies.** Add `"myst-parser>=4.0"` and `"sphinxcontrib-typer>=0.5"` to the `docs` dependency group in `pyproject.toml` (find it: `grep -n -A12 'docs = \[' pyproject.toml`). Run `uv sync --all-extras --group docs` (or `just _install-docs`) and confirm both import.

- [ ] **Step 2: conf.py.** Add `"myst_parser"` and `"sphinxcontrib_typer"` to `extensions`. Keep the existing entries. If `myst_parser` warns about the `.md` source suffix, do NOT register `.md` as a source suffix — the README is *included*, not a page.

- [ ] **Step 3: README markers + absolute links.** In `README.md`, put `<!-- docs-index-start -->` immediately after the badge block (before the tagline paragraph) and `<!-- docs-index-end -->` at the end of the last narrative section that belongs in docs (end of "Development", i.e. the file's end). Convert every repo-relative link inside that region to an absolute GitHub URL — find them with `grep -n '](\.\|](packages\|](doc' README.md`. Keep the badges OUTSIDE the markers.

- [ ] **Step 4: index.rst.** Keep the existing title/badges block and `.. include:: ./refs.rst`. Replace the single-line tagline body with:

```rst
.. include:: ../../README.md
   :parser: myst_parser.sphinx_
   :start-after: <!-- docs-index-start -->
   :end-before: <!-- docs-index-end -->
```

Then add a docs-only explanation section (~400-600 words) titled **Why this design** covering: why a static index instead of an index server (no service to run, no credentials at rest, CDN-cacheable); why GitHub release assets are a reasonable package store (already durable, already access-controlled, already CDN-backed); the trust model (PEP 503 `#sha256=` fragments, API digests verified on mirror, what the index does *not* protect against); and **when not to use it** (private repos without `mirror: true`, more than 100 releases per repo, packages needing a real upload API). Follow with the toctree:

```rst
.. toctree::
   :maxdepth: 2
   :caption: Contents:

   tutorials/index
   how-to/index
   reference/index
   changelog
```

- [ ] **Step 5: Skeleton pages.** Create `doc/source/tutorials/index.rst` and `doc/source/how-to/index.rst`, each with a title, a one-paragraph Diátaxis-appropriate intro (tutorials = learning-oriented, guaranteed success; how-to = task-oriented answers), and a toctree listing the pages the later tasks will add — create those pages as one-line stubs now so the build has no missing-reference warnings, or add the toctree entries in the later tasks. Choose one approach and say which. Move the existing autodoc content from `reference/index.rst` into `reference/api.rst` (title it "Source Reference"), and turn `reference/index.rst` into a title + intro + toctree listing `configuration`, `cli`, `api` (stubs for the first two).

- [ ] **Step 6: Verify.** `just build-docs-html`; `just check-docs`; confirm README prose appears in the built index; no sphinx warnings about missing toctree entries.

*(Driver checkpoint: commit as "Scaffold Diátaxis documentation")*

---

### Task 2: Reference — configuration and CLI

**Goal:** Exhaustive, code-verified reference for every YAML key and the whole CLI.

**Files:**
- Modify/create: `doc/source/reference/configuration.rst`, `doc/source/reference/cli.rst`, `doc/source/reference/index.rst`

**Acceptance Criteria:**
- [ ] Every key accepted by `config.load` is documented with type, default, whether required, constraints, and a YAML example
- [ ] Every `ConfigError` message in `config.py` appears in the docs with its cause
- [ ] Cross-key rules documented (`missing_digest` + `mirror` conflict; `--mirror` + `--config` conflict)
- [ ] CLI page renders the real command via `sphinxcontrib-typer`, plus prose on `GITHUB_TOKEN`, exit codes, and worked invocations
- [ ] Nothing documented that does not exist in the code

**Verify:** `just build-docs-html`; every key in `config.py`'s `_KNOWN_KEYS` appears in `configuration.rst`

**Steps:**

- [ ] **Step 1: Read the source first.** `src/ghr_pypi/config.py` in full (keys, defaults, validation order, every error string) and `src/ghr_pypi/cli.py` (options, help text, error paths, exit codes). Build the key list from `_KNOWN_KEYS` and the `Config` dataclass — not from this plan.

- [ ] **Step 2: `configuration.rst`.** Intro (what the file is, how it is passed, that `--config` and the positional repo are mutually exclusive), a summary table of all keys, then one subsection per key: type, default, required?, constraints, behavior, YAML example. Then a "Validation errors" section listing each `ConfigError` message verbatim with its cause and fix. Then a complete annotated example config using every key.

- [ ] **Step 3: `cli.rst`.** Use the extension's directive (check `sphinxcontrib-typer`'s docs for exact syntax; typically):

```rst
.. typer:: ghr_pypi.cli:app
   :prog: ghr-pypi
   :width: 80
```

Verify the directive renders — if the module path or options differ, adjust to what actually works and report it. Around it, write: synopsis, the two invocation forms, `--token` / `GITHUB_TOKEN`, what exit code 1 means and the conditions that cause it (empty index, config error, API failure, mirror failure, malformed repo, `--mirror` with `--config`), and 3–4 worked examples (single repo, multi-repo config, private repo with `--mirror`, JSON-only).

- [ ] **Step 4: Wire and verify.** Ensure `reference/index.rst`'s toctree lists `configuration`, `cli`, `api`. `just build-docs-html`; `just check-docs`. Cross-check: for each key in `_KNOWN_KEYS`, grep it in `configuration.rst`.

*(Driver checkpoint: commit as "Add configuration and CLI reference")*

---

### Task 3: Tutorials — GitHub Pages, Cloudflare, nginx

**Goal:** Three standalone, end-to-end, copy-pasteable tutorials that each end with a successful `pip install` from the reader's own index.

**Files:**
- Create: `doc/source/tutorials/github-pages.rst`, `cloudflare.rst`, `nginx.rst`; modify `tutorials/index.rst`

**Acceptance Criteria:**
- [ ] Each tutorial stands alone: prerequisites → publish a release with a wheel → build the index → deploy → verify with `pip install --index-url ...` → next steps
- [ ] All workflow YAML matches this repo's actual working workflows (`pages.yml`, `release.yml`) — read them
- [ ] No decision points or "if you prefer" branches (Diátaxis: tutorials are a single guaranteed path)
- [ ] All external links resolve (linkcheck runs in the final gate)

**Verify:** `just build-docs-html`; `just check-docs`

**Steps:**

- [ ] **Step 1: Read `.github/workflows/pages.yml` and `release.yml`** and base the GitHub Pages tutorial's YAML on them (simplified for a newcomer but functionally correct).

- [ ] **Step 2: `github-pages.rst`.** Settings → Pages → Source: GitHub Actions; a minimal release workflow that attaches a wheel; the pages workflow running `uvx ghr-pypi "$GITHUB_REPOSITORY" --out site`; permissions and the `release`-event caveat (workflow-created releases don't fire `release` events — dispatch pages explicitly); the resulting URL; `pip install --index-url https://<owner>.github.io/<repo>/simple/ <pkg>`.

- [ ] **Step 3: `cloudflare.rst`.** Cloudflare Pages project connected to the repo (or Direct Upload via `wrangler`); build command producing `site/`; the `GITHUB_TOKEN` secret; a `_headers` file for immutable caching of `files/` and short TTL for `simple/`; verify with pip. Close with a short "what Workers would add" note (content negotiation for the JSON API, private-asset redirect) marked as beyond the tutorial.

- [ ] **Step 4: `nginx.rst`.** Build in CI or locally, ship `site/` to the server (rsync); an nginx `server` block serving it, including: `types` entry so `.metadata` is served as `application/octet-stream` (or `text/plain`), an `Accept`-based `map`/`location` that serves `index.json` when the client asks for `application/vnd.pypi.simple.v1+json` (this is the payoff nginx offers over static hosts), optional `auth_basic` for a private index, and `gzip_static`. Verify with pip, then with `pip --index-url` behind basic auth (`https://user:pass@host/simple/`).

- [ ] **Step 5: `tutorials/index.rst`.** Intro explaining these are learning-oriented and each is self-contained; toctree with the three pages; a one-line "which should I pick?" table (Pages = zero infra; Cloudflare = CDN + Workers; nginx = full control, content negotiation, auth).

*(Driver checkpoint: commit as "Add deployment tutorials")*

---

### Task 4: How-to guides + final gate

**Goal:** FAQ-framed task guides, README documentation link, changelog entry, and a green full gate.

**Files:**
- Create: `doc/source/how-to/*.rst` (one page per guide, or a single page with sections — implementer's call, state which and why)
- Modify: `doc/source/how-to/index.rst`, `README.md`, `doc/source/changelog.rst`

**Acceptance Criteria:**
- [ ] All ten FAQ guides from the spec are answered, each with concrete commands/config, not prose alone
- [ ] Each answer verified against the code (behavior claims must be true)
- [ ] README gains a "Documentation" pointer near the top (outside the docs-index markers if it would read oddly in the manual — implementer's judgment, state which)
- [ ] `just check-all` → exit 0 (includes linkcheck)

**Verify:** `just check-all > /tmp/gate.log 2>&1; echo EXIT=$?` → `EXIT=0` (captured directly, not through a pipe)

**Steps:**

- [ ] **Step 1: Write the ten guides** listed in the spec's "How-to guides" section. Each: the question as the title, a 1–2 sentence answer, then the concrete steps/config, then a pointer to the relevant reference section. Keep them short — how-to guides answer, they do not teach.

- [ ] **Step 2: `how-to/index.rst`** — intro plus toctree (or the section list if single-page).

- [ ] **Step 3: README** — add a Documentation link near the top pointing at `https://ghr-pypi.readthedocs.io`.

- [ ] **Step 4: Changelog** bullet: `* Added a full Diátaxis documentation manual: tutorials, how-to guides, and reference.`

- [ ] **Step 5: Full gate.** `just fix`; `just test` (should be unchanged — report the count); `just check-all` capturing the true exit code. If linkcheck fails on a URL, fix or replace the URL; do not disable linkcheck.

*(Driver checkpoint: commit as "Add how-to guides and documentation index")*

---

## After the plan

Driver: commit the checkpoints. The RTD build will pick the manual up on the
next push; the first tag build also exercises the `PACKAGE_VERSION` export
added by the dynamic-versioning work.
