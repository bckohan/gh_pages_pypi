"""Build a PEP 503 "simple" package index from GitHub release assets.

Lists every release in a GitHub repository, collects the ``.whl`` and
``.tar.gz`` assets, and writes a static PyPI-compatible index that GitHub
Pages can serve. Links point at the release assets' download URLs and carry
``#sha256=`` fragments so pip verifies every download.
"""

import hashlib
import json
import re
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any, TypedDict

from jinja2 import Environment, PackageLoader, select_autoescape

API_ROOT = "https://api.github.com"


class FileEntry(TypedDict):
    """A release asset file with download URL and hash."""

    filename: str
    url: str
    sha256: str


Projects = dict[str, list[FileEntry]]

_env = Environment(
    loader=PackageLoader("gh_pages_pypi"),
    autoescape=select_autoescape(("html",)),
    keep_trailing_newline=True,
)


def normalize(name: str) -> str:
    """Normalize a project name per PEP 503."""
    return re.sub(r"[-_.]+", "-", name).lower()


def project_name_from_filename(filename: str) -> str | None:
    """Return the project name for a wheel or sdist filename, else None."""
    if filename.endswith(".whl"):
        return filename.split("-")[0]
    if filename.endswith(".tar.gz"):
        return filename[: -len(".tar.gz")].rsplit("-", 1)[0]
    return None


def fetch_releases(repo: str, token: str) -> list[dict[str, Any]]:
    """Return the JSON list of releases for the ``owner/name`` repository."""
    request = urllib.request.Request(
        f"{API_ROOT}/repos/{repo}/releases?per_page=100",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
        },
    )
    with urllib.request.urlopen(  # nosec B310 — https URL built from constant API_ROOT
        request, timeout=30
    ) as response:
        return json.load(response)


def hash_url(url: str) -> str:
    """Download ``url`` and return the sha256 hex digest of its content."""
    if not url.startswith("https://"):
        raise ValueError(f"refusing to fetch non-https URL: {url}")
    digest = hashlib.sha256()
    with urllib.request.urlopen(  # nosec B310 — scheme validated above
        url, timeout=30
    ) as response:
        for chunk in iter(lambda: response.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def collect_projects(
    releases: list[dict[str, Any]], hash_url: Callable[[str], str] = hash_url
) -> Projects:
    """Map normalized project names to their release files.

    Returns ``{project: [{"filename", "url", "sha256"}, ...]}`` sorted by
    project name and filename. Assets that are not wheels or sdists are
    ignored, as are draft releases (their assets aren't publicly
    downloadable).
    """
    projects: Projects = {}
    for release in releases:
        if release.get("draft"):
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


def pages_url(repo: str) -> str:
    """Return the GitHub Pages base URL for the ``owner/name`` repository."""
    owner, name = repo.split("/", 1)
    return f"https://{owner.lower()}.github.io/{name}/"


def write_site(projects: Projects, out_dir: Path, repo: str) -> None:
    """Write the landing page and PEP 503 simple index under ``out_dir``."""
    simple = out_dir / "simple"
    simple.mkdir(parents=True, exist_ok=True)
    project_page = _env.get_template("project.html")
    for project, files in projects.items():
        project_dir = simple / project
        project_dir.mkdir(parents=True, exist_ok=True)
        (project_dir / "index.html").write_text(
            project_page.render(project=project, files=files), encoding="utf-8"
        )
    (simple / "index.html").write_text(
        _env.get_template("simple_root.html").render(projects=projects),
        encoding="utf-8",
    )
    (out_dir / "index.html").write_text(
        _env.get_template("landing.html").render(
            repo=repo, index_url=pages_url(repo) + "simple/", projects=projects
        ),
        encoding="utf-8",
    )
