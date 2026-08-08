# `extract-meta` Subcommand Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers-extended-cc:subagent-driven-development (recommended) or superpowers-extended-cc:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **PROJECT RULE (AGENTS.md):** agents never commit or push — the human driver
> does. Implementers stop at "verified in working tree".

**Goal:** `ghr-pypi extract-meta dist/` writes each wheel's PEP 658 core metadata to `<wheel>.metadata`, replacing a `python3` heredoc in the release workflow — which requires today's single command to become the `index` subcommand.

**Architecture:** The zip-reading logic is lifted out of `index.extract_metadata` into a shared `index.read_wheel_metadata`. `cli.py` gains two explicitly-named commands (`index`, `extract-meta`); the mirroring path's behavior is unchanged. `release.yml` and `how-to/publish-metadata.rst` drop their copies of the heredoc.

**Spec:** `.agents/docs/superpowers/specs/2026-08-07-extract-meta-subcommand-design.md`

**Context for the implementer:**
- Current suite: 223 tests green, `just check-all` exit 0. The tree carries a
  large amount of uncommitted work — touch only your task's files.
- **Do NOT run `just test-all <path>`.** It splices arguments into `uv run`'s
  flag position and destroys the project venv. Use `just test` or
  `uv run pytest <path>`.
- `cli.py` does `from ghr_pypi import index`, so a command function named
  `index` would shadow the module. Both commands take **explicit** names in the
  decorator and differently-named functions.
- doc8 enforces a 100-character line limit on RST. `just check-all` must stay
  green.
- Read `src/ghr_pypi/cli.py` and `src/ghr_pypi/index.py` before writing; the
  code wins over this plan if they disagree.

---

### Task 1: `read_wheel_metadata` helper

**Goal:** One implementation of "read a wheel's core METADATA", used by the existing mirroring path.

**Files:**
- Modify: `src/ghr_pypi/index.py` (add the function; rewrite the body of `extract_metadata`, currently at ~line 352)
- Modify: `tests/test_index.py`

**Acceptance Criteria:**
- [ ] `read_wheel_metadata(path) -> bytes` returns the METADATA bytes of a valid wheel
- [ ] It raises `zipfile.BadZipFile` for a non-zip, for a zip with no `.dist-info/METADATA`, and for a zip with two top-level `.dist-info/METADATA` members
- [ ] It raises `OSError` for a missing file
- [ ] `extract_metadata`'s behavior is unchanged — same warning text, same `core_metadata` values, existing tests still pass untouched

**Verify:** `uv run pytest tests/test_index.py -q` → all pass; `just check-types` clean

**Steps:**

- [ ] **Step 1: Write the failing tests.** Add to `tests/test_index.py`. Reuse whatever wheel-building helper the file already has for the existing `extract_metadata` tests — read the file first and follow it rather than writing a new builder. Add `import zipfile` and `import pytest` only if the module does not already have them.

```python
def test_read_wheel_metadata_returns_the_payload(tmp_path):
    wheel = tmp_path / "demo-1.0-py3-none-any.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr("demo-1.0.dist-info/METADATA", "Name: demo\n")
    assert index.read_wheel_metadata(wheel) == b"Name: demo\n"


def test_read_wheel_metadata_rejects_a_non_zip(tmp_path):
    wheel = tmp_path / "demo-1.0-py3-none-any.whl"
    wheel.write_bytes(b"not a zip")
    with pytest.raises(zipfile.BadZipFile):
        index.read_wheel_metadata(wheel)


def test_read_wheel_metadata_rejects_a_wheel_without_metadata(tmp_path):
    wheel = tmp_path / "demo-1.0-py3-none-any.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr("demo/__init__.py", "")
    with pytest.raises(zipfile.BadZipFile):
        index.read_wheel_metadata(wheel)


def test_read_wheel_metadata_rejects_two_metadata_members(tmp_path):
    wheel = tmp_path / "demo-1.0-py3-none-any.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr("demo-1.0.dist-info/METADATA", "Name: demo\n")
        archive.writestr("other-1.0.dist-info/METADATA", "Name: other\n")
    with pytest.raises(zipfile.BadZipFile):
        index.read_wheel_metadata(wheel)


def test_read_wheel_metadata_rejects_a_missing_file(tmp_path):
    with pytest.raises(OSError):
        index.read_wheel_metadata(tmp_path / "absent.whl")
```

- [ ] **Step 2: Run and confirm they fail.**

Run: `uv run pytest tests/test_index.py -q`
Expected: the five new tests FAIL with `AttributeError: module 'ghr_pypi.index' has no attribute 'read_wheel_metadata'`.

