import hashlib
import io
import json
import zipfile

import pytest

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


def test_collect_projects_skips_unsafe_asset_names(capsys):
    release = {
        "tag_name": "v6.6.6",
        "assets": [
            {
                "name": "../../evil-1.0.0-py3-none-any.whl",
                "browser_download_url": "https://github.com/o/r/releases/download/v6.6.6/a",
            },
            {
                "name": "/abs/evil-1.0.0-py3-none-any.whl",
                "browser_download_url": "https://github.com/o/r/releases/download/v6.6.6/b",
            },
        ],
    }
    projects = index.collect_projects([release], hash_url=never_hash)
    assert projects == {}
    err = capsys.readouterr().err
    assert "unsafe name '../../evil-1.0.0-py3-none-any.whl'" in err
    assert "unsafe name '/abs/evil-1.0.0-py3-none-any.whl'" in err


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


DIGEST_RELEASE = [
    {
        "tag_name": "v9.0.0",
        "assets": [
            {
                "name": "digested-9.0.0-py3-none-any.whl",
                "browser_download_url": "https://github.com/o/r/releases/download/v9.0.0/digested-9.0.0-py3-none-any.whl",
                "digest": "sha256:feedbeef",
            },
            {
                "name": "legacy-9.0.0-py3-none-any.whl",
                "browser_download_url": "https://github.com/o/r/releases/download/v9.0.0/legacy-9.0.0-py3-none-any.whl",
            },
        ],
    },
]


def never_hash(url):
    raise AssertionError(f"hash_url called for {url}")


def test_digest_used_without_download():
    projects = index.collect_projects(
        [DIGEST_RELEASE[0] | {"assets": DIGEST_RELEASE[0]["assets"][:1]}],
        hash_url=never_hash,
    )
    assert projects["digested"][0]["sha256"] == "feedbeef"


def test_non_sha256_digest_falls_back_to_download():
    release = {
        "tag_name": "v9.0.1",
        "assets": [
            {
                "name": "oddhash-9.0.1-py3-none-any.whl",
                "browser_download_url": "https://github.com/o/r/releases/download/v9.0.1/oddhash-9.0.1-py3-none-any.whl",
                "digest": "blake2:abc123",
            },
        ],
    }
    projects = index.collect_projects([release], hash_url=fake_hash)
    assert projects["oddhash"][0]["sha256"] == "cafef00d"


def test_missing_digest_download_default():
    projects = index.collect_projects(DIGEST_RELEASE, hash_url=fake_hash)
    assert projects["legacy"][0]["sha256"] == "cafef00d"
    assert projects["digested"][0]["sha256"] == "feedbeef"


def test_missing_digest_no_fragment(tmp_path):
    projects = index.collect_projects(
        DIGEST_RELEASE, hash_url=never_hash, missing_digest="no-fragment"
    )
    assert projects["legacy"][0]["sha256"] is None
    index.write_site(projects, tmp_path, title="T", index_url=None)
    page = (tmp_path / "simple" / "legacy" / "index.html").read_text()
    assert "#sha256=" not in page
    assert "legacy-9.0.0-py3-none-any.whl</a>" in page
    digested_page = (tmp_path / "simple" / "digested" / "index.html").read_text()
    assert "#sha256=feedbeef" in digested_page


def test_missing_digest_omit(capsys):
    projects = index.collect_projects(
        DIGEST_RELEASE, hash_url=never_hash, missing_digest="omit"
    )
    assert "legacy" not in projects
    assert "digested" in projects
    err = capsys.readouterr().err
    assert "legacy-9.0.0-py3-none-any.whl has no digest, omitted" in err


