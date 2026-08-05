"""Tiny CLI for the GitHub Pages PyPI demo."""

import sys

from github_releases_pypi_demo_lib import greeting

__version__ = "1.0.0"


def main(argv=None):
    """Print a greeting for the first CLI argument (default: world)."""
    args = sys.argv[1:] if argv is None else argv
    print(greeting(args[0] if args else "world"))