- [ ] **Step 3: Add the function** to `src/ghr_pypi/index.py`, immediately above `extract_metadata`:

```python
def read_wheel_metadata(path: Path) -> bytes:
    """Return a wheel's :pep:`658` core metadata.

    Reads the single top-level ``*.dist-info/METADATA`` member. Raises
    ``OSError`` when the file cannot be read and ``zipfile.BadZipFile`` when it
    is not a valid zip or does not carry exactly one such member.
    """
    with zipfile.ZipFile(path) as archive:
        members = [
            member
            for member in archive.namelist()
            if member.endswith(".dist-info/METADATA") and member.count("/") == 1
        ]
        if len(members) != 1:
            raise zipfile.BadZipFile("no unique .dist-info/METADATA member")
        return archive.read(members[0])
```

- [ ] **Step 4: Rewrite `extract_metadata`'s inner loop** to call it. The `try`/`except`, the warning text, and both `core_metadata` assignments stay exactly as they are:

```python
            wheel = out_dir / "files" / project / entry["filename"]
            try:
                payload = read_wheel_metadata(wheel)
            except (OSError, zipfile.BadZipFile) as error:
                print(
                    f"warning: cannot extract metadata from "
                    f"{entry['filename']}: {error}",
                    file=sys.stderr,
                )
                entry["core_metadata"] = False
                continue
            wheel.with_name(wheel.name + ".metadata").write_bytes(payload)
            entry["core_metadata"] = hashlib.sha256(payload).hexdigest()
```

- [ ] **Step 5: Verify.**

Run: `uv run pytest tests/test_index.py -q` → all pass
Run: `just test` → report the total count
Run: `just fix`, then `just check-types` → clean

Confirm no existing `extract_metadata` test needed editing. If one did, say so
and explain why — a behavior change here is out of scope.

*(Driver checkpoint: commit as "Extract read_wheel_metadata helper")*

---

### Task 2: `index` and `extract-meta` subcommands

**Goal:** `ghr-pypi index` is today's command; `ghr-pypi extract-meta PATH...` writes `.metadata` sidecars; bare `ghr-pypi` prints help.

**Files:**
- Modify: `src/ghr_pypi/cli.py`
- Modify: `tests/test_cli.py`