def test_null_digest_treated_as_absent():
    # GitHub's API returns "digest": null for legacy assets — pin that wire
    # shape: an explicit None behaves exactly like a missing key.
    release = {
        "tag_name": "v9.0.3",
        "assets": [
            {
                "name": "nulldigest-9.0.3-py3-none-any.whl",
                "browser_download_url": "https://github.com/o/r/releases/download/v9.0.3/nulldigest-9.0.3-py3-none-any.whl",
                "digest": None,
            },
        ],
    }
    projects = index.collect_projects([release], hash_url=fake_hash)
    assert projects["nulldigest"][0]["sha256"] == "cafef00d"


def test_empty_sha256_digest_treated_as_absent(capsys):
    release = {
        "tag_name": "v9.0.2",
        "assets": [
            {
                "name": "emptyhash-9.0.2-py3-none-any.whl",
                "browser_download_url": "https://github.com/o/r/releases/download/v9.0.2/emptyhash-9.0.2-py3-none-any.whl",
                "digest": "sha256:",
            },
        ],
    }
    projects = index.collect_projects(
        [release], hash_url=never_hash, missing_digest="omit"
    )
    assert "emptyhash" not in projects
    err = capsys.readouterr().err
    assert "emptyhash-9.0.2-py3-none-any.whl has no digest, omitted" in err


def test_collect_projects_captures_api_url():
    release = {
        "tag_name": "v5.0.0",
        "assets": [
            {
                "name": "apiurl-5.0.0-py3-none-any.whl",
                "browser_download_url": "https://github.com/o/r/releases/download/v5.0.0/apiurl-5.0.0-py3-none-any.whl",
                "url": "https://api.github.com/repos/o/r/releases/assets/123",
                "digest": "sha256:beef",
            },
        ],
    }
    entry = index.collect_projects([release], hash_url=never_hash)["apiurl"][0]
    assert entry["api_url"] == "https://api.github.com/repos/o/r/releases/assets/123"


def test_collect_projects_api_url_defaults_to_empty():
    release = {
        "tag_name": "v5.0.1",
        "assets": [
            {
                "name": "nourl-5.0.1-py3-none-any.whl",
                "browser_download_url": "https://github.com/o/r/releases/download/v5.0.1/nourl-5.0.1-py3-none-any.whl",
                "digest": "sha256:beef",
            },
        ],
    }
    entry = index.collect_projects([release], hash_url=never_hash)["nourl"][0]
    assert entry["api_url"] == ""


def test_collect_projects_defer_hash():
    projects = index.collect_projects(
        DIGEST_RELEASE, hash_url=never_hash, defer_hash=True
    )
    assert projects["digested"][0]["sha256"] == "feedbeef"
    assert projects["legacy"][0]["sha256"] is None


def test_collect_projects_defer_hash_ignores_policy():
    projects = index.collect_projects(
        DIGEST_RELEASE, hash_url=never_hash, defer_hash=True, missing_digest="omit"
    )
    assert "legacy" in projects  # omit does not apply under defer_hash


def make_opener(payload=b"wheel-bytes", requests_log=None):
    def opener(request, timeout=None):
        if requests_log is not None:
            requests_log.append(request)
        return io.BytesIO(payload)

    return opener


MIRROR_RELEASE = [
    {
        "tag_name": "v7.0.0",
        "assets": [
            {
                "name": "mirrored-7.0.0-py3-none-any.whl",
                "browser_download_url": "https://github.com/o/r/releases/download/v7.0.0/mirrored-7.0.0-py3-none-any.whl",
                "url": "https://api.github.com/repos/o/r/releases/assets/7",
            },
        ],
    },
]


def mirror_projects():
    return index.collect_projects(MIRROR_RELEASE, hash_url=never_hash, defer_hash=True)


