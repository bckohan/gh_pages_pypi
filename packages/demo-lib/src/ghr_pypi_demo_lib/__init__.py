"""Tiny greeting library for the GitHub Pages PyPI demo."""

from importlib.metadata import version

__version__ = version("ghr-pypi-demo-lib")


def greeting(name):
    """Return a greeting proving this package was importable."""
    return f"Hello, {name}! (served from GitHub Pages)"
