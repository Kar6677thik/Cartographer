"""The shared foundation every Cartographer feature is built on.

What this module does
---------------------
``cartographer.core`` is a *package*: a folder of modules. This ``__init__`` file deliberately
imports nothing, so ``import cartographer.core.versions`` loads only ``versions``, not every
core module.

Why it exists
-------------
Spec 02 §3 (layering): ``core`` sits at the bottom. It may import only the standard library and
other ``core`` modules, never a feature package (``graph``, ``rules``, …) and never the CLI.
That keeps it reusable and testable on its own. By the end of M0 it will hold the data model
(diagnostics, results), configuration loading, file discovery and source parsing.

Python concepts used here
-------------------------
- Packages and ``__init__.py`` (docs/learn/concepts/project-layout-and-pyproject.md).

How to read this file
---------------------
There's nothing here on purpose. Open the individual modules instead, starting with
``versions.py``.
"""