def test_mirror_files_downloads_and_relinks(tmp_path):
    projects = mirror_projects()
    log = []
    index.mirror_files(projects, tmp_path, "tok", opener=make_opener(requests_log=log))
    entry = projects["mirrored"][0]
    dest = tmp_path / "files" / "mirrored" / "mirrored-7.0.0-py3-none-any.whl"
    assert dest.read_bytes() == b"wheel-bytes"
    assert entry["sha256"] == hashlib.sha256(b"wheel-bytes").hexdigest()
    assert entry["url"] == "../../files/mirrored/mirrored-7.0.0-py3-none-any.whl"
    assert len(log) == 1
    assert log[0].get_full_url() == "https://api.github.com/repos/o/r/releases/assets/7"
    assert log[0].get_header("Accept") == "application/octet-stream"
    assert log[0].get_header("Authorization") == "Bearer tok"


def test_mirror_files_reuses_matching_existing(tmp_path):
    projects = mirror_projects()
    dest = tmp_path / "files" / "mirrored" / "mirrored-7.0.0-py3-none-any.whl"
    dest.parent.mkdir(parents=True)
    dest.write_bytes(b"already-here")
    projects["mirrored"][0]["sha256"] = hashlib.sha256(b"already-here").hexdigest()
    log = []
    index.mirror_files(projects, tmp_path, "tok", opener=make_opener(requests_log=log))
    assert log == []  # no download
    assert dest.read_bytes() == b"already-here"


def test_mirror_files_adopts_existing_hash(tmp_path):
    projects = mirror_projects()  # sha256 is None (no digest)
    dest = tmp_path / "files" / "mirrored" / "mirrored-7.0.0-py3-none-any.whl"
    dest.parent.mkdir(parents=True)
    dest.write_bytes(b"already-here")
    log = []
    index.mirror_files(projects, tmp_path, "tok", opener=make_opener(requests_log=log))
    assert log == []
    assert (
        projects["mirrored"][0]["sha256"] == hashlib.sha256(b"already-here").hexdigest()
    )


def test_mirror_files_redownloads_corrupted(tmp_path):
    projects = mirror_projects()
    dest = tmp_path / "files" / "mirrored" / "mirrored-7.0.0-py3-none-any.whl"
    dest.parent.mkdir(parents=True)
    dest.write_bytes(b"corrupted")
    projects["mirrored"][0]["sha256"] = hashlib.sha256(b"wheel-bytes").hexdigest()
    log = []
    index.mirror_files(projects, tmp_path, "tok", opener=make_opener(requests_log=log))
    assert len(log) == 1
    assert dest.read_bytes() == b"wheel-bytes"


def test_mirror_files_digest_mismatch(tmp_path):
    projects = mirror_projects()
    projects["mirrored"][0]["sha256"] = "deadbeef"  # advertised digest, wrong
    with pytest.raises(index.MirrorError, match="mirrored-7.0.0-py3-none-any.whl"):
        index.mirror_files(projects, tmp_path, "tok", opener=make_opener())
    assert not (
        tmp_path / "files" / "mirrored" / "mirrored-7.0.0-py3-none-any.whl"
    ).exists()


def test_mirror_files_rejects_non_https(tmp_path):
    projects = mirror_projects()
    projects["mirrored"][0]["api_url"] = "http://api.github.com/insecure"
    with pytest.raises(index.MirrorError, match="non-https"):
        index.mirror_files(projects, tmp_path, "tok", opener=make_opener())


def test_mirror_files_missing_api_url(tmp_path):
    projects = mirror_projects()
    projects["mirrored"][0]["api_url"] = ""
    with pytest.raises(index.MirrorError, match="no API download URL"):
        index.mirror_files(projects, tmp_path, "tok", opener=make_opener())


def test_mirror_files_rejects_unsafe_filename(tmp_path):
    projects = mirror_projects()
    projects["mirrored"][0]["filename"] = "../escape-1.0.0-py3-none-any.whl"
    with pytest.raises(index.MirrorError, match="unsafe path"):
        index.mirror_files(projects, tmp_path, "tok", opener=make_opener())


