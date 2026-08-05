import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import build_index

FIXTURE_RELEASES = [
    {
        "tag_name": "demo-lib-v1.0.0",
        "assets": [
            {
                "name": "gh_pages_pypi_demo_lib-1.0.0-py3-none-any.whl",
                "browser_download_url": "https://github.com/bckohan/gh_pages_pypi/releases/download/demo-lib-v1.0.0/gh_pages_pypi_demo_lib-1.0.0-py3-none-any.whl",
            },
            {
                "name": "gh_pages_pypi_demo_lib-1.0.0.tar.gz",
                "browser_download_url": "https://github.com/bckohan/gh_pages_pypi/releases/download/demo-lib-v1.0.0/gh_pages_pypi_demo_lib-1.0.0.tar.gz",
            },
            {
                "name": "release-notes.txt",
                "browser_download_url": "https://github.com/bckohan/gh_pages_pypi/releases/download/demo-lib-v1.0.0/release-notes.txt",
            },
        ],
    },
    {
        "tag_name": "demo-app-v1.0.0",
        "assets": [
            {
                "name": "gh_pages_pypi_demo_app-1.0.0-py3-none-any.whl",
                "browser_download_url": "https://github.com/bckohan/gh_pages_pypi/releases/download/demo-app-v1.0.0/gh_pages_pypi_demo_app-1.0.0-py3-none-any.whl",
            },
        ],
    },
    {
        "tag_name": "demo-lib-v2.0.0",
        "draft": True,
        "assets": [
            {
                "name": "gh_pages_pypi_demo_lib-2.0.0-py3-none-any.whl",
                "browser_download_url": "https://github.com/bckohan/gh_pages_pypi/releases/download/demo-lib-v2.0.0/gh_pages_pypi_demo_lib-2.0.0-py3-none-any.whl",
            },
        ],
    },
]


def fake_hash(url):
    return "cafef00d"


def test_normalize():
    assert build_index.normalize("Gh_Pages.PyPI--Demo") == "gh-pages-pypi-demo"


def test_project_name_from_filename():
    assert (
        build_index.project_name_from_filename("gh_pages_pypi_demo_lib-1.0.0-py3-none-any.whl")
        == "gh_pages_pypi_demo_lib"
    )
    assert (
        build_index.project_name_from_filename("gh_pages_pypi_demo_lib-1.0.0.tar.gz")
        == "gh_pages_pypi_demo_lib"
    )
    assert build_index.project_name_from_filename("release-notes.txt") is None


def test_collect_projects():
    projects = build_index.collect_projects(FIXTURE_RELEASES, hash_url=fake_hash)
    assert sorted(projects) == ["gh-pages-pypi-demo-app", "gh-pages-pypi-demo-lib"]
    lib_files = projects["gh-pages-pypi-demo-lib"]
    assert [f["filename"] for f in lib_files] == [
        "gh_pages_pypi_demo_lib-1.0.0-py3-none-any.whl",
        "gh_pages_pypi_demo_lib-1.0.0.tar.gz",
    ]
    assert all(f["sha256"] == "cafef00d" for f in lib_files)


def test_write_site(tmp_path):
    projects = build_index.collect_projects(FIXTURE_RELEASES, hash_url=fake_hash)
    build_index.write_site(projects, tmp_path, "bckohan/gh_pages_pypi")

    landing = (tmp_path / "index.html").read_text()
    assert "https://bckohan.github.io/gh_pages_pypi/simple/" in landing

    root = (tmp_path / "simple" / "index.html").read_text()
    assert '<a href="gh-pages-pypi-demo-lib/">' in root
    assert '<a href="gh-pages-pypi-demo-app/">' in root

    lib_page = (tmp_path / "simple" / "gh-pages-pypi-demo-lib" / "index.html").read_text()
    assert "#sha256=cafef00d" in lib_page
    assert "gh_pages_pypi_demo_lib-1.0.0-py3-none-any.whl</a>" in lib_page


def test_main_fails_with_no_packages(tmp_path, monkeypatch):
    monkeypatch.setattr(build_index, "fetch_releases", lambda repo, token: [])
    with pytest.raises(SystemExit) as excinfo:
        build_index.main(
            ["--repo", "bckohan/gh_pages_pypi", "--out", str(tmp_path), "--token", "x"]
        )
    assert "no package assets" in str(excinfo.value)
