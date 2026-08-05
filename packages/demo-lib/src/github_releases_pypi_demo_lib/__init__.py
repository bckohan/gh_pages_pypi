"""Tiny greeting library for the GitHub Pages PyPI demo."""

__version__ = "1.0.0"


def greeting(name):
    """Return a greeting proving this package was importable."""
    return f"Hello, {name}! (served from GitHub Pages)"
