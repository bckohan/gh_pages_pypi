.. include:: ../refs.rst

.. _configuration:

=============
Configuration
=============

``ghr-pypi`` can be driven in two ways: with a single repository given as the positional
``REPO`` argument, or with a YAML configuration file given with ``--config``. Exactly one of
the two must be supplied — passing both, or neither, is an error (see :ref:`cli`).

The configuration file is the only way to aggregate several repositories into one index, and
the only way to set ``title``, ``url``, ``templates``, ``formats``, ``missing_digest``,
``metadata``, or ``mirror`` from a file. The single-repository form supports ``--mirror`` and
otherwise uses the defaults listed below, with ``title`` set to ``"<OWNER/NAME> package
index"`` and ``url`` set to the repository's GitHub Pages URL
(``https://<owner>.github.io/<name>/``).

The file is read as YAML and its top level must be a mapping. Only the eight keys documented
here are accepted; any other key aborts the build. Every value is validated before any network
request is made, so a configuration mistake fails immediately and cheaply.

.. code-block:: sh

   ghr-pypi --config index.yml --out site

Summary
=======

.. list-table::
   :header-rows: 1
   :widths: 18 24 20 38

   * - Key
     - Type
     - Default
     - Notes
   * - :ref:`config-repositories`
     - list of ``OWNER/NAME`` strings
     - *required*
     - Non-empty, no case-insensitive duplicates
   * - :ref:`config-templates`
     - string (path)
     - none
     - Resolved relative to the config file; must exist
   * - :ref:`config-title`
     - string
     - ``Package index``
     - Landing page heading and ``<title>``
   * - :ref:`config-url`
     - string (``https://``)
     - none
     - Enables the install example on the landing page
   * - :ref:`config-missing-digest`
     - ``download`` | ``no-fragment`` | ``omit``
     - ``download``
     - Rejected when ``mirror`` is enabled
   * - :ref:`config-formats`
     - list of ``html`` | ``json``
     - ``[html, json]``
     - Non-empty, no duplicates
   * - :ref:`config-mirror`
     - boolean
     - ``false``
     - Downloads assets into ``<out>/files/``
   * - :ref:`config-metadata`
     - boolean
     - ``true``
     - :pep:`658` core metadata handling

Keys
====

.. _config-repositories:

``repositories``
----------------

:Type: list of strings
:Default: none — **required**
:Constraints: Must be a non-empty list. Every entry must be a string of exactly two
              non-empty, ``/``-separated parts (``OWNER/NAME``). Entries must be unique
              when compared case-insensitively.

The repositories whose releases are indexed. Every wheel (``.whl``) and sdist (``.tar.gz``)
attached to any non-draft release of any listed repository becomes an entry in the index.
Draft releases are skipped because their assets are not publicly downloadable.

Repositories are processed in the order given. When two repositories publish the same
filename, the first occurrence wins and the duplicate is reported on stderr::

   warning: duplicate asset demo_lib-1.0-py3-none-any.whl ignored (https://...)

.. code-block:: yaml

   repositories:
     - yourorg/lib-one
     - yourorg/lib-two

.. _config-templates:

``templates``
-------------

:Type: string (directory path)
:Default: none — the built-in templates are used
:Constraints: Must be a string. Resolved relative to the **directory containing the config
              file**, then required to be an existing directory.

A directory of Jinja templates that override the built-ins. A file named ``landing.html``,
``project.html``, or ``simple_root.html`` in that directory replaces the corresponding
built-in wholesale. The built-ins remain reachable under a ``builtin/`` prefix, so an override
can extend rather than replace them:

.. code-block:: html

   {% extends "builtin/landing.html" %}
   {% block footer %}<footer>&copy; yourorg</footer>{% endblock %}

Always extend through the ``builtin/`` prefix — ``{% extends "landing.html" %}`` resolves to
the override itself and fails with a recursion error. ``landing.html`` and ``project.html``
define the blocks ``title``, ``head``, ``header``, ``content``, and ``footer``;
``simple_root.html`` defines only ``head``, because its body is the :pep:`503` anchor list
that installers parse.

Templates affect the HTML output only. The JSON Simple API output is spec-defined and is
never templated.

.. code-block:: yaml

   templates: ./templates

.. _config-title:

``title``
---------

:Type: string
:Default: ``Package index``
:Constraints: Must be a string.

The heading and ``<title>`` of the landing page (``<out>/index.html``). It has no effect when
``html`` is not in :ref:`config-formats`, because no landing page is written.

.. code-block:: yaml

   title: yourorg package index

.. _config-url:

``url``
-------

:Type: string
:Default: none
:Constraints: Must be a string beginning with ``https://``.

The public base URL the finished site will be served from. When set, the landing page shows a
copy-pasteable install command built from it — the value is stripped of trailing slashes and
``/simple/`` is appended:

.. code-block:: text

   pip install --extra-index-url https://yourorg.github.io/pypi/simple/ PACKAGE

When omitted, the landing page simply links to the simple index without an install example.
The value is not used for anything else: it does not rewrite asset URLs and it is not required
for the index to work.

.. code-block:: yaml

   url: https://yourorg.github.io/pypi/

.. _config-missing-digest:

``missing_digest``
------------------

:Type: string
:Default: ``download``
:Constraints: One of ``download``, ``no-fragment``, ``omit``. **Rejected outright when**
              :ref:`config-mirror` **is** ``true`` — even if the value equals the default.

GitHub's API supplies a sha256 digest for release assets uploaded since mid-2025. The builder
uses that digest directly and never downloads those files. This key governs only the assets
that have no API digest:

.. list-table::
   :header-rows: 1
   :widths: 20 80

   * - Value
     - Behavior
   * - ``download``
     - Download the asset and hash it, so the link carries a ``#sha256=`` fragment.
   * - ``no-fragment``
     - Index the asset with no ``#sha256=`` fragment; installers skip integrity
       verification for it.
   * - ``omit``
     - Leave the asset out of the index and warn on stderr.

Duplicate filenames are resolved *before* this policy is applied, so if the first
repository's copy of a filename lacks a digest, a later copy's digest is not consulted.

Under mirroring the policy is meaningless — every file is hashed from the bytes actually
downloaded — which is why setting both keys is a configuration error rather than a silent
no-op.

.. code-block:: yaml

   missing_digest: no-fragment

.. _config-formats:

``formats``
-----------

:Type: list of strings
:Default: ``[html, json]``
:Constraints: Must be a non-empty list whose entries are ``html`` or ``json``, with no
              duplicates.

Selects which representations of the index are written.

``html``
   Writes the :pep:`503` HTML tree — ``<out>/simple/index.html`` and
   ``<out>/simple/<project>/index.html`` — plus the human-facing landing page at
   ``<out>/index.html``.

``json``
   Writes the :pep:`691` JSON Simple API — ``<out>/simple/index.json`` and
   ``<out>/simple/<project>/index.json`` — at ``api-version`` 1.1, including the :pep:`700`
   ``versions``, ``size``, and ``upload-time`` fields.

``formats: [json]`` therefore produces a headless index with no landing page and no HTML;
``formats: [html]`` produces HTML only. With both (the default) the JSON files sit alongside
the HTML, which static hosts serve as ordinary files; a full webserver can instead serve them
at the canonical URLs through ``Accept``-header content negotiation on
``application/vnd.pypi.simple.v1+json``.

.. code-block:: yaml

   formats: [html, json]

.. _config-mirror:

``mirror``
----------

:Type: boolean
:Default: ``false``
:Constraints: Must be ``true`` or ``false``. Cannot be combined with
              :ref:`config-missing-digest`. On the single-repository command line the
              equivalent is the ``--mirror`` flag; passing ``--mirror`` together with
              ``--config`` is an error.

With ``mirror: true`` the builder downloads every indexed asset into
``<out>/files/<project>/`` and rewrites the index links to relative paths, so the finished
site is self-contained and relocatable and GitHub is out of the serving path. This is also
how private repositories are indexed: downloads go through GitHub's authenticated asset API
with the supplied token, whereas direct release-asset links would not be fetchable by
installers.

Every file is hashed while it streams to disk. Downloads are staged in a ``.part`` file and
only replace the destination after the length (when the server advertises ``Content-Length``)
and the advertised digest both check out, so a failed or interrupted build never corrupts a
previously mirrored file. Files already present with the expected hash are reused, so repeat
builds fetch only new assets — but files removed from releases are **not** pruned from
``<out>/files/``.

When :ref:`config-metadata` is also enabled, core metadata is extracted from every mirrored
wheel and written beside it as ``<filename>.metadata``.

.. code-block:: yaml

   mirror: true

.. _config-metadata:

``metadata``
------------

:Type: boolean
:Default: ``true``
:Constraints: Must be ``true`` or ``false``.

Controls :pep:`658` core metadata, which lets resolvers read a wheel's dependencies without
downloading the wheel.

* **Mirror mode** (:ref:`config-mirror` ``true``): metadata is extracted from each mirrored
  wheel, written next to it as ``<filename>.metadata``, and advertised in the index. A wheel
  that cannot be read produces a warning and is simply advertised without metadata.
* **Link mode**: the index can only advertise a metadata file that already lives at the
  wheel's own URL plus ``.metadata``, so the metadata must be uploaded as a release asset
  named ``<wheel-filename>.metadata``. The builder reports coverage per repository::

     warning: yourorg/lib-one: 3 of 4 wheels have no .metadata asset; resolvers must
     download full wheels for dependency metadata

With ``metadata: false`` no ``.metadata`` asset is ever paired, nothing is extracted, nothing
is advertised, and the coverage warnings are suppressed.

.. code-block:: yaml

   metadata: false

Validation errors
=================

Every failure below raises ``ConfigError``, which the command line prints prefixed with
``error:`` before exiting with status 1. ``{path}`` is the path passed to ``--config``.
Validation runs in the order listed, so only the first problem is reported.

``cannot read config file {path}: {error}``
   **Cause:** the file could not be opened or read — it does not exist, is a directory, or
   permissions deny it.
   **Fix:** check the path given to ``--config``; it is resolved relative to the working
   directory of the build, which in CI is the repository checkout.

``config file {path} is not valid UTF-8: {error}``
   **Cause:** the file's bytes are not decodable as UTF-8.
   **Fix:** re-save the file as UTF-8.

``invalid YAML in {path}: {error}``
   **Cause:** the file is not well-formed YAML. The wrapped message names the line and
   column.
   **Fix:** correct the syntax — most often inconsistent indentation or an unquoted value
   containing ``:``.

``{path}: top level must be a mapping``
   **Cause:** the document parses but is not a mapping — for example it is a bare list, a
   scalar, or empty.
   **Fix:** make the top level ``key: value`` pairs, starting with ``repositories:``.

``{path}: unknown key(s): {names}``
   **Cause:** the mapping contains keys outside the eight documented above; the sorted list
   of offenders is included.
   **Fix:** remove or rename them. Typos such as ``repository:`` or ``mirrors:`` land here.

``{path}: 'repositories' must be a non-empty list``
   **Cause:** ``repositories`` is absent, is not a list, or is an empty list.
   **Fix:** provide at least one ``OWNER/NAME`` entry.

``{path}: repository {repo!r} is not OWNER/NAME``
   **Cause:** an entry is not a string, or does not split into exactly two non-empty parts on
   ``/`` — ``yourorg``, ``yourorg/``, ``https://github.com/yourorg/repo`` all fail.
   **Fix:** use the bare ``owner/name`` slug, with no URL, no ``.git`` suffix, no trailing
   slash.

``{path}: 'repositories' contains duplicates``
   **Cause:** two entries are equal ignoring case — ``YourOrg/Lib`` and ``yourorg/lib``
   collide.
   **Fix:** list each repository once.

``{path}: 'templates' must be a string path``
   **Cause:** ``templates`` is present but is not a string (a list or mapping, typically).
   **Fix:** give a single path string.

``{path}: templates directory not found: {resolved}``
   **Cause:** the path resolved against the config file's directory is not an existing
   directory. The resolved absolute path is included.
   **Fix:** create the directory or correct the relative path. Remember it is relative to the
   config file, not to the working directory.

``{path}: 'url' must be a string``
   **Cause:** ``url`` is present but is not a string.
   **Fix:** quote it if YAML parsed it as something else.

``{path}: 'url' must be https``
   **Cause:** ``url`` does not start with ``https://``.
   **Fix:** use an ``https://`` URL. Plain ``http://`` is refused because installers should
   not be pointed at an unauthenticated index.

``{path}: 'title' must be a string``
   **Cause:** ``title`` is present but is not a string — an unquoted numeric or date-like
   value is the usual culprit.
   **Fix:** quote the value.

``{path}: 'missing_digest' must be one of download, no-fragment, omit, got {value!r}``
   **Cause:** ``missing_digest`` is not one of the three accepted values.
   **Fix:** use ``download``, ``no-fragment``, or ``omit``. Note ``no-fragment`` uses a
   hyphen, not an underscore.

``{path}: 'formats' must be a non-empty list``
   **Cause:** ``formats`` is present but is not a list, or is an empty list.
   **Fix:** list at least one of ``html`` or ``json``. To emit one format only, write
   ``formats: [json]`` rather than removing the other entry's value.

``{path}: 'formats' entries must be html or json, got {value!r}``
   **Cause:** an entry is something other than ``html`` or ``json``.
   **Fix:** correct the entry.

``{path}: 'formats' contains duplicates``
   **Cause:** the same format is listed twice.
   **Fix:** list each format once.

``{path}: 'mirror' must be true or false``
   **Cause:** ``mirror`` is present but did not parse as a YAML boolean — ``"true"`` in
   quotes, or ``yes`` in YAML 1.2 parsers, land here.
   **Fix:** use an unquoted ``true`` or ``false``.

``{path}: 'missing_digest' has no effect when 'mirror' is enabled``
   **Cause:** both ``mirror: true`` and a ``missing_digest`` key are present. The check is on
   the key's presence, so even ``missing_digest: download`` is rejected.
   **Fix:** delete ``missing_digest``. Mirroring hashes every file from the bytes it
   downloads, so there is nothing for the policy to decide.

``{path}: 'metadata' must be true or false``
   **Cause:** ``metadata`` is present but did not parse as a YAML boolean.
   **Fix:** use an unquoted ``true`` or ``false``.

Mirroring failures raise ``MirrorError`` rather than ``ConfigError``; they are described with
the other runtime failures in :ref:`cli`.

Complete example
================

Every key, annotated. This configuration mirrors two repositories into a self-contained site
served from a custom domain, with overridden templates and both output formats.

.. code-block:: yaml

   # index.yml — passed as: ghr-pypi --config index.yml --out site

   # Required. Releases from these repositories are aggregated, in order.
   # On a filename collision the first repository listed wins.
   repositories:
     - yourorg/lib-one
     - yourorg/lib-two

   # Optional. Landing page heading and <title>.
   title: yourorg package index

   # Optional. Public https base URL of the finished site; drives the install
   # example shown on the landing page (".../simple/" is appended).
   url: https://packages.yourorg.example/

   # Optional. Jinja template overrides, resolved relative to THIS file.
   templates: ./templates

   # Optional. Which representations to write. Both is the default.
   formats: [html, json]

   # Optional. Download assets into site/files/ and link to them relatively.
   # Required for private repositories.
   mirror: true

   # Optional. Extract and advertise PEP 658 core metadata. Default: true.
   metadata: true

   # NOTE: 'missing_digest' is deliberately absent — it is rejected whenever
   # 'mirror' is true. In link mode (mirror: false) it would be valid here:
   #
   #   missing_digest: download   # or no-fragment, or omit
