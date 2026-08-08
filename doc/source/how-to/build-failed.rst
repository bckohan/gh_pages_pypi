.. include:: ../refs.rst

.. _howto-build-failed:

=================================================
Why is my index empty, or why did the build fail?
=================================================

Every failure prints one line beginning with ``error:`` and exits 1 — read that line first.
Reproduce it locally in seconds, where the warnings are easier to see than in a CI log:

.. code-block:: sh

   GITHUB_TOKEN=$(gh auth token) uvx ghr-pypi index yourorg/yourrepo --out /tmp/site

"No package assets found"
=========================

::

   error: no package assets found in releases of yourorg/yourrepo; refusing to build an
   empty index

The releases were read successfully and contained nothing indexable. In order of likelihood:

* **The assets are not wheels or sdists.** Only ``.whl`` and ``.tar.gz`` files are collected;
  a ``.zip`` sdist, a ``.sigstore`` bundle, a checksum file or a bare ``.metadata`` sidecar is
  ignored, silently. (The reverse gotcha: *any* ``.tar.gz`` is indexed, under whatever name
  precedes its final ``-``, so an unrelated tarball can appear as a project.)
* **The releases are drafts.** Draft releases are skipped entirely.
* **The project publishes to PyPI but attaches nothing to its releases.** Building a wheel in
  CI is not the same as uploading it to the release; check with
  ``gh release view <tag> --json assets --jq '.assets[].name'``.
* **``missing_digest: omit`` removed everything.** Each dropped file warns
  ``... has no digest, omitted (missing_digest=omit)``. Switch to ``download`` or
  ``no-fragment``.
* **The repository has more than 100 releases.** One page is read, newest first, so old
  releases fall off the end. That empties an index only if every recent release is asset-less.

The other error lines
=====================

``error: provide --token or set GITHUB_TOKEN``
   Checked before anything else, so it masks other problems until you fix it. A token is
   required even for public repositories.

``error: GitHub API request for <repo> failed: ...``
   Bad, expired or under-scoped token; a repository that does not exist as far as this token
   is concerned (GitHub answers 404 rather than 403 for repositories a token cannot see);
   rate limiting; a network failure.

``error: provide REPO..., set GITHUB_REPOSITORY, or use --config``
   No repositories were resolved. Pass one or more ``OWNER/NAME`` arguments,
   run inside GitHub Actions (which sets ``GITHUB_REPOSITORY``), or supply a
   config file that lists them.

``error: with --config, list repositories in the config file``
   Positional arguments and ``--config`` are mutually exclusive. Move the
   repositories into the file's ``repositories`` key. ``GITHUB_REPOSITORY``
   does not trigger this — it is used only when the file omits the key.

``error: <path> has no 'repositories' and GITHUB_REPOSITORY is not set``
   The config file omits ``repositories`` and there is nothing to fall back to.
   Add the key, or pass the repository in the environment.

``error: GITHUB_REPOSITORY 'x' is not OWNER/NAME``
   The environment variable is malformed. It is validated whenever it is set,
   even when the repositories come from elsewhere, so that a broken environment
   fails before any network request.

``error: repository 'x' given more than once``
   The same repository was passed twice on the command line (the comparison
   ignores case). There is no such check across sources — an argument that
   differs only in case from ``GITHUB_REPOSITORY`` is taken as given.

``error: with --config, set 'mirror' in the config file``
   ``--mirror`` is a flag of the command line form only; with a config file it is a key.

``error: <config message>``
   Configuration validation. Every message is listed with its cause and fix in
   :ref:`configuration`.

``error: downloading a release asset failed: ...``
   A file transfer failed — while hashing digest-less assets, or while mirroring.

Exit status 2, with usage text, means the command line itself did not parse (an unknown
option, a missing option value).

Warnings are not failures
=========================

Lines beginning with ``warning:`` never stop the build: duplicate filenames, unsafe asset
names, omitted assets, unreadable wheels, and the :pep:`658` coverage report. An index can be
published successfully and still be missing what you expected, so read them.

Next
====

* :ref:`cli` — every exit-1 condition in the order it is checked.
* :ref:`configuration` — every ``ConfigError`` message, verbatim.
