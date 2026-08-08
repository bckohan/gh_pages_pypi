.. include:: ../refs.rst

.. _tutorial-github-pages:

=======================
Publish on GitHub Pages
=======================

In this tutorial you will write a small Python package, publish it as a GitHub release, turn
that release into a real package index, and install the package from that index with ``pip``.
Nothing runs on a server you own and nothing costs anything. Two GitHub Actions workflows do
all the work: one builds the wheel and publishes the release, the other builds the index and
deploys it to GitHub Pages.

Allow about twenty minutes. You do not need to have used GitHub Actions before. Follow the
steps in order, type every command exactly as it is written, and at the end you will have
installed a package from an index you built yourself.

What you will need
==================

* A GitHub account.
* ``git``.
* The `GitHub CLI <https://cli.github.com/>`_, signed in — run ``gh auth login`` once.
* `uv <https://docs.astral.sh/uv/getting-started/installation/>`_.
* ``python3``, to check the result at the end.

Every command below refers to your GitHub username. Set it once, in the terminal you will use
for the whole tutorial:

.. code-block:: sh

   export OWNER=$(gh api user --jq .login)
   echo "$OWNER"

That should print your username. Keep this terminal open.

Step 1 — Create the package
===========================

Make a directory, start a git repository in it, and create the package layout:

.. code-block:: sh

   mkdir hello-index
   cd hello-index
   git init -b main
   mkdir -p src/hello_index .github/workflows

Create ``pyproject.toml`` with exactly this content:

.. code-block:: toml

   [build-system]
   requires = ["hatchling"]
   build-backend = "hatchling.build"

   [project]
   name = "hello-index"
   version = "1.0.0"
   description = "A package installed from a GitHub release asset"
   requires-python = ">=3.9"

   [tool.hatch.build.targets.wheel]
   packages = ["src/hello_index"]

Create ``src/hello_index/__init__.py``:

.. code-block:: python

   """A very small package, published from a GitHub release asset."""

   __version__ = "1.0.0"


   def greet(source: str) -> str:
       """Return a greeting naming where this package was installed from."""
       return f"Hello from {source}!"

Build it once, locally, to be sure the packaging works:

.. code-block:: sh

   uv build

You will see ``dist/hello_index-1.0.0-py3-none-any.whl`` and
``dist/hello_index-1.0.0.tar.gz``. Delete them again — the workflow will build the real ones:

.. code-block:: sh

   rm -rf dist

Step 2 — Add the release workflow
=================================

This workflow runs when you push a tag starting with ``v``. It builds the wheel and the
sdist, creates a GitHub release, attaches both files to it, and then starts the index build.

Create ``.github/workflows/release.yml``:

