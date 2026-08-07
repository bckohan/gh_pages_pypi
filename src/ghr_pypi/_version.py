"""Build-time version source: ``PACKAGE_VERSION`` or a dated dev version."""

import os
from datetime import datetime


def get_version() -> str:
    """Return ``PACKAGE_VERSION`` when set, else a dated dev version.

    ``just print-version`` computes the canonical dev version (``devN``);
    this ``dev0`` floor only applies to builds that bypass it. Kept free of
    git calls so it works inside sdist builds — and note hatchling takes the
    static version from a sdist's ``PKG-INFO`` rather than re-running this,
    so wheels built from a released sdist keep the released version.
    """
    now = datetime.now().astimezone()
    return os.environ.get("PACKAGE_VERSION") or f"{now.year}.{now.month}.{now.day}.dev0"
