# `extract-meta` Subcommand — Design

**Date:** 2026-08-07
**Status:** Approved

## Problem

Publishing PEP 658 metadata alongside release assets means writing each
wheel's core `METADATA` to `<wheel>.metadata` before uploading. Today that
logic lives in a `python3` heredoc inside `.github/workflows/release.yml` —
untestable, uncopyable, and a second implementation of what
`index.extract_metadata` already does for mirrored wheels. Anyone else wanting
PEP 658 metadata in their own release workflow has to copy the heredoc.

Exposing it as a command requires the existing single command to become a named
subcommand.

## Decisions

- **Two subcommands.** `ghr-pypi index` is today's command verbatim;
  `ghr-pypi extract-meta` is new. Bare `ghr-pypi` prints help.
- **One implementation of the wheel read**, shared by the mirroring path and
  the new command.
- **`release.yml` adopts the command**, so the repository uses the thing it
  ships rather than a private copy of it.

## CLI restructure

Typer derives a command's name from its function name, but `index` is already
bound in `cli.py` by `from ghr_pypi import index`. Both commands therefore take
explicit names:

```python
@app.command("index")
def build_index(...):     # today's `build`, body unchanged
@app.command("extract-meta")
def extract_meta(...):
```

`ghr-pypi index` keeps every default from the repository-argument work: no
repository (falls back to `$GITHUB_REPOSITORY`), no `--out` (defaults to
`_site`). `_resolve_config` is untouched.

**Breaking change.** `ghr-pypi OWNER/NAME --out site`, valid in the published
`2026.8.6`, now requires `index`. Recorded in the changelog as such.

## `extract-meta`

```
ghr-pypi extract-meta PATH...
```

Each `PATH` is a wheel or a directory. Directories are scanned
**non-recursively** for `*.whl`. For each wheel, the unique top-level
`*.dist-info/METADATA` member is read and written to `<wheel>.metadata` beside
the wheel, overwriting any existing file. One line per wheel goes to stdout,
followed by a count.

At least one `PATH` is required.

Every one of these is a hard error, exit 1:

- a path that does not exist
- an explicit path that is not a `.whl`
- a directory containing no wheels
- a wheel that cannot be opened or is not a valid zip
- a wheel without exactly one top-level `*.dist-info/METADATA` member

A release workflow that silently produces no metadata is precisely the failure
this command exists to prevent, so nothing is skipped with a warning.

Sdists are out of scope: PEP 658 core metadata comes from the wheel.

There is no `--out` option. The only caller uploads `dist/**` wholesale and
needs each `.metadata` next to its wheel.

## Shared helper

`index.py` gains:

```python
def read_wheel_metadata(path: Path) -> bytes:
    """Return a wheel's core METADATA, raising on any failure."""
```

It raises `zipfile.BadZipFile` / `OSError` as the existing code already does —
no new exception type. Callers:

- `index.extract_metadata` (mirroring) calls it inside its existing
  `try`/`except`, warns, and sets `core_metadata = False`. **Its behavior does
  not change.**
- `extract-meta` calls it and lets a failure become exit 1.

## `release.yml`

The heredoc step is replaced. The `github-release` job has no checkout and no
uv, but it does have the freshly built wheel in `dist/`:

```yaml
- name: Extract PEP 658 metadata from wheels
  run: |
    python3 -m pip install --quiet dist/ghr_pypi-*.whl
    ghr-pypi extract-meta dist/
```

Installing from `dist/` rather than PyPI runs the version being released, so
there is no chicken-and-egg on the first release that contains the command.

**Accepted tradeoff:** this puts a step of the release path behind a pip
install and behind the new command working, where the heredoc had no
dependencies at all. The alternative is a knowingly duplicated implementation
in the file that is hardest to test.

The step must run **before** the sigstore signing step, exactly where the
heredoc sits now, so the `.metadata` files are present for upload.

## Fallout

Every invocation site gains `index`:

- `.github/workflows/pages.yml` → `ghr-pypi index`
- `README.md`: the synopsis (line ~38), the Pages snippet (~74), the config
  example (~116), the mirroring example (~167), and `uvx ghr-pypi --help` (~32)
- `doc/source/reference/cli.rst` — restructured for two commands; the
  `.. typer::` directive needs `:show-nested:` to render the tree
- `doc/source/tutorials/{github-pages,cloudflare,nginx}.rst`,
  `doc/source/how-to/*.rst`, `doc/source/reference/configuration.rst` — every
  `ghr-pypi ...` example
- `tests/test_cli.py` — every `runner.invoke(app, [...])` gains `"index"` as
  its first element

`doc/source/reference/cli.rst` also gains an `extract-meta` section: synopsis,
what it writes, the error list, and the release-workflow example. A how-to
already covers publishing metadata (`how-to/publish-metadata.rst`) — it should
point at the command instead of describing the heredoc.

## Testing

- `read_wheel_metadata`: a good wheel; a non-zip; a zip with no `METADATA`; a
  zip with two `.dist-info/METADATA` members.
- `extract-meta` through `CliRunner`: a directory of two wheels writes two
  `.metadata` files with the right bytes; an explicit wheel path; a mix of
  both; overwriting an existing `.metadata`; and each of the five error cases
  exiting 1 with a message naming the offending path.
- Non-recursion is asserted explicitly: a wheel in a subdirectory of the given
  directory is **not** processed.
- `index` subcommand: the existing suite, re-pointed, proves the rename;
  bare `ghr-pypi` exits non-zero with help rather than attempting a build.

## Out of scope

- Changing how metadata works during `index` — no create-and-mirror fallback,
  no new `metadata` config states. (Considered and dropped: PEP 658 pins the
  metadata URL to `<file-url>.metadata`, so serving it in link mode would
  require mirroring the individual wheel. Left as a possible future item.)
- Uploading the `.metadata` files — the release workflow's existing
  `gh release upload dist/**` already covers them.
