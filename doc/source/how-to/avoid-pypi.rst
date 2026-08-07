.. include:: ../refs.rst

.. _howto-avoid-pypi:

==================================================================
How do I stop pip from resolving my package from pypi.org instead?
==================================================================

Use ``--index-url``, not ``--extra-index-url``. With an *extra* index ``pip`` queries both and
takes the highest version it finds anywhere, so a package with your name on pypi.org can
shadow yours — the dependency-confusion problem.

.. code-block:: sh

   pip install --index-url https://yourorg.github.io/pypi/simple/ yourpkg

Make it stick, rather than retyping it:

.. code-block:: sh

   pip config set global.index-url https://yourorg.github.io/pypi/simple/
   # or, per environment:
   export PIP_INDEX_URL=https://yourorg.github.io/pypi/simple/

.. code-block:: text

   # requirements.txt
   --index-url https://yourorg.github.io/pypi/simple/
   yourpkg==1.2.0

See `pip's configuration documentation <https://pip.pypa.io/en/stable/topics/configuration/>`_
for where those settings are stored and how they are layered.

When you need PyPI as well
==========================

Most projects do — your package's own dependencies live there. Then ``--index-url`` alone is
not enough, and you have two real options:

* **Own the name on pypi.org.** Register it, even as an empty placeholder, so nobody else can
  claim it and shadow your private build. Cheapest insurance there is.
* **Pin the package to your index.** ``uv`` can bind a requirement to one specific index and
  never look elsewhere for it:

  .. code-block:: toml

     [[tool.uv.index]]
     name = "yourorg"
     url = "https://yourorg.github.io/pypi/simple/"
     explicit = true

     [tool.uv.sources]
     yourpkg = { index = "yourorg" }

  ``explicit = true`` means the index is consulted *only* for requirements that name it. See
  `uv's package index documentation <https://docs.astral.sh/uv/concepts/indexes/>`_.

.. note::

   The built-in landing page prints an ``--extra-index-url`` example, because that is the
   friendlier default for a public index. If you would rather hand out ``--index-url``,
   override the ``content`` block of ``landing.html`` — see :ref:`howto-customize-pages`.

Next
====

* :ref:`config-url` — the value the landing page's install example is built from.
* :ref:`tutorial-github-pages` — ``--index-url`` used against a real index, start to finish.