def test_mirror_files_rejects_unsafe_project_key(tmp_path):
    site = tmp_path / "site"
    for hostile_key in ("../../esc", str(tmp_path / "abs-esc")):
        projects = {hostile_key: [mirror_projects()["mirrored"][0]]}
        with pytest.raises(index.MirrorError, match="unsafe path"):
            index.mirror_files(projects, site, "tok", opener=make_opener())
    # nothing was written anywhere — inside the site or beside it
    assert list(tmp_path.iterdir()) == []


def test_mirror_files_midstream_failure_preserves_cache(tmp_path):
    projects = mirror_projects()
    dest = tmp_path / "files" / "mirrored" / "mirrored-7.0.0-py3-none-any.whl"
    dest.parent.mkdir(parents=True)
    dest.write_bytes(b"cached-good")
    # expected hash matches neither the cache nor the stream → re-download
    projects["mirrored"][0]["sha256"] = hashlib.sha256(b"wheel-bytes").hexdigest()

    class ExplodingResponse:
        def __init__(self):
            self.calls = 0

        def read(self, size):
            self.calls += 1
            if self.calls > 1:
                raise OSError("connection reset")
            return b"first-chunk"

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    with pytest.raises(OSError, match="connection reset"):
        index.mirror_files(
            projects,
            tmp_path,
            "tok",
            opener=lambda request, timeout=None: ExplodingResponse(),
        )
    assert dest.read_bytes() == b"cached-good"  # cached copy untouched
    assert not dest.with_name(dest.name + ".part").exists()


def test_mirror_files_truncated_download(tmp_path):
    projects = mirror_projects()

    class TruncatedResponse(io.BytesIO):
        headers = {"Content-Length": "999"}

    with pytest.raises(index.MirrorError, match="truncated"):
        index.mirror_files(
            projects,
            tmp_path,
            "tok",
            opener=lambda request, timeout=None: TruncatedResponse(b"short"),
        )
    dest = tmp_path / "files" / "mirrored" / "mirrored-7.0.0-py3-none-any.whl"
    assert not dest.exists()
    assert not dest.with_name(dest.name + ".part").exists()


def test_write_site_after_mirror(tmp_path):
    projects = mirror_projects()
    index.mirror_files(projects, tmp_path, "tok", opener=make_opener())
    index.write_site(projects, tmp_path, title="T", index_url=None)
    page = (tmp_path / "simple" / "mirrored" / "index.html").read_text()
    assert 'href="../../files/mirrored/mirrored-7.0.0-py3-none-any.whl#sha256=' in page
    data = json.loads((tmp_path / "simple" / "mirrored" / "index.json").read_text())
    assert (
        data["files"][0]["url"]
        == "../../files/mirrored/mirrored-7.0.0-py3-none-any.whl"
    )


def test_version_from_filename():
    assert index.version_from_filename("demo_lib-1.0.0-py3-none-any.whl") == "1.0.0"
    assert index.version_from_filename("demo_lib-1.0.0.tar.gz") == "1.0.0"
    assert index.version_from_filename("demo-lib-2.0rc1.tar.gz") == "2.0rc1"
    assert index.version_from_filename("release-notes.txt") is None
    assert index.version_from_filename("noversion.whl") is None
    assert index.version_from_filename("noversion.tar.gz") is None
    assert index.version_from_filename("foo-1.0-1-py3-none-any.whl") == "1.0"


def test_collect_projects_captures_size_and_upload_time():
    release = {
        "tag_name": "v3.0.0",
        "assets": [
            {
                "name": "sized-3.0.0-py3-none-any.whl",
                "browser_download_url": "https://github.com/o/r/releases/download/v3.0.0/sized-3.0.0-py3-none-any.whl",
                "digest": "sha256:beef",
                "size": 4321,
                "created_at": "2026-08-05T03:07:33Z",
            },
        ],
    }
    entry = index.collect_projects([release], hash_url=never_hash)["sized"][0]
    assert entry["size"] == 4321
    assert entry["upload_time"] == "2026-08-05T03:07:33Z"


