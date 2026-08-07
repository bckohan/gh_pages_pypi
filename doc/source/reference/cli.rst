.. include:: ../refs.rst

.. _cli:

======================
Command Line Interface
======================

``ghr-pypi`` is a single command. It reads the releases of one or more GitHub repositories,
collects their wheel and sdist assets, and writes a :pep:`503` package index into a directory
of your choosing. It never starts a server and never writes anything outside ``--out``.

Synopsis
========

.. code-block:: text

   ghr-pypi [REPO] --out DIRECTORY [--config PATH] [--token TOKEN] [--mirror]

The package installs the ``ghr-pypi`` console script. It can equally be run without
installing:

.. code-block:: sh

   uvx ghr-pypi "$GITHUB_REPOSITORY" --out site
   python -m pip install ghr-pypi && ghr-pypi yourorg/yourrepo --out site

Reference
=========

.. typer:: ghr_pypi.cli:app
   :prog: ghr-pypi
   :width: 80

Invocation forms
================

Exactly one of the positional ``REPO`` argument and the ``--config`` option must be given.
Supplying both, or neither, exits with status 1.

Single repository
-----------------

.. code-block:: sh

   ghr-pypi yourorg/yourrepo --out site

The argument is a bare ``OWNER/NAME`` slug — not a URL, not a clone path. In this form the
remaining settings take their defaults, except that the landing page title becomes
``yourorg/yourrepo package index`` and the index URL advertised on the landing page is the
repository's GitHub Pages URL, ``https://<owner>.github.io/<name>/`` (the owner is
lower-cased, the repository name is used as given). ``--mirror`` is the only behavioral
switch available here; everything else requires a configuration file.

Configuration file
------------------

.. code-block:: sh

   ghr-pypi --config index.yml --out site

Required for indexing more than one repository, and the only way to set ``title``, ``url``,
``templates``, ``formats``, ``missing_digest``, or ``metadata``. See :ref:`configuration` for
every key. ``--mirror`` is rejected in this form — set ``mirror: true`` in the file instead,
so that the file remains the whole description of the build.

Options
=======

``--out DIRECTORY``
   **Required.** Where the site is written. The directory and its parents are created if
   they do not exist. Existing files are overwritten; nothing is deleted, so stale projects
   or mirrored files from a previous build survive unless you clear the directory first.

``REPO``
   The repository to index, as ``OWNER/NAME``. Mutually exclusive with ``--config``.

``--config PATH``
   Path to the YAML configuration file. Mutually exclusive with ``REPO``. Relative paths in
   the file (``templates``) resolve against the file's own directory, not the working
   directory.

``--token TOKEN``
   GitHub API token, used as a bearer token for the releases API and — under mirroring — for
   the authenticated asset downloads. **Always required**, even for public repositories:
   unauthenticated GitHub API requests are rate-limited far too aggressively for a build.

``--mirror``
   Download every asset into ``<out>/files/`` and link to those copies relatively instead of
   linking to GitHub. Single-repository form only. See :ref:`config-mirror` for the full
   behavior.

``GITHUB_TOKEN``
================

``--token`` reads its default from the ``GITHUB_TOKEN`` environment variable, so the token
never has to appear in a command line or a process listing.

Inside GitHub Actions the automatically provided ``github.token`` is sufficient for the
repository the workflow runs in:

.. code-block:: yaml

   - name: Build the package index
     env:
       GITHUB_TOKEN: ${{ github.token }}
     run: uvx ghr-pypi "$GITHUB_REPOSITORY" --out site

For repositories other than the one running the workflow — that is, for any aggregating
configuration — ``github.token`` is not enough. Use a fine-grained personal access token or a
GitHub App installation token with read access to each repository's contents, stored as a
secret:

.. code-block:: yaml

   env:
     GITHUB_TOKEN: ${{ secrets.INDEX_TOKEN }}

Exit codes
==========

.. list-table::
   :header-rows: 1
   :widths: 10 90

   * - Code
     - Meaning
   * - ``0``
     - The index was written. The command prints ``wrote index for N project(s) to <out>``
       on stdout.
   * - ``1``
     - The build failed. A single line beginning with ``error:`` is printed on stderr and
       nothing is deployed.
   * - ``2``
     - Command line usage error, raised by the argument parser before the build starts —
       ``--out`` missing, an unknown option, an unparseable value. Usage text is printed.