.. code-block:: yaml

   name: release

   on:
     push:
       tags:
         - "v*"

   permissions: {}

   jobs:
     release:
       runs-on: ubuntu-latest
       permissions:
         contents: write # create the release and upload the distributions
         actions: write # start the pages workflow once the release exists
       steps:
         - uses: actions/checkout@v7
           with:
             persist-credentials: false

         - uses: astral-sh/setup-uv@v9

         - name: Build the wheel and the sdist
           run: uv build

         - name: Create the release and attach the distributions
           env:
             GH_TOKEN: ${{ github.token }}
             GH_REPO: ${{ github.repository }}
           run: gh release create "$GITHUB_REF_NAME" dist/* --generate-notes

         - name: Rebuild the package index
           env:
             GH_TOKEN: ${{ github.token }}
             GH_REPO: ${{ github.repository }}
           run: gh workflow run pages.yml

.. note::

   The last step exists because of a rule that surprises everyone the first time. A release
   created by a workflow using the built-in ``GITHUB_TOKEN`` does **not** fire a ``release``
   event in other workflows — GitHub suppresses it so that workflows cannot trigger
   themselves in a loop. See `events that trigger workflows
   <https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows>`_.
   Without ``gh workflow run pages.yml`` the index would simply never notice the new release.

Step 3 — Add the Pages workflow
===============================

This workflow reads the repository's releases, writes a :pep:`503` index into ``_site/``, and
publishes that directory to GitHub Pages.

Create ``.github/workflows/pages.yml``:

.. code-block:: yaml

   name: pages

   on:
     release:
       types: [published, deleted]
     workflow_dispatch:

   permissions: {}

   concurrency:
     group: pages
     cancel-in-progress: true

   jobs:
     build:
       runs-on: ubuntu-latest
       permissions:
         contents: read # read the repository's releases
       steps:
         - uses: astral-sh/setup-uv@v9

         - name: Build the package index
           env:
             GITHUB_TOKEN: ${{ github.token }}
           run: uvx ghr-pypi index

         - uses: actions/configure-pages@v6

         - uses: actions/upload-pages-artifact@v5

     deploy:
       needs: build
       runs-on: ubuntu-latest
       permissions:
         pages: write # deploy the built site
         id-token: write # authenticate the deployment
       environment:
         name: github-pages
         url: ${{ steps.deployment.outputs.page_url }}
       steps:
         - id: deployment
           uses: actions/deploy-pages@v5

Four things about this file are worth noticing.

The build step passes ``index`` and nothing else. ``index`` takes the repository to index from
``GITHUB_REPOSITORY``, which Actions sets for every step, and writes the site to ``_site`` —
which is also the directory ``actions/upload-pages-artifact`` uploads when it is given no
``path``. Naming either one explicitly
(``ghr-pypi index "$GITHUB_REPOSITORY" --out site``, with a matching ``path: site``) still
works and is what you would do outside Actions.

The build job never checks the repository out. It does not need to: ``ghr-pypi`` reads the
releases through GitHub's API, so the only inputs are the repository name and a token.

``GITHUB_TOKEN`` is the workflow's own automatically provided token. ``ghr-pypi index``
always requires a token, even for a public repository, because unauthenticated API requests
are rate limited far too aggressively to build an index with. ``contents: read`` is all it
needs for the repository the workflow runs in. See `automatic token authentication
<https://docs.github.com/en/actions/tutorials/authenticate-with-github_token>`_.

The workflow only runs on a release or on an explicit dispatch. It deliberately does not run
on every push, because ``ghr-pypi index`` refuses to write an empty index — a run before your
first release would fail.

Step 4 — Push the repository to GitHub
======================================

.. code-block:: sh

   git add .
   git commit -m "hello-index 1.0.0"
   gh repo create hello-index --public --source=. --push

The repository now exists at ``https://github.com/$OWNER/hello-index``.

Step 5 — Turn on GitHub Pages
=============================

Open the repository's settings page:

.. code-block:: sh

   echo "https://github.com/$OWNER/hello-index/settings/pages"

In **Build and deployment**, set **Source** to **GitHub Actions**. There is nothing to save;
the choice takes effect immediately. Background on this setting is in `configuring a
publishing source
<https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site>`_.

Do this before the next step. The ``actions/configure-pages`` step fails with a clear error if
Pages has not been enabled for the repository.

Step 6 — Publish the first release
==================================

.. code-block:: sh

   git tag v1.0.0
   git push origin v1.0.0

Pushing the tag starts the release workflow.

Step 7 — Watch the two workflows
================================

Wait for the release workflow to finish:

.. code-block:: sh

   gh run watch "$(gh run list --workflow release.yml --limit 1 \
     --json databaseId --jq '.[0].databaseId')"

When it reports success, the release exists and it has dispatched the index build. Wait for
that one too:

.. code-block:: sh

   gh run watch "$(gh run list --workflow pages.yml --limit 1 \
     --json databaseId --jq '.[0].databaseId')"

Now read what the index build actually said:

.. code-block:: sh

   gh run view --log "$(gh run list --workflow pages.yml --limit 1 \
     --json databaseId --jq '.[0].databaseId')" | grep -E 'wrote index|warning:'

Two lines come back, each prefixed by ``gh`` with its job and step name. The first is the
result::

   wrote index for 1 project(s) to _site

The second is a warning::

   warning: <your username>/hello-index: 1 of 1 wheels have no .metadata asset; resolvers
   must download full wheels for dependency metadata

That warning is expected and harmless here. It means installers cannot read your package's
dependency list without downloading the wheel itself. :ref:`config-metadata` explains what to
do about it later.

Step 8 — Look at what you built
===============================

Print the address of your index and open it in a browser:

.. code-block:: sh

   echo "https://$OWNER.github.io/hello-index/"

The landing page lists the projects in the index and shows the install command. The first
deployment of a brand-new Pages site can take a minute or two to become reachable; if you get
a 404, wait and reload.

The index itself lives one level down. These are the pages ``pip`` actually reads:

.. code-block:: sh

   curl -s "https://$OWNER.github.io/hello-index/simple/hello-index/" | head -20

Each link ends with a ``#sha256=...`` fragment. That digest comes from GitHub's release asset
API and is what makes the download verifiable: ``pip`` computes the hash of what it received
and refuses the file if it does not match.

Step 9 — Install your package from your index
=============================================

This is the point of the whole exercise. Make a throwaway virtual environment and install
from the index you just deployed:

.. code-block:: sh

   python3 -m venv /tmp/hello-index-check
   /tmp/hello-index-check/bin/pip install \
     --index-url "https://$OWNER.github.io/hello-index/simple/" \
     hello-index

``pip`` reports::

   Successfully installed hello-index-1.0.0

Nothing in that install came from PyPI. ``--index-url`` replaced PyPI entirely, ``pip`` read
your ``simple/`` pages, followed the link to the release asset on GitHub, and verified the
sha256. Prove the package works:

.. code-block:: sh

   /tmp/hello-index-check/bin/python -c \
     "import hello_index; print(hello_index.greet('GitHub Pages'))"

.. code-block:: text

   Hello from GitHub Pages!

Clean up the throwaway environment:

.. code-block:: sh

   rm -rf /tmp/hello-index-check

What you built
==============

A repository that, every time you push a version tag, builds a wheel, publishes it as a
GitHub release asset, regenerates a :pep:`503` and :pep:`691` index from every release it has
ever made, and deploys that index to GitHub Pages. The packages are stored as release assets,
served by GitHub's own CDN; the index is a directory of static files with no server, no
database, and no credentials sitting anywhere.

Push ``v1.0.1`` after bumping the version in ``pyproject.toml`` and the whole cycle repeats.

Where to go next
================

* The :ref:`how-to guides <how-to>` answer the questions that come next: aggregating several
  repositories into one index, indexing a private repository, customizing the landing page.
* :ref:`configuration` documents every key of the YAML configuration file, which is how you
  set the title, the URL, and everything else the command line form leaves at its default.
* :ref:`cli` documents every command line option, every exit code, and every error message.
* The tool itself lives at repo_.
