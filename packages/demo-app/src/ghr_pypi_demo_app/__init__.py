"""Tiny CLI for the GitHub Pages PyPI demo."""

import sys
from importlib.metadata import version

from ghr_pypi_demo_lib import greeting

__version__ = version("ghr-pypi-demo-app")


def main(argv=None):
    """Print a greeting for the first CLI argument (default: world)."""
    args = sys.argv[1:] if argv is None else argv
    print(greeting(args[0] if args else "world"))
