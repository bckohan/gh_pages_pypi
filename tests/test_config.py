from pathlib import Path

import pytest

from github_releases_pypi.config import Config, ConfigError, load


def write(tmp_path: Path, text: str) -> Path:
    cfg = tmp_path / "index.yml"
    cfg.write_text(text)
    return cfg


def test_load_full(tmp_path):
    (tmp_path / "tpl").mkdir()
    cfg = load(
        write(
            tmp_path,
            """
repositories:
  - bckohan/github-releases-pypi
  - someorg/other-project
templates: ./tpl
title: My Package Index
url: https://example.github.io/idx/
""",
        )
    )
    assert cfg == Config(
        repositories=("bckohan/github-releases-pypi", "someorg/other-project"),
        templates=(tmp_path / "tpl").resolve(),
        title="My Package Index",
        url="https://example.github.io/idx/",
    )


def test_load_minimal_defaults(tmp_path):
    cfg = load(write(tmp_path, "repositories: [a/b]\n"))
    assert cfg.repositories == ("a/b",)
    assert cfg.templates is None
    assert cfg.title == "Package index"
    assert cfg.url is None


def test_templates_relative_to_config_dir(tmp_path, monkeypatch):
    (tmp_path / "tpl").mkdir()
    monkeypatch.chdir(tmp_path.parent)  # CWD != config dir
    cfg = load(write(tmp_path, "repositories: [a/b]\ntemplates: tpl\n"))
    assert cfg.templates == (tmp_path / "tpl").resolve()


@pytest.mark.parametrize(
    "text,match",
    [
        ("- just\n- a list\n", "top level must be a mapping"),
        ("repositories: [a/b]\nbogus: 1\n", "unknown key"),
        ("title: no repos\n", "'repositories' must be a non-empty list"),
        ("repositories: []\n", "'repositories' must be a non-empty list"),
        ("repositories: notalist\n", "'repositories' must be a non-empty list"),
        ("repositories: [noslash]\n", "is not OWNER/NAME"),
        ("repositories: [a/b/c]\n", "is not OWNER/NAME"),
        ("repositories: [/b]\n", "is not OWNER/NAME"),
        ("repositories: [123]\n", "is not OWNER/NAME"),
        ("repositories: [a/b, a/b]\n", "contains duplicates"),
        ("repositories: [A/b, a/b]\n", "contains duplicates"),
        ("repositories: [a/b]\ntemplates: 123\n", "'templates' must be a string path"),
        (
            "repositories: [a/b]\ntemplates: [a, b]\n",
            "'templates' must be a string path",
        ),
        (
            "repositories: [a/b]\ntemplates: ./missing\n",
            "templates directory not found",
        ),
        ("repositories: [a/b]\nurl: http://insecure.example\n", "'url' must be https"),
        ("repositories: [a/b]\nurl: true\n", "'url' must be a string"),
        ("repositories: [a/b]\ntitle: [not, a, string]\n", "'title' must be a string"),
        ("repositories: [a/b]\nurl: [::bad yaml::\n", "invalid YAML"),
        (
            "repositories: [a/b]\nmissing_digest: always\n",
            "must be one of download, no-fragment, omit",
        ),
        (
            "repositories: [a/b]\nmissing_digest: true\n",
            "'missing_digest' must be one of",
        ),
        ("repositories: [a/b]\nformats: []\n", "'formats' must be a non-empty list"),
        ("repositories: [a/b]\nformats: html\n", "'formats' must be a non-empty list"),
        (
            "repositories: [a/b]\nformats: [xml]\n",
            "'formats' entries must be html or json, got 'xml'",
        ),
        (
            "repositories: [a/b]\nformats: [html, html]\n",
            "'formats' contains duplicates",
        ),
        ("repositories: [a/b]\nmirror: maybe\n", "'mirror' must be true or false"),
        ("repositories: [a/b]\nmirror: 1\n", "'mirror' must be true or false"),
        (
            "repositories: [a/b]\nmirror: true\nmissing_digest: download\n",
            "'missing_digest' has no effect when 'mirror' is enabled",
        ),
    ],
)
def test_load_errors(tmp_path, text, match):
    with pytest.raises(ConfigError, match=match):
        load(write(tmp_path, text))


@pytest.mark.parametrize("value", ["download", "no-fragment", "omit"])
def test_missing_digest_values(tmp_path, value):
    cfg = load(write(tmp_path, f"repositories: [a/b]\nmissing_digest: {value}\n"))
    assert cfg.missing_digest == value


def test_missing_digest_default(tmp_path):
    assert load(write(tmp_path, "repositories: [a/b]\n")).missing_digest == "download"


@pytest.mark.parametrize(
    "value,expected",
    [
        ("[html]", ("html",)),
        ("[json]", ("json",)),
        ("[html, json]", ("html", "json")),
        ("[json, html]", ("json", "html")),
    ],
)
def test_formats_values(tmp_path, value, expected):
    cfg = load(write(tmp_path, f"repositories: [a/b]\nformats: {value}\n"))
    assert cfg.formats == expected


def test_formats_default(tmp_path):
    assert load(write(tmp_path, "repositories: [a/b]\n")).formats == ("html", "json")


@pytest.mark.parametrize("value,expected", [("true", True), ("false", False)])
def test_mirror_values(tmp_path, value, expected):
    cfg = load(write(tmp_path, f"repositories: [a/b]\nmirror: {value}\n"))
    assert cfg.mirror is expected


def test_mirror_default(tmp_path):
    assert load(write(tmp_path, "repositories: [a/b]\n")).mirror is False


def test_mirror_allows_missing_digest_when_off(tmp_path):
    cfg = load(
        write(tmp_path, "repositories: [a/b]\nmirror: false\nmissing_digest: omit\n")
    )
    assert cfg.mirror is False and cfg.missing_digest == "omit"


def test_load_missing_file(tmp_path):
    with pytest.raises(ConfigError, match="cannot read config file"):
        load(tmp_path / "nope.yml")


def test_load_non_utf8(tmp_path):
    cfg = tmp_path / "index.yml"
    cfg.write_bytes(b"\xff\xfe repositories: [a/b]")
    with pytest.raises(ConfigError, match="not valid UTF-8"):
        load(cfg)
