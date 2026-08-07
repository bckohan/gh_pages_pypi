import re
import sys
from pathlib import Path

import pytest
from packaging.version import Version

from ghr_pypi._version import get_version

# tomllib is stdlib only on 3.11+; this project supports 3.10, so the pyproject
# assertions below are skipped there rather than breaking collection.
try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.10
    tomllib = None  # type: ignore[assignment]

REPO_ROOT = Path(__file__).parent.parent

PYPROJECTS = [
    (REPO_ROOT / "pyproject.toml", "src/ghr_pypi/_version.py"),
    (
        REPO_ROOT / "packages/demo-lib/pyproject.toml",
        "src/ghr_pypi_demo_lib/_version.py",
    ),
    (
        REPO_ROOT / "packages/demo-app/pyproject.toml",
        "src/ghr_pypi_demo_app/_version.py",
    ),
]


def test_get_version_uses_env(monkeypatch):
    monkeypatch.setenv("PACKAGE_VERSION", "1.2.3")
    assert get_version() == "1.2.3"


def test_get_version_dev_fallback(monkeypatch):
    monkeypatch.delenv("PACKAGE_VERSION", raising=False)
    fallback = get_version()
    assert re.fullmatch(r"\d{4}\.\d{1,2}\.\d{1,2}\.dev0", fallback), fallback
    assert str(Version(fallback)) == fallback


def test_get_version_empty_env_falls_back(monkeypatch):
    monkeypatch.setenv("PACKAGE_VERSION", "")
    assert get_version().endswith(".dev0")


@pytest.mark.skipif(sys.version_info < (3, 11), reason="tomllib requires 3.11+")
@pytest.mark.parametrize("pyproject,version_path", PYPROJECTS)
def test_pyproject_version_is_dynamic(pyproject, version_path):
    data = tomllib.loads(pyproject.read_text())
    assert "version" not in data["project"], f"{pyproject} pins a static version"
    assert data["project"]["dynamic"] == ["version"]
    hatch = data["tool"]["hatch"]["version"]
    assert hatch["source"] == "code"
    assert hatch["expression"] == "get_version()"
    assert (pyproject.parent / hatch["path"]).is_file()
    assert hatch["path"] == version_path


def test_version_sources_identical():
    contents = {(p.parent / vp).read_text() for p, vp in PYPROJECTS}
    assert len(contents) == 1, "the three _version.py copies have drifted"


def test_dunder_version_is_pep440():
    import ghr_pypi

    assert str(Version(ghr_pypi.__version__)) == ghr_pypi.__version__
