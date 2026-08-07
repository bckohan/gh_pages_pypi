.. include:: ./refs.rst

Changelog
=========

2026.8.X
--------

* Support yank/exclude.
* The positional ``REPO`` argument takes zero or more repositories and defaults
  to ``$GITHUB_REPOSITORY``; ``--out`` defaults to ``_site`` and the config
  file's ``repositories`` key is optional. A GitHub Pages workflow can now run
  ``ghr-pypi`` with no arguments.


2026.8.6
--------

* Initial release.
* Aggregate releases from multiple repositories via ``--config`` (YAML).
* Template override hooks: a config-specified directory and ``builtin/``-prefixed block inheritance.
* Use GitHub's asset digests instead of downloading to hash; ``missing_digest``
  config policy for digest-less assets.
* Emit a PEP 691/700 JSON Simple API alongside the HTML index, controlled by
  the ``formats`` config key.
* ``mirror`` mode: download assets into the site (private-repo support,
  self-contained output, incremental re-builds).
* Serve PEP 658/714 core metadata: extracted from mirrored wheels, passed
  through from ``.metadata`` release assets, with per-repository coverage
  warnings.
* Release workflow publishes each wheel's PEP 658 ``.metadata`` as a
  release asset.
* ``yanked`` and ``exclude`` config keys, keyed by project then version:
  ``yanked`` marks files PEP 592 yanked (``data-yanked`` in the HTML, a
  ``yanked`` key in the JSON) while leaving them installable by exact pin;
  ``exclude`` keeps them out of the index entirely.
* Versions are computed at build time from git tags; no version strings are
  stored in the repository.
* Added a full Diátaxis documentation manual: tutorials, how-to guides, and
  reference.
