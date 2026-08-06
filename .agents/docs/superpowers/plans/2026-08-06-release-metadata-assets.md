# Release `.metadata` Assets Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers-extended-cc:subagent-driven-development (recommended) or superpowers-extended-cc:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **PROJECT RULE (AGENTS.md):** agents never commit or push — the human driver
> does. Implementers stop at "verified in working tree".

**Goal:** Our release workflow uploads `<wheel>.metadata` assets alongside wheels (PEP 658 producer side, dogfooding our own link-mode consumer); the README carries the copyable recipe.

**Spec:** `.agents/docs/superpowers/specs/2026-08-06-release-metadata-assets-design.md`

---

### Task 1: Workflow extraction step + docs

**Goal:** `release.yml`'s github-release job extracts and uploads `.metadata` for every wheel; README documents the recipe.

**Files:**
- Modify: `.github/workflows/release.yml` (github-release job — one new step)
- Modify: `README.md` (PEP 658 section, link-mode bullet)
- Modify: `doc/source/changelog.rst`

**Acceptance Criteria:**
- [ ] New step sits after both download-artifact steps and before "Create GitHub Release"; `.metadata` files never enter the build artifacts (build job untouched; PyPI jobs untouched)
- [ ] Extraction script enforces the unique depth-1 `*.dist-info/METADATA` rule and fails the job otherwise
- [ ] `gh release upload dist/**` and sigstore globs untouched (upload picks the files up as-is; signing stays wheels+sdists)
- [ ] Script verified locally against a real wheel from `uv build`
- [ ] README shows the copyable step + names our release.yml as the live example
- [ ] `just check-all` → exit 0

**Verify:** YAML parses; `uvx zizmor --no-online-audits .github/workflows` no new findings; local script run produces byte-correct `.metadata`; `just check-all` exit 0.

**Steps:**

- [ ] **Step 1: Workflow step.** In `.github/workflows/release.yml`, github-release job, insert after "Download the demo distributions" and before "Sign the dists with Sigstore":

```yaml
      # PEP 658: publish each wheel's core METADATA as a sibling release
      # asset so link-mode indexes can serve dependency metadata.
      - name: Extract PEP 658 metadata from wheels
        run: |
          python3 - <<'EOF'
          import pathlib
          import zipfile

          for wheel in pathlib.Path("dist").glob("*.whl"):
              with zipfile.ZipFile(wheel) as archive:
                  members = [
                      member
                      for member in archive.namelist()
                      if member.endswith(".dist-info/METADATA")
                      and member.count("/") == 1
                  ]
                  if len(members) != 1:
                      raise SystemExit(
                          f"{wheel.name}: no unique .dist-info/METADATA member"
                      )
                  wheel.with_name(wheel.name + ".metadata").write_bytes(
                      archive.read(members[0])
                  )
                  print(f"extracted {wheel.name}.metadata")
          EOF
```

The existing "Upload artifact signatures to GitHub Release" step's `dist/**` glob then uploads the `.metadata` files with no change; sigstore's explicit `*.whl`/`*.tar.gz` inputs remain metadata-free.

- [ ] **Step 2: Local script verification.** Run the heredoc body locally against this repo's own wheel: `uv build` (writes `dist/`), run the script, then verify `dist/*.whl.metadata` is byte-equal to the wheel's METADATA member (`python3 -c` with zipfile read + filecmp/read_bytes comparison). Clean up `dist/` afterward (`git clean -n dist` first to confirm it's untracked build output — `dist/` is gitignored).

- [ ] **Step 3: README.** In the "Dependency metadata (PEP 658)" section's link-mode bullet, after the warning example, add:

```markdown
  To publish metadata assets from your release workflow, extract each
  wheel's `METADATA` and upload it next to the wheel (see the
  "Extract PEP 658 metadata from wheels" step in
  [`release.yml`](.github/workflows/release.yml) for the full version):

      - name: Extract PEP 658 metadata
        run: |
          python3 -c "
          import pathlib, zipfile
          for w in pathlib.Path('dist').glob('*.whl'):
              m = [n for n in zipfile.ZipFile(w).namelist()
                   if n.endswith('.dist-info/METADATA') and n.count('/') == 1]
              w.with_name(w.name + '.metadata').write_bytes(
                  zipfile.ZipFile(w).read(m[0]))
          "
      - run: gh release upload "$TAG" dist/*.whl.metadata
```

(indented code block inside the bullet, consistent with the section's existing warning example.)

- [ ] **Step 4: Changelog** bullet under the current entry:

```rst
* Release workflow publishes each wheel's PEP 658 ``.metadata`` as a
  release asset.
```

- [ ] **Step 5: Gate.** YAML parse (`uv run --no-sync python -c "import yaml; yaml.safe_load(open('.github/workflows/release.yml'))"`); `uvx zizmor --no-online-audits .github/workflows` (no new findings); `just fix`; `just test` (127 — unchanged); `just check-all` → exit 0 (real).

*(Driver checkpoint: commit as "Publish PEP 658 metadata assets with releases")*
