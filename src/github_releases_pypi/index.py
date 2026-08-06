"""Build a PEP 503 "simple" package index from GitHub release assets.

Lists every release in a GitHub repository, collects the ``.whl`` and
``.tar.gz`` assets, and writes a static PyPI-compatible index that GitHub
Pages can serve. Links point at the release assets' download URLs and, when a
hash is available, carry ``#sha256=`` fragments so pip verifies the download.
"""

import hashlib
import json
import re
import sys
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any, TypedDict

from jinja2 import (
    ChoiceLoader,
    Environment,
    FileSystemLoader,
    PackageLoader,
    PrefixLoader,
    select_autoescape,
)
from packaging.version import InvalidVersion, Version

from github_releases_pypi.config import Formats, MissingDigest

API_ROOT = "https://api.github.com"


class FileEntry(TypedDict):
    """A release asset file with download URL, hash, and metadata.

    ``sha256`` is the hash, or None when unavailable and the policy allows it.
    ``size`` comes from the GitHub asset API, 0 when unknown. ``upload_time``
    is the asset's RFC 3339 ``created_at``, None when unknown.
    """

    filename: str
    url: str
    sha256: str | None
    size: int
    upload_time: str | None


Projects = dict[str, list[FileEntry]]


def build_env(templates_dir: Path | None = None) -> Environment:
    """Return the Jinja environment, checking ``templates_dir`` first.

    Built-in templates stay reachable under a ``builtin/`` prefix so an
    override can ``{% extends "builtin/landing.html" %}`` without recursing
    into itself.
    """
    builtin = PackageLoader("github_releases_pypi")
    loaders: list = []
    if templates_dir is not None:
        loaders.append(FileSystemLoader(templates_dir))
    loaders += [PrefixLoader({"builtin": builtin}), builtin]
    return Environment(
        loader=ChoiceLoader(loaders),
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
    releases: list[dict[str, Any]],
    hash_url: Callable[[str], str] = hash_url,
    missing_digest: MissingDigest = "download",
) -> Projects:
    """Map normalized project names to their release files.

    Returns ``{project: [{"filename", "url", "sha256"}, ...]}`` sorted by
    project name and filename. Assets that are not wheels or sdists are
    ignored, as are draft releases (their assets aren't publicly
    downloadable). Duplicate filenames across releases are indexed once
    (first occurrence wins) with a stderr warning.

    Assets carrying an API ``digest`` are never downloaded; ``missing_digest``
    governs the rest: ``download`` (hash them), ``no-fragment`` (index without
    a hash), ``omit`` (exclude with a warning).
    """
    projects: Projects = {}
    seen: set[str] = set()
    for release in releases:
        if release.get("draft"):
            continue
        for asset in release.get("assets", []):
            project = project_name_from_filename(asset["name"])
            if project is None:
                continue
            if asset["name"] in seen:
                print(
                    f"warning: duplicate asset {asset['name']} ignored "
                    f"({asset['browser_download_url']})",
                    file=sys.stderr,
                )
                continue
            seen.add(asset["name"])
            digest = asset.get("digest")
            sha256: str | None
            if (
                isinstance(digest, str)
                and digest.startswith("sha256:")
                and digest[len("sha256:") :]
            ):
                sha256 = digest[len("sha256:") :]
            elif missing_digest == "no-fragment":
                sha256 = None
            elif missing_digest == "omit":
                print(
                    f"warning: {asset['name']} has no digest, omitted "
                    "(missing_digest=omit)",
                    file=sys.stderr,
                )
                continue
            else:
                sha256 = hash_url(asset["browser_download_url"])
            projects.setdefault(normalize(project), []).append(
                {
                    "filename": asset["name"],
                    "url": asset["browser_download_url"],
                    "sha256": sha256,
                    "size": int(asset.get("size") or 0),
                    "upload_time": asset.get("created_at"),
                }
            )
    for files in projects.values():
        files.sort(key=lambda file: file["filename"])
    return dict(sorted(projects.items()))


def pages_url(repo: str) -> str:
    """Return the GitHub Pages base URL for the ``owner/name`` repository."""
    owner, name = repo.split("/", 1)
    return f"https://{owner.lower()}.github.io/{name}/"


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


def write_site(
    projects: Projects,
    out_dir: Path,
    *,
    title: str,
    index_url: str | None,
    templates_dir: Path | None = None,
    formats: tuple[Formats, ...] = ("html", "json"),
) -> None:
    """Write the landing page and PEP 503/691 simple index under ``out_dir``.

    ``formats`` selects the HTML tree, the JSON tree (api-version 1.1), or
    both; the landing page is written only when ``html`` is included.
    """
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