def test_collect_projects_defaults_size_and_upload_time():
    entry = index.collect_projects(FIXTURE_RELEASES, hash_url=fake_hash)[
        "github-releases-pypi-demo-lib"
    ][0]
    assert entry["size"] == 0
    assert entry["upload_time"] is None


def test_write_site_json_project_page(tmp_path):
    projects = index.collect_projects(FIXTURE_RELEASES, hash_url=fake_hash)
    index.write_site(projects, tmp_path, title="T", index_url=None)
    data = json.loads(
        (
            tmp_path / "simple" / "github-releases-pypi-demo-lib" / "index.json"
        ).read_text()
    )
    assert data["meta"] == {"api-version": "1.1"}
    assert data["name"] == "github-releases-pypi-demo-lib"
    assert data["versions"] == ["1.0.0"]
    files = {f["filename"]: f for f in data["files"]}
    whl = files["github_releases_pypi_demo_lib-1.0.0-py3-none-any.whl"]
    assert whl["hashes"] == {"sha256": "cafef00d"}
    assert whl["size"] == 0
    assert "upload-time" not in whl
    assert "api_url" not in whl


def test_write_site_json_root(tmp_path):
    projects = index.collect_projects(FIXTURE_RELEASES, hash_url=fake_hash)
    index.write_site(projects, tmp_path, title="T", index_url=None)
    data = json.loads((tmp_path / "simple" / "index.json").read_text())
    assert data["meta"] == {"api-version": "1.1"}
    assert {"name": "github-releases-pypi-demo-lib"} in data["projects"]
    assert {"name": "github-releases-pypi-demo-app"} in data["projects"]


def test_write_site_json_empty_hashes_and_upload_time(tmp_path):
    projects = index.collect_projects(
        DIGEST_RELEASE, hash_url=never_hash, missing_digest="no-fragment"
    )
    index.write_site(projects, tmp_path, title="T", index_url=None)
    data = json.loads((tmp_path / "simple" / "legacy" / "index.json").read_text())
    assert data["files"][0]["hashes"] == {}
    assert "upload-time" not in data["files"][0]


def test_write_site_formats_html_only(tmp_path):
    projects = index.collect_projects(FIXTURE_RELEASES, hash_url=fake_hash)
    index.write_site(projects, tmp_path, title="T", index_url=None, formats=("html",))
    assert not list(tmp_path.rglob("*.json"))
    assert (tmp_path / "index.html").exists()
    assert (tmp_path / "simple" / "index.html").exists()


METADATA_RELEASE = [
    {
        "tag_name": "v8.0.0",
        "_source_repo": "o/meta",
        "assets": [
            {
                "name": "hasmeta-8.0.0-py3-none-any.whl",
                "browser_download_url": "https://github.com/o/meta/releases/download/v8.0.0/hasmeta-8.0.0-py3-none-any.whl",
                "digest": "sha256:aaaa",
            },
            {
                "name": "hasmeta-8.0.0-py3-none-any.whl.metadata",
                "browser_download_url": "https://github.com/o/meta/releases/download/v8.0.0/hasmeta-8.0.0-py3-none-any.whl.metadata",
                "digest": "sha256:bbbb",
            },
            {
                "name": "nudemeta-8.0.0-py3-none-any.whl",
                "browser_download_url": "https://github.com/o/meta/releases/download/v8.0.0/nudemeta-8.0.0-py3-none-any.whl",
                "digest": "sha256:cccc",
            },
            {
                "name": "nudemeta-8.0.0-py3-none-any.whl.metadata",
                "browser_download_url": "https://github.com/o/meta/releases/download/v8.0.0/nudemeta-8.0.0-py3-none-any.whl.metadata",
            },
            {
                "name": "nometa-8.0.0-py3-none-any.whl",
                "browser_download_url": "https://github.com/o/meta/releases/download/v8.0.0/nometa-8.0.0-py3-none-any.whl",
                "digest": "sha256:dddd",
            },
            {
                "name": "withmeta-8.0.0.tar.gz",
                "browser_download_url": "https://github.com/o/meta/releases/download/v8.0.0/withmeta-8.0.0.tar.gz",
                "digest": "sha256:eeee",
            },
            {
                "name": "withmeta-8.0.0.tar.gz.metadata",
                "browser_download_url": "https://github.com/o/meta/releases/download/v8.0.0/withmeta-8.0.0.tar.gz.metadata",
                "digest": "sha256:ffff",
            },
        ],
    },
]


