.. include:: ../refs.rst

.. _howto-customize-pages:

===============================================
How do I customize the look of the index pages?
===============================================

Point the ``templates`` config key at a directory of Jinja templates that override the
built-ins, and extend the built-ins through the ``builtin/`` prefix so you only replace the
parts you care about. There is no command line flag for this — it is a config-file-only
setting.

.. code-block:: text

   index.yml
   templates/
     landing.html

.. code-block:: yaml

   # index.yml
   repositories:
     - yourorg/lib-one
   title: yourorg packages
   templates: ./templates      # resolved relative to THIS file

.. code-block:: html

   {# templates/landing.html #}
   {% extends "builtin/landing.html" %}
   {% block head %}<style>body { font-family: system-ui; max-width: 40rem; }</style>{% endblock %}
   {% block footer %}<footer>Questions? Ask in #packaging.</footer>{% endblock %}

Always extend through ``builtin/``. ``{% extends "landing.html" %}`` resolves to the override
itself and dies with a recursion error.

What you can override
=====================

.. list-table::
   :header-rows: 1
   :widths: 22 26 52

   * - Template
     - Blocks
     - Context
   * - ``landing.html``
     - ``title``, ``head``, ``header``, ``content``, ``footer``
     - ``title``, ``index_url`` (may be ``None``), ``projects``
   * - ``project.html``
     - ``title``, ``head``, ``header``, ``content``, ``footer``
     - ``project``, ``files``
   * - ``simple_root.html``
     - ``head``
     - ``projects``

Each entry in ``files`` carries ``filename``, ``url``, ``sha256`` (may be ``None``), ``size``,
``upload_time``, ``core_metadata``, and ``yanked``.

Three things to keep in mind
============================

* **The templates directory is not copied into the site.** Only the templates are rendered, so
  a ``style.css`` sitting next to them will not be published — inline the CSS in
  ``{% block head %}``, or copy the file into ``--out`` yourself after the build.
* **``simple_root.html`` and ``project.html`` are machine-read.** Their bodies are the
  :pep:`503` anchor lists that installers parse. If you replace ``project.html`` wholesale
  rather than extending it, keep the built-in's ``{% if file.sha256 %}`` guard around the
  ``#sha256=`` fragment, its ``data-core-metadata``/``data-dist-info-metadata`` attributes, and
  its ``data-yanked`` attribute, or you will publish links pip cannot verify, drop :pep:`658`
  metadata advertisements, and silently un-yank :pep:`592` yanked releases.
* **The JSON output is never templated.** Its shape is defined by :pep:`691`; overrides change
  the HTML only.

Next
====

* :ref:`config-templates` — resolution rules and the errors a bad path produces.
* :ref:`howto-publish-metadata` — what the metadata attributes are for.
