.. include:: ./refs.rst

Changelog
=========

2026.8.X
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
* Versions are computed at build time from git tags; no version strings are
  stored in the repository.
* Added a full Diátaxis documentation manual: tutorials, how-to guides, and
  reference.
