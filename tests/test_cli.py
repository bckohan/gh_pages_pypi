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
