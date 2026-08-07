.. include:: ../refs.rst

.. _howto-aggregate-repositories:

=======================================================
How do I aggregate several repositories into one index?
=======================================================

List them in a YAML config file and pass it with ``--config``. The config file replaces the
positional ``REPO`` argument — it is the only way to index more than one repository.

.. code-block:: yaml

   # index.yml
   repositories:
     - yourorg/lib-one
     - yourorg/lib-two
     - otherorg/vendored-tool
   title: yourorg package index
   url: https://yourorg.github.io/pypi/

.. code-block:: sh

   ghr-pypi --config index.yml --out site

Every wheel and sdist attached to every non-draft release of every listed repository ends up
in one flat index, keyed by :pep:`503`-normalized project name. Two repositories publishing
different projects get one project page each; two publishing the *same* project name share a
page, with the files merged.

Give it a token that can read them all
======================================

A workflow's built-in ``github.token`` can only read the repository the workflow runs in, so
it cannot build an aggregate index. Use a fine-grained personal access token or a GitHub App
installation token with **Contents: Read-only** on each repository, stored as a secret:

.. code-block:: yaml

   - name: Build the package index
     env:
       GITHUB_TOKEN: ${{ secrets.INDEX_TOKEN }}
     run: uvx ghr-pypi --config index.yml --out site

The build reads one page of releases per repository, so the config file is usually checked
into a small dedicated "index" repository whose Pages site (or CDN project) serves the result.
That workflow does need a checkout — the config file has to be on disk.

Collisions and duplicates
=========================

* Repositories are processed **in the listed order**. If two of them publish the same
  *filename*, the first occurrence wins and the loser is reported::

     warning: duplicate asset demo_lib-1.0-py3-none-any.whl ignored (https://...)

* Listing the same repository twice is rejected outright, case-insensitively:
  ``yourorg/Lib`` and ``yourorg/lib`` collide with
  ``'repositories' contains duplicates``.

* Every entry must be a bare ``OWNER/NAME`` slug — not a URL, not a clone path.

Next
====

* :ref:`config-repositories` — the exact constraints and error messages.
* :ref:`cli` — why ``--mirror`` is refused with ``--config``, and what the single-repository
  form defaults differently.
