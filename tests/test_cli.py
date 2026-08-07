import json

from typer.testing import CliRunner

from ghr_pypi import index
from ghr_pypi.cli import app
from tests.test_index import FILTER_RELEASES, FIXTURE_RELEASES

runner = CliRunner()


def all_output(result):
    """stdout+stderr across click versions (mix_stderr removed in click 8.2)."""
    try:
        return result.output + (result.stderr or "")
    except (ValueError, AttributeError):
        return result.output


def fetch_stub(releases):
    """fetch_releases fake returning fresh copies; the CLI tags releases in place."""
    return lambda repo, token: [dict(release) for release in releases]


def test_cli_requires_token(tmp_path, monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    result = runner.invoke(app, ["bckohan/ghr-pypi", "--out", str(tmp_path)])
    assert result.exit_code == 1
    assert "provide --token or set GITHUB_TOKEN" in all_output(result)


def test_cli_fails_with_no_packages(tmp_path, monkeypatch):
    monkeypatch.setattr(index, "fetch_releases", lambda repo, token: [])
    result = runner.invoke(
        app, ["bckohan/ghr-pypi", "--out", str(tmp_path), "--token", "x"]
    )
    assert result.exit_code == 1
    assert "no package assets" in all_output(result)


def test_cli_reports_api_failure(tmp_path, monkeypatch):
    import urllib.error

    def boom(repo, token):
        raise urllib.error.URLError("nope")

    monkeypatch.setattr(index, "fetch_releases", boom)
    result = runner.invoke(
        app, ["bckohan/ghr-pypi", "--out", str(tmp_path), "--token", "x"]
    )
    assert result.exit_code == 1
    assert "GitHub API request for bckohan/ghr-pypi failed" in all_output(result)


def test_cli_writes_site(tmp_path, monkeypatch):
    monkeypatch.setattr(index, "fetch_releases", fetch_stub(FIXTURE_RELEASES))
    monkeypatch.setattr(index, "hash_url", lambda url: "cafef00d")
    result = runner.invoke(
        app, ["bckohan/ghr-pypi", "--out", str(tmp_path), "--token", "x"]
    )
    assert result.exit_code == 0, all_output(result)
    assert "wrote index for 2 project(s)" in result.output
    assert (tmp_path / "simple" / "ghr-pypi-demo-lib" / "index.html").exists()


def test_cli_token_from_env(tmp_path, monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "x")
    monkeypatch.setattr(index, "fetch_releases", fetch_stub(FIXTURE_RELEASES))
    monkeypatch.setattr(index, "hash_url", lambda url: "cafef00d")
    result = runner.invoke(app, ["bckohan/ghr-pypi", "--out", str(tmp_path)])
    assert result.exit_code == 0, all_output(result)
    assert (tmp_path / "simple" / "index.html").exists()


def config_file(tmp_path, text):
    cfg = tmp_path / "index.yml"
    cfg.write_text(text)
    return cfg


def test_cli_requires_exactly_one_source(tmp_path):
    result = runner.invoke(app, ["--out", str(tmp_path), "--token", "x"])
    assert result.exit_code == 1
    assert "provide exactly one of REPO or --config" in all_output(result)

    cfg = config_file(tmp_path, "repositories: [a/b]\n")
    result = runner.invoke(
        app,
        ["a/b", "--config", str(cfg), "--out", str(tmp_path), "--token", "x"],
    )
    assert result.exit_code == 1
    assert "provide exactly one of REPO or --config" in all_output(result)


def test_cli_config_merges_repositories(tmp_path, monkeypatch):
    second_repo_releases = [
        {
            "tag_name": "v1.0.0",
            "assets": [
                {
                    "name": "otherpkg-1.0.0-py3-none-any.whl",
                    "browser_download_url": "https://github.com/someorg/other/releases/download/v1.0.0/otherpkg-1.0.0-py3-none-any.whl",
                },
            ],
        },
    ]
    releases_by_repo = {
        "bckohan/ghr-pypi": FIXTURE_RELEASES,
        "someorg/other-project": second_repo_releases,
    }
    monkeypatch.setattr(
        index,
        "fetch_releases",
        lambda repo, token: fetch_stub(releases_by_repo[repo])(repo, token),
    )
    monkeypatch.setattr(index, "hash_url", lambda url: "cafef00d")
    cfg = config_file(
        tmp_path,
        """
repositories:
  - bckohan/ghr-pypi
  - someorg/other-project
title: Aggregated Index
""",
    )
    out = tmp_path / "site"
    result = runner.invoke(
        app, ["--config", str(cfg), "--out", str(out), "--token", "x"]
    )
    assert result.exit_code == 0, all_output(result)
    assert "wrote index for 3 project(s)" in result.output
    assert (out / "simple" / "otherpkg" / "index.html").exists()
    assert (out / "simple" / "ghr-pypi-demo-lib" / "index.html").exists()
    landing = (out / "index.html").read_text()
    assert "Aggregated Index" in landing
    assert "--extra-index-url" not in landing  # no url in config


def test_cli_config_error(tmp_path):
    cfg = config_file(tmp_path, "repositories: []\n")
    result = runner.invoke(
        app, ["--config", str(cfg), "--out", str(tmp_path), "--token", "x"]
    )
    assert result.exit_code == 1
    assert "'repositories' must be a non-empty list" in all_output(result)


def test_cli_config_url_failure_names_repo(tmp_path, monkeypatch):
    import urllib.error

    def boom(repo, token):
        if repo == "someorg/other-project":
            raise urllib.error.URLError("nope")
        return fetch_stub(FIXTURE_RELEASES)(repo, token)

    monkeypatch.setattr(index, "fetch_releases", boom)
    cfg = config_file(
        tmp_path,
        "repositories: [bckohan/ghr-pypi, someorg/other-project]\n",
    )
    result = runner.invoke(
        app, ["--config", str(cfg), "--out", str(tmp_path), "--token", "x"]
    )
    assert result.exit_code == 1
    assert "GitHub API request for someorg/other-project failed" in all_output(result)


def test_cli_rejects_malformed_repo(tmp_path):
    result = runner.invoke(app, ["foo", "--out", str(tmp_path), "--token", "x"])
    assert result.exit_code == 1
    assert "is not OWNER/NAME" in all_output(result)


def test_cli_missing_digest_policy_flows_through(tmp_path, monkeypatch):
    legacy_release = [
        {
            "tag_name": "v1.0.0",
            "assets": [
                {
                    "name": "legacy-1.0.0-py3-none-any.whl",
                    "browser_download_url": "https://github.com/a/b/releases/download/v1.0.0/legacy-1.0.0-py3-none-any.whl",
                },
            ],
        },
    ]
    monkeypatch.setattr(index, "fetch_releases", lambda repo, token: legacy_release)

    def never_hash(url):
        raise AssertionError("hash_url called despite no-fragment policy")

    monkeypatch.setattr(index, "hash_url", never_hash)
    cfg = config_file(tmp_path, "repositories: [a/b]\nmissing_digest: no-fragment\n")
    out = tmp_path / "site"
    result = runner.invoke(
        app, ["--config", str(cfg), "--out", str(out), "--token", "x"]
    )
    assert result.exit_code == 0, all_output(result)
    page = (out / "simple" / "legacy" / "index.html").read_text()
    assert "#sha256=" not in page


def test_cli_formats_json_only(tmp_path, monkeypatch):
    monkeypatch.setattr(index, "fetch_releases", fetch_stub(FIXTURE_RELEASES))
    monkeypatch.setattr(index, "hash_url", lambda url: "cafef00d")
    cfg = config_file(tmp_path, "repositories: [a/b]\nformats: [json]\n")
    out = tmp_path / "site"
    result = runner.invoke(
        app, ["--config", str(cfg), "--out", str(out), "--token", "x"]
    )
    assert result.exit_code == 0, all_output(result)
    assert (out / "simple" / "index.json").exists()
    assert not list(out.rglob("*.html"))


def test_cli_mirror_flag(tmp_path, monkeypatch):
    monkeypatch.setattr(index, "fetch_releases", fetch_stub(FIXTURE_RELEASES))
    calls = []

    def fake_mirror(projects, out_dir, token, **kwargs):
        calls.append((out_dir, token))
        for files in projects.values():
            for entry in files:
                entry["sha256"] = "cafef00d"
                entry["url"] = f"../../files/x/{entry['filename']}"

    monkeypatch.setattr(index, "mirror_files", fake_mirror)

    def never_hash(url):
        raise AssertionError("hash_url called despite mirror mode")

    monkeypatch.setattr(index, "hash_url", never_hash)
    out = tmp_path / "site"
    result = runner.invoke(
        app,
        [
            "bckohan/ghr-pypi",
            "--out",
            str(out),
            "--token",
            "tok",
            "--mirror",
        ],
    )
    assert result.exit_code == 0, all_output(result)
    assert calls == [(out, "tok")]
    page = (out / "simple" / "ghr-pypi-demo-lib" / "index.html").read_text()
    assert "../../files/x/" in page


def test_cli_mirror_with_config_errors(tmp_path):
    cfg = config_file(tmp_path, "repositories: [a/b]\n")
    result = runner.invoke(
        app,
        ["--config", str(cfg), "--out", str(tmp_path), "--token", "x", "--mirror"],
    )
    assert result.exit_code == 1
    assert "with --config, set 'mirror' in the config file" in all_output(result)


def test_cli_mirror_from_config(tmp_path, monkeypatch):
    monkeypatch.setattr(index, "fetch_releases", fetch_stub(FIXTURE_RELEASES))
    calls = []

    def fake_mirror(projects, out_dir, token, **kwargs):
        calls.append(token)
        for files in projects.values():
            for entry in files:
                entry["sha256"] = "cafef00d"
                entry["url"] = f"../../files/x/{entry['filename']}"

    monkeypatch.setattr(index, "mirror_files", fake_mirror)
    cfg = config_file(tmp_path, "repositories: [a/b]\nmirror: true\n")
    result = runner.invoke(
        app, ["--config", str(cfg), "--out", str(tmp_path / "s"), "--token", "tok"]
    )
    assert result.exit_code == 0, all_output(result)
    assert calls == ["tok"]


def test_cli_mirror_error_surfaces(tmp_path, monkeypatch):
    monkeypatch.setattr(index, "fetch_releases", fetch_stub(FIXTURE_RELEASES))

    def boom(projects, out_dir, token, **kwargs):
        raise index.MirrorError("bad.whl: downloaded sha256 x does not match y")

    monkeypatch.setattr(index, "mirror_files", boom)
    result = runner.invoke(
        app,
        [
            "bckohan/ghr-pypi",
            "--out",
            str(tmp_path),
            "--token",
            "t",
            "--mirror",
        ],
    )
    assert result.exit_code == 1
    assert "bad.whl" in all_output(result)


def test_cli_reports_asset_download_failure(tmp_path, monkeypatch):
    import urllib.error

    monkeypatch.setattr(index, "fetch_releases", fetch_stub(FIXTURE_RELEASES))

    def boom(url):
        raise urllib.error.URLError("asset gone")

    monkeypatch.setattr(index, "hash_url", boom)
    result = runner.invoke(
        app,
        ["bckohan/ghr-pypi", "--out", str(tmp_path), "--token", "x"],
    )
    assert result.exit_code == 1
    assert "downloading a release asset failed" in all_output(result)


def test_cli_link_mode_metadata_warnings(tmp_path, monkeypatch):
    from tests.test_index import METADATA_RELEASE

    covered = [
        {
            "tag_name": "v1.0.0",
            "assets": [
                {
                    "name": "cov-1.0.0-py3-none-any.whl",
                    "browser_download_url": "https://github.com/a/covered/releases/download/v1.0.0/cov-1.0.0-py3-none-any.whl",
                    "digest": "sha256:aaaa",
                },
                {
                    "name": "cov-1.0.0-py3-none-any.whl.metadata",
                    "browser_download_url": "https://github.com/a/covered/releases/download/v1.0.0/cov-1.0.0-py3-none-any.whl.metadata",
                    "digest": "sha256:bbbb",
                },
            ],
        },
    ]
    releases_by_repo = {"a/covered": covered, "o/meta": METADATA_RELEASE}
    monkeypatch.setattr(
        index,
        "fetch_releases",
        lambda repo, token: fetch_stub(releases_by_repo[repo])(repo, token),
    )
    cfg = config_file(tmp_path, "repositories: [a/covered, o/meta]\n")
    result = runner.invoke(
        app, ["--config", str(cfg), "--out", str(tmp_path / "s"), "--token", "x"]
    )
    assert result.exit_code == 0, all_output(result)
    err = all_output(result)
    assert "warning: o/meta: 1 of 3 wheels have no .metadata asset" in err
    assert "warning: a/covered" not in err


def test_cli_metadata_false_silences_warnings(tmp_path, monkeypatch):
    from tests.test_index import METADATA_RELEASE

    monkeypatch.setattr(index, "fetch_releases", fetch_stub(METADATA_RELEASE))
    cfg = config_file(tmp_path, "repositories: [o/meta]\nmetadata: false\n")
    out = tmp_path / "s"
    result = runner.invoke(
        app, ["--config", str(cfg), "--out", str(out), "--token", "x"]
    )
    assert result.exit_code == 0, all_output(result)
    assert "have no .metadata asset" not in all_output(result)
    # advertising is disabled too, not just the warnings
    page = (out / "simple" / "hasmeta" / "index.html").read_text()
    assert "data-core-metadata" not in page
    assert (
        "core-metadata" not in (out / "simple" / "hasmeta" / "index.json").read_text()
    )


def test_cli_mirror_metadata_false_advertises_nothing(tmp_path, monkeypatch):
    from tests.test_index import METADATA_RELEASE

    monkeypatch.setattr(index, "fetch_releases", fetch_stub(METADATA_RELEASE))

    def fake_mirror(projects, out_dir, token, **kwargs):
        for files in projects.values():
            for entry in files:
                entry["sha256"] = "cafef00d"
                entry["url"] = f"../../files/x/{entry['filename']}"

    monkeypatch.setattr(index, "mirror_files", fake_mirror)
    cfg = config_file(
        tmp_path, "repositories: [o/meta]\nmirror: true\nmetadata: false\n"
    )
    out = tmp_path / "s"
    result = runner.invoke(
        app, ["--config", str(cfg), "--out", str(out), "--token", "x"]
    )
    assert result.exit_code == 0, all_output(result)
    # a release-uploaded .metadata asset must NOT be advertised against the
    # rewritten local URL — no sibling exists there, resolvers would 404
    page = (out / "simple" / "hasmeta" / "index.html").read_text()
    assert "data-core-metadata" not in page
    assert (
        "core-metadata" not in (out / "simple" / "hasmeta" / "index.json").read_text()
    )


def test_cli_mirror_runs_extraction(tmp_path, monkeypatch):
    monkeypatch.setattr(index, "fetch_releases", fetch_stub(FIXTURE_RELEASES))
    extract_calls = []

    def fake_mirror(projects, out_dir, token, **kwargs):
        for files in projects.values():
            for entry in files:
                entry["sha256"] = "cafef00d"
                entry["url"] = f"../../files/x/{entry['filename']}"

    monkeypatch.setattr(index, "mirror_files", fake_mirror)
    monkeypatch.setattr(
        index, "extract_metadata", lambda projects, out: extract_calls.append(out)
    )
    out = tmp_path / "site"
    result = runner.invoke(
        app,
        ["bckohan/ghr-pypi", "--out", str(out), "--token", "t", "--mirror"],
    )
    assert result.exit_code == 0, all_output(result)
    assert extract_calls == [out]


def test_cli_mirror_metadata_false_skips_extraction(tmp_path, monkeypatch):
    monkeypatch.setattr(index, "fetch_releases", fetch_stub(FIXTURE_RELEASES))
    monkeypatch.setattr(
        index,
        "mirror_files",
        lambda projects, out_dir, token, **kwargs: None,
    )
    called = []
    monkeypatch.setattr(
        index, "extract_metadata", lambda projects, out: called.append(1)
    )
    cfg = config_file(tmp_path, "repositories: [a/b]\nmirror: true\nmetadata: false\n")
    result = runner.invoke(
        app, ["--config", str(cfg), "--out", str(tmp_path / "s"), "--token", "x"]
    )
    assert result.exit_code == 0, all_output(result)
    assert called == []


def test_cli_mirror_network_failure(tmp_path, monkeypatch):
    import urllib.error

    monkeypatch.setattr(index, "fetch_releases", fetch_stub(FIXTURE_RELEASES))

    def boom(projects, out_dir, token, **kwargs):
        raise urllib.error.URLError("nope")

    monkeypatch.setattr(index, "mirror_files", boom)
    result = runner.invoke(
        app,
        [
            "bckohan/ghr-pypi",
            "--out",
            str(tmp_path),
            "--token",
            "t",
            "--mirror",
        ],
    )
    assert result.exit_code == 1
    assert "downloading a release asset failed" in all_output(result)


def test_cli_config_filters_flow_through(tmp_path, monkeypatch):
    # end-to-end guard on the cli -> collect_projects wiring: without
    # filters=cfg.filters the config's yanked/exclude blocks are inert
    monkeypatch.setattr(index, "fetch_releases", fetch_stub(FILTER_RELEASES))

    def never_hash(url):
        raise AssertionError("hash_url called; every fixture asset has a digest")

    monkeypatch.setattr(index, "hash_url", never_hash)
    cfg = config_file(
        tmp_path,
        """
repositories: [a/b]
yanked:
  Yankee:
    "1.1.0": "bad wheel"
exclude:
  yankee:
    - "1.0.0"
""",
    )
    out = tmp_path / "site"
    result = runner.invoke(
        app, ["--config", str(cfg), "--out", str(out), "--token", "x"]
    )
    assert result.exit_code == 0, all_output(result)
    page = (out / "simple" / "yankee" / "index.html").read_text()
    assert 'data-yanked="bad wheel"' in page
    assert "yankee-1.0.0" not in page  # the excluded version never reached the index
    data = json.loads((out / "simple" / "yankee" / "index.json").read_text())
    assert data["versions"] == ["1.1.0"]
    assert data["files"][0]["yanked"] == "bad wheel"
