.. include:: ./refs.rst

Changelog
=========

2026.8.5 (2026-08-05)
---------------------

* Initial release.
* Aggregate releases from multiple repositories via ``--config`` (YAML).
* Template override hooks: a config-specified directory and ``builtin/``-prefixed block inheritance.
* Use GitHub's asset digests instead of downloading to hash; ``missing_digest``
  config policy for digest-less assets.
