#!/usr/bin/env python3
"""Generate a PEP 503 "simple" package index from GitHub release assets.

Lists every release in a GitHub repository, collects the ``.whl`` and
``.tar.gz`` assets, and writes a static PyPI-compatible index that GitHub
Pages can serve. Links point at the release assets' download URLs and carry
``#sha256=`` fragments so pip verifies every download.

Usage::

    build_index.py --repo OWNER/NAME --out DIR [--token TOKEN]

The token defaults to the ``GITHUB_TOKEN`` environment variable.
"""

import argparse
import hashlib
import html
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

API_ROOT = "https://api.github.com"

LANDING_PAGE = """<!DOCTYPE html>
<html>
  <head>
    <meta charset="utf-8">
    <title>{repo} package index</title>
  </head>
  <body>
    <h1>{repo} package index</h1>
    <p>A PyPI-compatible (PEP 503) package index served by GitHub Pages.
       Packages are hosted as GitHub release assets.</p>
    <p>Install packages with:</p>
    <pre>pip install --extra-index-url {index_url} PACKAGE</pre>
    <p>Available packages:</p>
    <ul>
{projects}
    </ul>
    <p><a href="simple/">Browse the simple index</a></p>
  </body>
</html>
"""

ROOT_PAGE = """<!DOCTYPE html>
<html>
  <head>
    <meta name="pypi:repository-version" content="1.0">
    <title>Simple index</title>
  </head>
  <body>
{anchors}
  </body>
</html>
"""

PROJECT_PAGE = """<!DOCTYPE html>
<html>
  <head>
    <meta name="pypi:repository-version" content="1.0">
    <title>Links for {project}</title>
  </head>
  <body>
    <h1>Links for {project}</h1>
{anchors}
  </body>
</html>
"""


def normalize(name):
    """Normalize a project name per PEP 503."""
    return re.sub(r"[-_.]+", "-", name).lower()


def project_name_from_filename(filename):
    """Return the project name for a wheel or sdist filename, else None."""
    if filename.endswith(".whl"):
        return filename.split("-")[0]
    if filename.endswith(".tar.gz"):
        return filename[: -len(".tar.gz")].rsplit("-", 1)[0]
    return None


def fetch_releases(repo, token):
    """Return the JSON list of releases for the ``owner/name`` repository."""
    request = urllib.request.Request(
        f"{API_ROOT}/repos/{repo}/releases?per_page=100",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
        },
    )
    with urllib.request.urlopen(request) as response:
        return json.load(response)


def hash_url(url):
    """Download ``url`` and return the sha256 hex digest of its content."""
    digest = hashlib.sha256()
    with urllib.request.urlopen(url) as response:
        for chunk in iter(lambda: response.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def collect_projects(releases, hash_url=hash_url):
    """Map normalized project names to their release files.

    Returns ``{project: [{"filename", "url", "sha256"}, ...]}`` sorted by
    project name and filename. Assets that are not wheels or sdists are
    ignored.
    """
    projects = {}
    for release in releases:
        if release.get("draft"):  # draft assets aren't publicly downloadable
            continue
        for asset in release.get("assets", []):
            project = project_name_from_filename(asset["name"])
            if project is None:
                continue
            projects.setdefault(normalize(project), []).append(
                {
                    "filename": asset["name"],
                    "url": asset["browser_download_url"],
                    "sha256": hash_url(asset["browser_download_url"]),
                }
            )
    for files in projects.values():
        files.sort(key=lambda file: file["filename"])
    return dict(sorted(projects.items()))


def pages_url(repo):
    """Return the GitHub Pages base URL for the ``owner/name`` repository."""
    owner, name = repo.split("/", 1)
    return f"https://{owner.lower()}.github.io/{name}/"


def write_site(projects, out_dir, repo):
    """Write the landing page and PEP 503 simple index under ``out_dir``."""
    simple = out_dir / "simple"
    simple.mkdir(parents=True, exist_ok=True)
    for project, files in projects.items():
        anchors = "\n".join(
            '    <a href="{url}#sha256={sha}">{filename}</a><br/>'.format(
                url=html.escape(file["url"]),
                sha=file["sha256"],
                filename=html.escape(file["filename"]),
            )
            for file in files
        )
        project_dir = simple / project
        project_dir.mkdir(parents=True, exist_ok=True)
        (project_dir / "index.html").write_text(
            PROJECT_PAGE.format(project=html.escape(project), anchors=anchors)
        )
    root_anchors = "\n".join(
        f'    <a href="{project}/">{project}</a><br/>' for project in projects
    )
    (simple / "index.html").write_text(ROOT_PAGE.format(anchors=root_anchors))
    project_items = "\n".join(
        f"      <li><code>{project}</code></li>" for project in projects
    )
    (out_dir / "index.html").write_text(
        LANDING_PAGE.format(
            repo=html.escape(repo),
            index_url=pages_url(repo) + "simple/",
            projects=project_items,
        )
    )


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Generate a PEP 503 index from GitHub release assets."
    )
    parser.add_argument("--repo", required=True, help="repository as owner/name")
    parser.add_argument("--out", required=True, help="output directory")
    parser.add_argument(
        "--token",
        default=os.environ.get("GITHUB_TOKEN"),
        help="GitHub API token (defaults to $GITHUB_TOKEN)",
    )
    args = parser.parse_args(argv)
    if not args.token:
        sys.exit("error: provide --token or set GITHUB_TOKEN")

    try:
        releases = fetch_releases(args.repo, args.token)
    except urllib.error.URLError as error:
        sys.exit(f"error: GitHub API request for {args.repo} failed: {error}")
    projects = collect_projects(releases)
    if not projects:
        sys.exit(
            f"error: no package assets found in releases of {args.repo}; "
            "refusing to build an empty index"
        )
    write_site(projects, Path(args.out), args.repo)
    print(f"wrote index for {len(projects)} project(s) to {args.out}")


if __name__ == "__main__":
    main()