Every exit-1 condition
----------------------

The checks below run in this order; the first one that fails ends the run.

``error: provide exactly one of REPO or --config``
   Both ``REPO`` and ``--config`` were given, or neither was.

``error: provide --token or set GITHUB_TOKEN``
   No token was supplied, or the supplied value was empty. Checked before anything else is
   validated, so this masks other problems until it is fixed.

``error: with --config, set 'mirror' in the config file``
   ``--mirror`` was combined with ``--config``.

``error: <config validation message>``
   The configuration file could not be read, parsed, or validated. Each message is listed
   verbatim with its cause and fix in :ref:`configuration`.

``error: repository '...' is not OWNER/NAME``
   The positional ``REPO`` is not exactly two non-empty ``/``-separated parts. Passing a URL
   such as ``https://github.com/yourorg/repo`` fails here.

``error: GitHub API request for <repo> failed: <reason>``
   The releases API call failed — bad or expired token, insufficient permissions, a
   nonexistent or inaccessible repository, rate limiting, or a network failure. The named
   repository is the one being fetched when the failure occurred.

``error: downloading a release asset failed: <reason>``
   An asset download failed. This happens while hashing digest-less assets under
   ``missing_digest: download``, and again while mirroring.

``error: no package assets found in releases of <repos>; refusing to build an empty index``
   The repositories were read successfully but contained no wheel or sdist assets in any
   non-draft release. The index is deliberately not written, so a misconfigured run can never
   replace a working index with an empty one. Common causes: assets attached only to draft
   releases, a token that cannot see the releases, a repository that publishes to PyPI but
   attaches nothing to its releases, or ``missing_digest: omit`` removing everything.

``error: <mirroring message>``
   A mirrored download failed verification. The messages are ``<file>: unsafe path``,
   ``<file>: asset has no API download URL``, ``<file>: refusing to fetch non-https URL:
   ...``, ``<file>: truncated download (N of M bytes)``, and ``<file>: downloaded sha256 ...
   does not match advertised digest ...``. The partially written file is removed and any
   previously mirrored copy is left intact.

Warnings
--------

Diagnostics that do **not** fail the build are printed on stderr and start with ``warning:``:
duplicate filenames across repositories, assets skipped for unsafe names, assets omitted
under ``missing_digest: omit``, wheels whose core metadata could not be extracted, and the
per-repository :pep:`658` metadata coverage report. They are worth reading in CI logs — an
index can be published successfully and still be missing what you expected.

Examples
========

Index one repository for GitHub Pages
-------------------------------------

.. code-block:: sh

   export GITHUB_TOKEN=ghp_...
   ghr-pypi yourorg/yourrepo --out site
   # wrote index for 2 project(s) to site

Serve ``site/`` at ``https://yourorg.github.io/yourrepo/`` and install from it:

.. code-block:: sh

   pip install --index-url https://yourorg.github.io/yourrepo/simple/ yourpackage

Aggregate several repositories
------------------------------

.. code-block:: yaml

   # index.yml
   repositories:
     - yourorg/lib-one
     - yourorg/lib-two
   title: yourorg package index
   url: https://yourorg.github.io/pypi/

.. code-block:: sh

   GITHUB_TOKEN="$INDEX_TOKEN" ghr-pypi --config index.yml --out site

The token must be able to read every listed repository; a workflow's built-in
``github.token`` cannot.

Index a private repository
--------------------------

.. code-block:: sh

   ghr-pypi yourorg/private-repo --out site --token "$GITHUB_TOKEN" --mirror

``--mirror`` downloads each asset through GitHub's authenticated asset API into
``site/files/`` and links to those copies, because direct release-asset links to a private
repository are not fetchable by pip. Serve the resulting directory behind whatever
authentication your host provides; pip and uv both understand basic auth and ``netrc``:

.. code-block:: sh

   pip install --index-url https://user:pass@packages.example/simple/ yourpackage

Emit the JSON API only
----------------------

.. code-block:: yaml

   # json-only.yml
   repositories:
     - yourorg/lib-one
   formats: [json]

.. code-block:: sh

   ghr-pypi --config json-only.yml --out site

Writes ``site/simple/index.json`` and ``site/simple/<project>/index.json`` and nothing else —
no landing page, no HTML. Useful when a webserver in front of the files performs
``Accept``-header content negotiation, or when the index is consumed only by tools that speak
:pep:`691`.