def test_collect_projects_pairs_metadata_assets():
    projects = index.collect_projects(METADATA_RELEASE, hash_url=never_hash)
    assert projects["hasmeta"][0]["core_metadata"] == "bbbb"
    assert projects["nudemeta"][0]["core_metadata"] is True
    assert projects["nometa"][0]["core_metadata"] is False
    assert projects["withmeta"][0]["core_metadata"] is False  # sdists excluded


def test_collect_projects_source_repo():
    projects = index.collect_projects(METADATA_RELEASE, hash_url=never_hash)
    assert projects["hasmeta"][0]["source_repo"] == "o/meta"
    untagged = index.collect_projects(FIXTURE_RELEASES, hash_url=fake_hash)
    assert untagged["github-releases-pypi-demo-lib"][0]["source_repo"] == ""


def test_collect_projects_metadata_disabled():
    projects = index.collect_projects(
        METADATA_RELEASE, hash_url=never_hash, metadata=False
    )
    # even the digest-bearing pair is ignored — nothing is advertised
    assert projects["hasmeta"][0]["core_metadata"] is False
    assert all(
        entry["core_metadata"] is False
        for files in projects.values()
        for entry in files
    )


def test_collect_projects_unsafe_metadata_asset_not_paired(capsys):
    release = {
        "tag_name": "v8.0.1",
        "assets": [
            {
                "name": "victim-8.0.1-py3-none-any.whl",
                "browser_download_url": "https://github.com/o/r/releases/download/v8.0.1/victim-8.0.1-py3-none-any.whl",
                "digest": "sha256:aaaa",
            },
            {
                "name": "../victim-8.0.1-py3-none-any.whl.metadata",
                "browser_download_url": "https://github.com/o/r/releases/download/v8.0.1/evil",
                "digest": "sha256:bbbb",
            },
        ],
    }
    projects = index.collect_projects([release], hash_url=never_hash)
    assert projects["victim"][0]["core_metadata"] is False


def build_wheel_bytes(
    metadata: bytes = b"Metadata-Version: 2.1\nName: mirrored\nVersion: 7.0.0\n",
) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("mirrored/__init__.py", "")
        archive.writestr("mirrored-7.0.0.dist-info/METADATA", metadata)
        archive.writestr("mirrored-7.0.0.dist-info/WHEEL", "Wheel-Version: 1.0\n")
    return buffer.getvalue()


def test_extract_metadata(tmp_path):
    wheel_bytes = build_wheel_bytes()
    projects = mirror_projects()
    index.mirror_files(
        projects, tmp_path, "tok", opener=make_opener(payload=wheel_bytes)
    )
    index.extract_metadata(projects, tmp_path)
    entry = projects["mirrored"][0]
    meta_path = (
        tmp_path / "files" / "mirrored" / "mirrored-7.0.0-py3-none-any.whl.metadata"
    )
    assert meta_path.read_bytes() == build_wheel_bytes.__defaults__[0]
    assert (
        entry["core_metadata"]
        == hashlib.sha256(build_wheel_bytes.__defaults__[0]).hexdigest()
    )

    index.write_site(projects, tmp_path, title="T", index_url=None)
    page = (tmp_path / "simple" / "mirrored" / "index.html").read_text()
    expected = f"sha256={entry['core_metadata']}"
    assert f'data-core-metadata="{expected}"' in page
    assert f'data-dist-info-metadata="{expected}"' in page
    data = json.loads((tmp_path / "simple" / "mirrored" / "index.json").read_text())
    assert data["files"][0]["core-metadata"] == {"sha256": entry["core_metadata"]}
    assert data["files"][0]["dist-info-metadata"] == {"sha256": entry["core_metadata"]}
    assert "core_metadata" not in data["files"][0]
    assert "source_repo" not in data["files"][0]


