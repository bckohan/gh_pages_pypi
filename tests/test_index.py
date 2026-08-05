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


def test_collect_projects_dedupes_duplicate_filenames(capsys):
    duplicate = {
        "tag_name": "mirror-v1.0.0",
        "assets": [
            {
                "name": "github_releases_pypi_demo_lib-1.0.0-py3-none-any.whl",
                "browser_download_url": "https://github.com/other/mirror/releases/download/v1/github_releases_pypi_demo_lib-1.0.0-py3-none-any.whl",
            },
        ],
    }
    hashed = []

    def counting_hash(url):
        hashed.append(url)
        return "cafef00d"

    projects = index.collect_projects(
        FIXTURE_RELEASES + [duplicate], hash_url=counting_hash
    )
    lib_files = projects["github-releases-pypi-demo-lib"]
    whl = [f for f in lib_files if f["filename"].endswith(".whl")]
    assert len(whl) == 1
    assert "bckohan/github-releases-pypi" in whl[0]["url"]  # first occurrence won
    assert not any("other/mirror" in url for url in hashed)  # duplicate never hashed
    assert (
        "duplicate asset github_releases_pypi_demo_lib-1.0.0-py3-none-any.whl"
        in capsys.readouterr().err
    )


def test_write_site(tmp_path):
    projects = index.collect_projects(FIXTURE_RELEASES, hash_url=fake_hash)
    index.write_site(
        projects,
        tmp_path,
        title="bckohan/github-releases-pypi package index",
        index_url="https://bckohan.github.io/github-releases-pypi/simple/",
    )

    landing = (tmp_path / "index.html").read_text()
    assert "https://bckohan.github.io/github-releases-pypi/simple/" in landing
    assert "bckohan/github-releases-pypi package index" in landing

    root = (tmp_path / "simple" / "index.html").read_text()
    assert '<a href="github-releases-pypi-demo-lib/">' in root
    assert '<a href="github-releases-pypi-demo-app/">' in root

    lib_page = (
        tmp_path / "simple" / "github-releases-pypi-demo-lib" / "index.html"
    ).read_text()
    assert "#sha256=cafef00d" in lib_page
    assert "github_releases_pypi_demo_lib-1.0.0-py3-none-any.whl</a>" in lib_page
    assert '<meta name="pypi:repository-version" content="1.0"' in lib_page


def test_write_site_without_index_url(tmp_path):
    projects = index.collect_projects(FIXTURE_RELEASES, hash_url=fake_hash)
    index.write_site(projects, tmp_path, title="An index", index_url=None)
    landing = (tmp_path / "index.html").read_text()
    assert "--extra-index-url" not in landing
    assert '<a href="simple/">' in landing


def test_write_site_template_override(tmp_path):
    overrides = tmp_path / "tpl"
    overrides.mkdir()
    (overrides / "landing.html").write_text("<html>custom landing</html>\n")
    projects = index.collect_projects(FIXTURE_RELEASES, hash_url=fake_hash)
    index.write_site(
        projects,
        tmp_path / "site",
        title="T",
        index_url=None,
        templates_dir=overrides,
    )
    assert (
        tmp_path / "site" / "index.html"
    ).read_text() == "<html>custom landing</html>\n"
    # other templates still fall back to the built-ins
    root = (tmp_path / "site" / "simple" / "index.html").read_text()
    assert '<meta name="pypi:repository-version" content="1.0"' in root


def test_write_site_block_extension(tmp_path):
    overrides = tmp_path / "tpl"
    overrides.mkdir()
    (overrides / "landing.html").write_text(
        '{% extends "builtin/landing.html" %}'
        "{% block footer %}<footer>custom footer</footer>{% endblock %}"
    )
    projects = index.collect_projects(FIXTURE_RELEASES, hash_url=fake_hash)
    index.write_site(
        projects,
        tmp_path / "site",
        title="Extended",
        index_url=None,
        templates_dir=overrides,
    )
    landing = (tmp_path / "site" / "index.html").read_text()
    assert "<footer>custom footer</footer>" in landing
    assert "Available packages:" in landing  # built-in content block retained