**Acceptance Criteria:**
- [ ] `ghr-pypi index` behaves exactly as `ghr-pypi` did — all defaults intact
- [ ] Bare `ghr-pypi` exits non-zero and prints help, without attempting a build
- [ ] `extract-meta` accepts wheel paths and directories; directories are scanned **non-recursively**
- [ ] Each wheel gets `<wheel>.metadata` beside it with the exact METADATA bytes; an existing file is overwritten
- [ ] All five error cases exit 1 with a message naming the offending path
- [ ] No paths at all exits non-zero (Typer's own required-argument handling)

**Verify:** `just test` → all pass (report the count)

**Steps:**

- [ ] **Step 1: Re-point the existing CLI tests.** In `tests/test_cli.py`, every
  `runner.invoke(app, [...])` call (there are 5) gains `"index"` as its first
  list element. The `_resolve_config` unit tests call the function directly and
  do **not** change. Run `uv run pytest tests/test_cli.py -q` and confirm they
  now fail (the command does not exist yet) — this is the red step that proves
  the rename lands.

- [ ] **Step 2: Write the failing `extract-meta` tests.** Add to
  `tests/test_cli.py`:

```python
def make_wheel(path, name="demo", version="1.0", payload="Name: demo\n"):
    wheel = path / f"{name}-{version}-py3-none-any.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr(f"{name}-{version}.dist-info/METADATA", payload)
    return wheel


def test_extract_meta_scans_a_directory(tmp_path):
    make_wheel(tmp_path, "one", payload="Name: one\n")
    make_wheel(tmp_path, "two", payload="Name: two\n")
    result = runner.invoke(app, ["extract-meta", str(tmp_path)])
    assert result.exit_code == 0, all_output(result)
    assert (tmp_path / "one-1.0-py3-none-any.whl.metadata").read_bytes() == b"Name: one\n"
    assert (tmp_path / "two-1.0-py3-none-any.whl.metadata").read_bytes() == b"Name: two\n"
    assert "2 wheel(s)" in result.output


def test_extract_meta_accepts_an_explicit_wheel(tmp_path):
    wheel = make_wheel(tmp_path)
    result = runner.invoke(app, ["extract-meta", str(wheel)])
    assert result.exit_code == 0, all_output(result)
    assert wheel.with_name(wheel.name + ".metadata").read_bytes() == b"Name: demo\n"


def test_extract_meta_does_not_recurse(tmp_path):
    make_wheel(tmp_path, "top")
    nested = tmp_path / "nested"
    nested.mkdir()
    buried = make_wheel(nested, "buried")
    result = runner.invoke(app, ["extract-meta", str(tmp_path)])
    assert result.exit_code == 0, all_output(result)
    assert not buried.with_name(buried.name + ".metadata").exists()


def test_extract_meta_overwrites(tmp_path):
    wheel = make_wheel(tmp_path)
    sidecar = wheel.with_name(wheel.name + ".metadata")
    sidecar.write_bytes(b"stale")
    result = runner.invoke(app, ["extract-meta", str(wheel)])
    assert result.exit_code == 0, all_output(result)
    assert sidecar.read_bytes() == b"Name: demo\n"


def test_extract_meta_rejects_a_missing_path(tmp_path):
    result = runner.invoke(app, ["extract-meta", str(tmp_path / "absent")])
    assert result.exit_code == 1
    assert "does not exist" in all_output(result)


def test_extract_meta_rejects_a_non_wheel(tmp_path):
    other = tmp_path / "notes.txt"
    other.write_text("hi")
    result = runner.invoke(app, ["extract-meta", str(other)])
    assert result.exit_code == 1
    assert "is not a wheel" in all_output(result)


def test_extract_meta_rejects_an_empty_directory(tmp_path):
    result = runner.invoke(app, ["extract-meta", str(tmp_path)])
    assert result.exit_code == 1
    assert "no wheels" in all_output(result)


def test_extract_meta_rejects_an_unreadable_wheel(tmp_path):
    wheel = tmp_path / "broken-1.0-py3-none-any.whl"
    wheel.write_bytes(b"not a zip")
    result = runner.invoke(app, ["extract-meta", str(wheel)])
    assert result.exit_code == 1
    assert "broken-1.0-py3-none-any.whl" in all_output(result)


def test_extract_meta_requires_a_path():
    result = runner.invoke(app, ["extract-meta"])
    assert result.exit_code != 0


def test_bare_invocation_prints_help():
    result = runner.invoke(app, [])
    assert result.exit_code != 0
    assert "extract-meta" in all_output(result)
```

`runner`, `app` and `all_output` are existing module-level names — reuse them.
Add `import zipfile` to the test module's imports.

- [ ] **Step 3: Restructure `cli.py`.** Add `import zipfile` to the imports.
  Change the existing command's decorator and function name — **its body and
  signature are otherwise untouched**:

```python
@app.command("index")
def build_index(
```

(the parameter list and everything from `"""Build a PEP 503 package index...` onward stays exactly as it is)

- [ ] **Step 4: Add `extract-meta`** below it:

```python
@app.command("extract-meta")
def extract_meta(
    paths: Annotated[
        list[Path],
        typer.Argument(
            metavar="PATH...",
            help="Wheels, or directories to scan (non-recursively) for *.whl",
        ),
    ],
) -> None:
    """Write each wheel's PEP 658 core metadata to <wheel>.metadata.

    Upload the sidecars alongside their wheels in the same release: the index
    can only advertise metadata that lives at the wheel's own URL plus
    ``.metadata``.
    """
    wheels: list[Path] = []
    for path in paths:
        if not path.exists():
            typer.echo(f"error: {path} does not exist", err=True)
            raise typer.Exit(1)
        if path.is_dir():
            found = sorted(path.glob("*.whl"))
            if not found:
                typer.echo(f"error: no wheels in {path}", err=True)
                raise typer.Exit(1)
            wheels.extend(found)
        elif path.suffix == ".whl":
            wheels.append(path)
        else:
            typer.echo(f"error: {path} is not a wheel", err=True)
            raise typer.Exit(1)
    for wheel in wheels:
        try:
            payload = index.read_wheel_metadata(wheel)
        except (OSError, zipfile.BadZipFile) as error:
            typer.echo(
                f"error: cannot extract metadata from {wheel}: {error}", err=True
            )
            raise typer.Exit(1) from error
        target = wheel.with_name(wheel.name + ".metadata")
        target.write_bytes(payload)
        typer.echo(f"wrote {target}")
    typer.echo(f"extracted metadata from {len(wheels)} wheel(s)")
```

- [ ] **Step 5: Verify the surface by hand.** Typer's handling of a required
  variadic `list[Path]` argument is the one thing here worth checking
  empirically rather than assuming:

```
uv run ghr-pypi --help
uv run ghr-pypi index --help
uv run ghr-pypi extract-meta --help
uv run ghr-pypi ; echo EXIT=$?
uv run ghr-pypi extract-meta ; echo EXIT=$?
```

Both bare invocations must exit non-zero. Report the observed exit codes. If
`extract-meta` with no arguments exits 0 instead of erroring, add
`typer.Argument(..., )` handling or a `if not paths:` guard, and say what you
did.

- [ ] **Step 6: Verify.**

Run: `uv run pytest tests/test_cli.py -q` → all pass
Run: `just test` → report the total count
Run: `just fix`, then `just check-types` → clean

- [ ] **Step 7: Prove the wiring (mutation testing — do not skip).** One at a
  time, reverting each:

1. Change `path.glob("*.whl")` to `path.rglob("*.whl")` → confirm
   `test_extract_meta_does_not_recurse` FAILS. Revert.
2. Change the `raise typer.Exit(1)` in the unreadable-wheel handler to
   `continue` → confirm `test_extract_meta_rejects_an_unreadable_wheel` FAILS.
   Revert.

Report both observed results.

*(Driver checkpoint: commit as "Add index and extract-meta subcommands")*

---

### Task 3: Workflow, docs, full gate

**Goal:** The release workflow and every documented invocation use the subcommands; the heredoc is gone from both places it lives.

**Files:**
- Modify: `.github/workflows/release.yml`, `.github/workflows/pages.yml`, `README.md`, `direction.md`
- Modify: `doc/source/reference/cli.rst`, `doc/source/how-to/publish-metadata.rst`, `doc/source/changelog.rst`, and every other page under `doc/source/` carrying a `ghr-pypi` invocation

**Acceptance Criteria:**
- [ ] `release.yml` calls `ghr-pypi extract-meta dist/`, still before the sigstore step
- [ ] No `python3 - <<'EOF'` metadata heredoc remains in `release.yml` or `publish-metadata.rst`
- [ ] Every `ghr-pypi` invocation in the workflows, README and docs names a subcommand
- [ ] `cli.rst` documents both commands; the `.. typer::` directive renders the tree
- [ ] The changelog records the breaking change
- [ ] The implemented `direction.md` bullet is removed
- [ ] `just check-all` → exit 0

**Verify:** `just check-all > /tmp/gate.log 2>&1; echo EXIT=$?` → `EXIT=0`

**Steps:**

- [ ] **Step 1: `.github/workflows/release.yml`.** Replace the whole
  "Extract PEP 658 metadata from wheels" step (the `python3 - <<'EOF'`
  heredoc) with:

```yaml
      # PEP 658: publish each wheel's core METADATA as a sibling release
      # asset so link-mode indexes can serve dependency metadata. Installing
      # from dist/ runs the version being released — no PyPI round trip.
      - name: Extract PEP 658 metadata from wheels
        run: |
          python3 -m pip install --quiet dist/ghr_pypi-*.whl
          ghr-pypi extract-meta dist/
```

Leave it exactly where it is in the step order — **before** the sigstore
signing step, so the `.metadata` files exist for signing and upload. Do not
touch any other step.

- [ ] **Step 2: `.github/workflows/pages.yml`.** Change the build step's `run:`
  to `uv run --locked --no-default-groups ghr-pypi index`, and the comment's
  `#   uvx ghr-pypi` to `#   uvx ghr-pypi index`. Nothing else in that file
  changes — keep the pinned action SHAs as they are in the file.

- [ ] **Step 3: `doc/source/reference/cli.rst`.** This page currently documents
  one command. Restructure it:

  - The opening sentence becomes "``ghr-pypi`` has two commands." followed by
    a one-line description of each.
  - The synopsis block becomes:

```rst
.. code-block:: text

   ghr-pypi index [REPO]... [--out DIRECTORY] [--config PATH] [--token TOKEN] [--mirror]
   ghr-pypi extract-meta PATH...
```

  - Every existing example on the page gains `index`.
  - The `.. typer::` directive gains `:show-nested:` so both commands render.
    Verify that option name against the installed `sphinxcontrib-typer` rather
    than trusting this plan — build the docs and look at the output. If the
    directive already renders subcommands by default, leave it alone and say so.
  - Add a new top-level section for `extract-meta` at the end, before
    "Exit codes":

```rst
``extract-meta``
================

.. code-block:: sh

   ghr-pypi extract-meta dist/
   ghr-pypi extract-meta dist/demo-1.0-py3-none-any.whl

Writes each wheel's :pep:`658` core metadata to ``<wheel>.metadata`` beside the
wheel, overwriting any existing file, and prints one line per wheel followed by
a count. Each ``PATH`` is either a wheel or a directory; a directory is scanned
for ``*.whl`` **without recursing**. Sdists are ignored — core metadata comes
from the wheel.

This exists for release workflows. The index can only advertise metadata that
lives at the wheel's own URL plus ``.metadata``, so in link mode the sidecar has
to be uploaded as an asset of the same release as its wheel — see
:ref:`howto-publish-metadata`.

Every one of these exits 1, naming the path: a path that does not exist, an
explicit path that is not a ``.whl``, a directory containing no wheels, a wheel
that cannot be opened, and a wheel without exactly one top-level
``*.dist-info/METADATA`` member. Nothing is skipped with a warning — a release
that silently ships no metadata is the failure this command prevents.
```

  Check the "Exit codes" table afterwards and make sure its wording covers both
  commands rather than only the index build.

- [ ] **Step 4: `doc/source/how-to/publish-metadata.rst`.** Replace the YAML
  block containing the `python3 - <<'EOF'` heredoc (currently around lines
  28-46) with:

```rst
.. code-block:: yaml

   - name: Extract PEP 658 metadata from wheels
     run: |
       python3 -m pip install --quiet ghr-pypi
       ghr-pypi extract-meta dist/

   - name: Upload the wheels, sdists and metadata
     env:
       GH_TOKEN: ${{ github.token }}
     run: gh release create "$GITHUB_REF_NAME" dist/* --generate-notes
```

Keep the surrounding prose, including the paragraph after it about per-release
pairing. Add a sentence pointing at :ref:`cli` for the command's full behavior.

- [ ] **Step 5: Sweep the remaining docs and the README.** Every `ghr-pypi`
  invocation that builds an index needs `index`. Find them with:

```bash
grep -rn "ghr-pypi " --include='*.rst' --include='*.md' doc/source README.md | grep -v "ghr-pypi index\|ghr-pypi extract-meta"
```

Judge each hit: `pip install ghr-pypi` and prose mentions of the project name
are not invocations. Known invocation sites include `README.md` (the synopsis,
`uvx ghr-pypi --help`, the Pages snippet, the config example, the mirroring
example), `doc/source/reference/configuration.rst`,
`doc/source/tutorials/{github-pages,cloudflare,nginx}.rst`, and several pages
under `doc/source/how-to/`. Re-run the grep afterwards until only non-invocation
hits remain, and report what you left and why.

The README region between `<!-- docs-index-start -->` and
`<!-- docs-index-end -->` is MyST-included verbatim into `doc/source/index.rst`
— keep those lines short.

- [ ] **Step 6: `doc/source/changelog.rst`.** Add to the `2026.8.X` section:

```rst
* **Breaking:** the index build is now the ``index`` subcommand —
  ``ghr-pypi OWNER/NAME`` becomes ``ghr-pypi index OWNER/NAME``. Bare
  ``ghr-pypi`` prints help.
* Added ``ghr-pypi extract-meta PATH...``, which writes each wheel's :pep:`658`
  core metadata to ``<wheel>.metadata`` for upload as a release asset.
```

Match the file's existing bullet style; do not invent a new one.

- [ ] **Step 7: `direction.md`.** Delete the bullet beginning "Add simple
  command for extracting metadata". Leave the remaining bullets untouched.
  (This file is gitignored, so it will not appear in `git status` — verify the
  edit by reading it back.)

- [ ] **Step 8: Gate.**

```
just fix
just test
just check-all > /tmp/gate.log 2>&1; echo EXIT=$?
```

Expect `EXIT=0`. Fix any linkcheck failure by correcting the URL — never by
disabling linkcheck. Note that the justfile invokes linkcheck with a leading
`-`, so link failures do not fail the gate: read `doc/build/output.txt`
yourself and report what it says.

Then prove the heredoc is gone:

```bash
grep -rn "dist-info/METADATA" --include='*.yml' --include='*.rst' --include='*.md' . | grep -v '^\./\.agents/' | grep -v '^\./doc/build/'
```

Expected: no output (the only remaining copy is in `src/ghr_pypi/index.py`).

*(Driver checkpoint: commit as "Use ghr-pypi extract-meta in the release workflow")*

---

## After the plan

Driver: commit the checkpoints. The wheel-metadata read now exists once, in
`index.py`, reachable from a command anyone can run — including this
repository's own release workflow.