def test_extract_metadata_corrupt_wheel(tmp_path, capsys):
    projects = mirror_projects()
    index.mirror_files(
        projects, tmp_path, "tok", opener=make_opener(payload=b"not-a-zip")
    )
    index.extract_metadata(projects, tmp_path)
    assert projects["mirrored"][0]["core_metadata"] is False
    assert "cannot extract metadata" in capsys.readouterr().err
    assert not (
        tmp_path / "files" / "mirrored" / "mirrored-7.0.0-py3-none-any.whl.metadata"
    ).exists()


def build_ambiguous_wheel_bytes() -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("mirrored-7.0.0.dist-info/METADATA", b"one")
        archive.writestr("intruder-1.0.dist-info/METADATA", b"two")
    return buffer.getvalue()


@pytest.mark.parametrize(
    "payload,paired,error",
    [
        pytest.param(
            build_ambiguous_wheel_bytes(),
            False,
            ": no unique .dist-info/METADATA member",
            id="ambiguous-dist-info",
        ),
        pytest.param(
            b"not-a-zip",
            True,
            "cannot extract metadata",
            id="paired-but-corrupt",
        ),
    ],
)
def test_extract_metadata_failure_ladder(tmp_path, capsys, payload, paired, error):
    projects = mirror_projects()
    if paired:
        # link-mode pairing already recorded a hash from a release .metadata
        # asset — a failed extraction must reset it, not leave a stale claim
        projects["mirrored"][0]["core_metadata"] = "feedface"
    index.mirror_files(projects, tmp_path, "tok", opener=make_opener(payload=payload))
    index.extract_metadata(projects, tmp_path)
    assert projects["mirrored"][0]["core_metadata"] is False
    err = capsys.readouterr().err
    assert "cannot extract metadata" in err
    assert error in err
    assert not (
        tmp_path / "files" / "mirrored" / "mirrored-7.0.0-py3-none-any.whl.metadata"
    ).exists()


def test_metadata_true_renders_boolean(tmp_path):
    projects = index.collect_projects(METADATA_RELEASE, hash_url=never_hash)
    index.write_site(projects, tmp_path, title="T", index_url=None)
    page = (tmp_path / "simple" / "nudemeta" / "index.html").read_text()
    assert 'data-core-metadata="true"' in page
    data = json.loads((tmp_path / "simple" / "nudemeta" / "index.json").read_text())
    assert data["files"][0]["core-metadata"] is True
    nometa_page = (tmp_path / "simple" / "nometa" / "index.html").read_text()
    assert "data-core-metadata" not in nometa_page


def test_metadata_coverage():
    tagged = [dict(release, _source_repo="o/one") for release in FIXTURE_RELEASES]
    projects = index.collect_projects(tagged + METADATA_RELEASE, hash_url=fake_hash)
    coverage = index.metadata_coverage(projects)
    assert coverage["o/meta"] == (1, 3)  # nometa lacks metadata; 3 wheels total
    assert coverage["o/one"] == (2, 2)  # both fixture wheels lack metadata


def test_write_site_formats_json_only(tmp_path):
    projects = index.collect_projects(FIXTURE_RELEASES, hash_url=fake_hash)
    index.write_site(projects, tmp_path, title="T", index_url=None, formats=("json",))
    assert not list(tmp_path.rglob("*.html"))
    assert (tmp_path / "simple" / "index.json").exists()
    assert (
        tmp_path / "simple" / "github-releases-pypi-demo-lib" / "index.json"
    ).exists()
