"""Tiny CLI for the GitHub Pages PyPI demo."""

import sys

from ghr_pypi_demo_lib import greeting

__version__ = "2026.8.6.1"


def main(argv=None):
    """Print a greeting for the first CLI argument (default: world)."""
    args = sys.argv[1:] if argv is None else argv
    print(greeting(args[0] if args else "world"))
