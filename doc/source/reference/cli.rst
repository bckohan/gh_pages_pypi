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

   ghr-pypi [REPO]... [--out DIRECTORY] [--config PATH] [--token TOKEN] [--mirror]

The package installs the ``ghr-pypi`` console script. It can equally be run without
installing:

.. code-block:: sh

   uvx ghr-pypi
   python -m pip install ghr-pypi && ghr-pypi yourorg/yourrepo --out site

Reference
=========

.. typer:: ghr_pypi.cli:app
   :prog: ghr-pypi
   :width: 80

Invocation forms
================

Repositories are named in one of two places: the ``repositories`` key of a
``--config`` file, or the positional ``REPO`` arguments. The two may not be
combined — passing both is an error, raised before the file is even read.

``GITHUB_REPOSITORY`` is the fallback for either. As a *source of repositories*
it is consulted only when neither the file nor the command line names one, so it
never conflicts with what you typed; GitHub Actions sets it for every step,
which is why it has to be harmless next to a config file. It still has two other
effects whenever it is set — it supplies the index URL (see
:ref:`cli-url-derivation`) and it is validated eagerly. If nothing names a
repository, the command exits 1.

No arguments
------------

.. code-block:: sh

   ghr-pypi

Inside GitHub Actions this is the whole invocation: ``GITHUB_REPOSITORY`` names
the repository being built and ``--out`` defaults to ``_site``, which is also
the directory ``actions/upload-pages-artifact`` uploads by default. Exactly one
repository is resolved this way, so the landing page comes out titled
``owner/repo package index`` and advertising ``https://owner.github.io/repo/``,
just as if you had typed the slug.

One or more repositories
------------------------

.. code-block:: sh

   ghr-pypi yourorg/yourrepo --out site
   ghr-pypi yourorg/lib-one yourorg/lib-two --out site

Each argument is a bare ``OWNER/NAME`` slug — not a URL, not a clone path.
Repeating one, ignoring case, is an error.

Defaults shared by both command line forms
------------------------------------------

Whichever of the two above you use, every setting takes its default except the
title and the URL:

* The landing page title becomes ``yourorg/yourrepo package index`` when exactly
  one repository is resolved, and ``Package index`` otherwise.
* The index URL advertised on the landing page is the GitHub Pages URL of
  ``GITHUB_REPOSITORY`` whenever that is set. The repository running the build
  is the one serving the site, even when it is indexing someone else's assets.
* Failing that, it is the Pages URL of the single resolved repository. Several
  repositories given outside Actions leave no URL at all, and the landing page
  then shows no install example.

In a Pages URL the owner is lower-cased and the repository name is used as
given.

``--mirror`` is the only behavioral switch available on the command line;
everything else requires a configuration file.

Configuration file
------------------

.. code-block:: sh

   ghr-pypi --config index.yml --out site

Required for indexing more than one repository from a fixed list, and the only
way to set ``title``, ``url``, ``templates``, ``formats``, ``missing_digest``,
or ``metadata``. See :ref:`configuration` for every key. Repositories must be
listed in the file, not on the command line — passing both is an error, though
``GITHUB_REPOSITORY`` may be set alongside a config file and is used only when
the file omits ``repositories``. ``--mirror`` is rejected in this form — set
``mirror: true`` in the file instead, so that the file remains the whole
description of the build.

.. _cli-url-derivation:

A configuration file never derives ``url`` from its own ``repositories``.
Omitting ``url`` means "no install example on the landing page": a repository
listed in the file is not necessarily the one serving the site, and the tool
will not guess. The command line form does guess, because there the repository
you named is normally your own.

The one thing that overrides this is ``GITHUB_REPOSITORY``. When it is set, its
Pages URL is used in **both** forms — including alongside a config file that
omits ``url`` — because the repository running the build is the host. Set
``url`` explicitly whenever the site is served from anywhere else.

Options
=======

``--out DIRECTORY``
   Where the site is written. Defaults to ``_site``, matching
   ``actions/upload-pages-artifact``. The directory and its parents are created
   if they do not exist. Existing files are overwritten; nothing is deleted, so
   stale projects or mirrored files from a previous build survive unless you
   clear the directory first.

``REPO...``
   Zero or more repositories to index, each as ``OWNER/NAME``. Defaults to the
   ``GITHUB_REPOSITORY`` environment variable, which is validated whenever it is
   set — even when the repositories come from elsewhere — so that a broken
   environment fails before any network request. An empty value counts as
   unset. Must not be combined with ``--config``.

``--config PATH``
   Path to the YAML configuration file. Its ``repositories`` key replaces the
   positional arguments, which must then be omitted. Relative paths in the file
   (``templates``) resolve against the file's own directory, not the working
   directory.

``--token TOKEN``
   GitHub API token, used as a bearer token for the releases API and — under mirroring — for
   the authenticated asset downloads. **Always required**, even for public repositories:
   unauthenticated GitHub API requests are rate-limited far too aggressively for a build.

``--mirror``
   Download every asset into ``<out>/files/`` and link to those copies relatively instead of
   linking to GitHub. Command line form only — with ``--config``, set ``mirror: true`` in the
   file. See :ref:`config-mirror` for the full behavior.

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
     run: uvx ghr-pypi

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
       an unknown option, a missing option value, an unparseable value. Usage text is
       printed.

Every exit-1 condition
----------------------

The checks below run in this order; the first one that fails ends the run.

``error: provide --token or set GITHUB_TOKEN``
   No token was supplied, or the supplied value was empty. Checked before anything else is
   validated, so this masks other problems until it is fixed.

``error: GITHUB_REPOSITORY '...' is not OWNER/NAME``
   The environment variable is set but is not exactly two non-empty
   ``/``-separated parts. It is validated whenever it is set — even when the
   repositories come from arguments or a config file — so that a broken
   environment fails before any network request. An empty value counts as unset
   and is not an error.

``error: with --config, list repositories in the config file``
   Positional ``REPO`` arguments were combined with ``--config``. Setting
   ``GITHUB_REPOSITORY`` does not trigger this.

``error: with --config, set 'mirror' in the config file``
   ``--mirror`` was combined with ``--config``.

``error: <config validation message>``
   The configuration file could not be read, parsed, or validated. Each message is listed
   verbatim with its cause and fix in :ref:`configuration`.

``error: <path> has no 'repositories' and GITHUB_REPOSITORY is not set``
   The config file omits ``repositories`` (or sets it to nothing) and there is
   no environment variable to fall back to.

``error: repository '...' is not OWNER/NAME``
   A positional ``REPO`` is not exactly two non-empty ``/``-separated parts. Passing a URL
   such as ``https://github.com/yourorg/repo`` fails here.

``error: repository '...' given more than once``
   The same repository was passed twice on the command line; the comparison
   ignores case. There is no equivalent check across sources — an argument that
   differs only in case from ``GITHUB_REPOSITORY`` is taken as given.

``error: provide REPO..., set GITHUB_REPOSITORY, or use --config``
   No repositories were resolved from any source.

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
