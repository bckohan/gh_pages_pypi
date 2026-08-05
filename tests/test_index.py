from github_releases_pypi import index

FIXTURE_RELEASES = [
    {
        "tag_name": "demo-lib-v1.0.0",
        "assets": [
            {
                "name": "github_releases_pypi_demo_lib-1.0.0-py3-none-any.whl",
                "browser_download_url": "https://github.com/bckohan/github-releases-pypi/releases/download/demo-lib-v1.0.0/github_releases_pypi_demo_lib-1.0.0-py3-none-any.whl",
            },
            {
                "name": "github_releases_pypi_demo_lib-1.0.0.tar.gz",
                "browser_download_url": "https://github.com/bckohan/github-releases-pypi/releases/download/demo-lib-v1.0.0/github_releases_pypi_demo_lib-1.0.0.tar.gz",
            },
            {
                "name": "release-notes.txt",
                "browser_download_url": "https://github.com/bckohan/github-releases-pypi/releases/download/demo-lib-v1.0.0/release-notes.txt",
            },
        ],
    },
    {
        "tag_name": "demo-app-v1.0.0",
        "assets": [
            {
                "name": "github_releases_pypi_demo_app-1.0.0-py3-none-any.whl",
                "browser_download_url": "https://github.com/bckohan/github-releases-pypi/releases/download/demo-app-v1.0.0/github_releases_pypi_demo_app-1.0.0-py3-none-any.whl",
            },
        ],
    },
    {
        "tag_name": "demo-lib-v2.0.0",
        "draft": True,
        "assets": [
            {
                "name": "github_releases_pypi_demo_lib-2.0.0-py3-none-any.whl",
                "browser_download_url": "https://github.com/bckohan/github-releases-pypi/releases/download/demo-lib-v2.0.0/github_releases_pypi_demo_lib-2.0.0-py3-none-any.whl",
            },
        ],
    },
]


def fake_hash(url):
    return "cafef00d"


def test_normalize():
    assert index.normalize("GitHub_Releases.PyPI--Demo") == "github-releases-pypi-demo"


def test_project_name_from_filename():
    assert (
        index.project_name_from_filename(
            "github_releases_pypi_demo_lib-1.0.0-py3-none-any.whl"
        )
        == "github_releases_pypi_demo_lib"
    )
    assert (
        index.project_name_from_filename("github_releases_pypi_demo_lib-1.0.0.tar.gz")
        == "github_releases_pypi_demo_lib"
    )
    assert index.project_name_from_filename("release-notes.txt") is None


def test_collect_projects():
    projects = index.collect_projects(FIXTURE_RELEASES, hash_url=fake_hash)
    assert sorted(projects) == [
        "github-releases-pypi-demo-app",
        "github-releases-pypi-demo-lib",
    ]
    lib_files = projects["github-releases-pypi-demo-lib"]
    assert [f["filename"] for f in lib_files] == [
        "github_releases_pypi_demo_lib-1.0.0-py3-none-any.whl",
        "github_releases_pypi_demo_lib-1.0.0.tar.gz",
    ]
    assert all(f["sha256"] == "cafef00d" for f in lib_files)


def test_write_site(tmp_path):
    projects = index.collect_projects(FIXTURE_RELEASES, hash_url=fake_hash)
    index.write_site(projects, tmp_path, "bckohan/github-releases-pypi")

    landing = (tmp_path / "index.html").read_text()
    assert "https://bckohan.github.io/github-releases-pypi/simple/" in landing

    root = (tmp_path / "simple" / "index.html").read_text()
    assert '<a href="github-releases-pypi-demo-lib/">' in root
    assert '<a href="github-releases-pypi-demo-app/">' in root

    lib_page = (
        tmp_path / "simple" / "github-releases-pypi-demo-lib" / "index.html"
    ).read_text()
    assert "#sha256=cafef00d" in lib_page
    assert "github_releases_pypi_demo_lib-1.0.0-py3-none-any.whl</a>" in lib_page
    assert '<meta name="pypi:repository-version" content="1.0"' in lib_page
