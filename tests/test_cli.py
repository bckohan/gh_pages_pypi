from typer.testing import CliRunner

from github_releases_pypi import index
from github_releases_pypi.cli import app
from tests.test_index import FIXTURE_RELEASES

runner = CliRunner()


def all_output(result):
    """stdout+stderr across click versions (mix_stderr removed in click 8.2)."""
    try:
        return result.output + (result.stderr or "")
    except (ValueError, AttributeError):
        return result.output


def test_cli_requires_token(tmp_path, monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    result = runner.invoke(
        app, ["bckohan/github-releases-pypi", "--out", str(tmp_path)]
    )
    assert result.exit_code == 1
    assert "provide --token or set GITHUB_TOKEN" in all_output(result)


def test_cli_fails_with_no_packages(tmp_path, monkeypatch):
    monkeypatch.setattr(index, "fetch_releases", lambda repo, token: [])
    result = runner.invoke(
        app, ["bckohan/github-releases-pypi", "--out", str(tmp_path), "--token", "x"]
    )
    assert result.exit_code == 1
    assert "no package assets" in all_output(result)


def test_cli_reports_api_failure(tmp_path, monkeypatch):
    import urllib.error

    def boom(repo, token):
        raise urllib.error.URLError("nope")

    monkeypatch.setattr(index, "fetch_releases", boom)
    result = runner.invoke(
        app, ["bckohan/github-releases-pypi", "--out", str(tmp_path), "--token", "x"]
    )
    assert result.exit_code == 1
    assert "GitHub API request for bckohan/github-releases-pypi failed" in all_output(
        result
    )


def test_cli_writes_site(tmp_path, monkeypatch):
    monkeypatch.setattr(index, "fetch_releases", lambda repo, token: FIXTURE_RELEASES)
    monkeypatch.setattr(index, "hash_url", lambda url: "cafef00d")
    result = runner.invoke(
        app, ["bckohan/github-releases-pypi", "--out", str(tmp_path), "--token", "x"]
    )
    assert result.exit_code == 0, all_output(result)
    assert "wrote index for 2 project(s)" in result.output
    assert (
        tmp_path / "simple" / "github-releases-pypi-demo-lib" / "index.html"
    ).exists()


def test_cli_token_from_env(tmp_path, monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "x")
    monkeypatch.setattr(index, "fetch_releases", lambda repo, token: FIXTURE_RELEASES)
    monkeypatch.setattr(index, "hash_url", lambda url: "cafef00d")
    result = runner.invoke(
        app, ["bckohan/github-releases-pypi", "--out", str(tmp_path)]
    )
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
        "bckohan/github-releases-pypi": FIXTURE_RELEASES,
        "someorg/other-project": second_repo_releases,
    }
    monkeypatch.setattr(
        index, "fetch_releases", lambda repo, token: releases_by_repo[repo]
    )
    monkeypatch.setattr(index, "hash_url", lambda url: "cafef00d")
    cfg = config_file(
        tmp_path,
        """
repositories:
  - bckohan/github-releases-pypi
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
    assert (out / "simple" / "github-releases-pypi-demo-lib" / "index.html").exists()
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
        return FIXTURE_RELEASES

    monkeypatch.setattr(index, "fetch_releases", boom)
    cfg = config_file(
        tmp_path,
        "repositories: [bckohan/github-releases-pypi, someorg/other-project]\n",
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


def test_cli_reports_asset_download_failure(tmp_path, monkeypatch):
    import urllib.error

    monkeypatch.setattr(index, "fetch_releases", lambda repo, token: FIXTURE_RELEASES)

    def boom(url):
        raise urllib.error.URLError("asset gone")

    monkeypatch.setattr(index, "hash_url", boom)
    result = runner.invoke(
        app,
        ["bckohan/github-releases-pypi", "--out", str(tmp_path), "--token", "x"],
    )
    assert result.exit_code == 1
    assert "downloading a release asset failed" in all_output(result)
