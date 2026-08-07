.. include:: ../refs.rst

.. _tutorials:

=========
Tutorials
=========

These are lessons, not recipes. Each one starts from an empty repository and ends with a
package you install from an index you built yourself, and each is self-contained: follow any
single tutorial start to finish, in order, without reading the others. Everything you need to
type is on the page, there are no choices to make along the way, and if you follow the steps
exactly the result is guaranteed. Come back to the :ref:`how-to guides <how-to>` and the
:ref:`reference <reference>` once you want to adapt what you built.

.. toctree::
   :maxdepth: 2
   :caption: Contents:

   github-pages
   cloudflare
   nginx

Which one should I do?
======================

Any of them, and the first one is the shortest. They differ in where the index ends up and in
what that host is able to do for you.

.. list-table::
   :header-rows: 1
   :widths: 22 14 64

   * - Tutorial
     - Time
     - What it teaches
   * - :ref:`tutorial-github-pages`
     - ~20 min
     - Zero infrastructure. Two GitHub Actions workflows publish a release and deploy the
       index; the packages stay on GitHub and are linked to.
   * - :ref:`tutorial-cloudflare`
     - ~30 min
     - A CDN in front of a mirrored index — packages and pages both served from the edge —
       with cache-lifetime rules, and a note on what edge code would add.
   * - :ref:`tutorial-nginx`
     - ~45 min
     - Full control on a server you own: content negotiation between the HTML and
       :pep:`691` JSON APIs at one URL, pre-compressed responses, and a password.

If you have no preference, do :ref:`tutorial-github-pages`. It is the fastest route to a
working index, and everything the other two do is a variation on it.
