"""Cartographer: maps unfamiliar Python codebases.

What this module does
---------------------
This is the package's ``__init__`` module. Python runs it the first time anything inside
``cartographer`` is imported (for example ``import cartographer.core.versions`` runs this file
first). It re-exports ``__version__`` so ``cartographer.__version__`` works, and nothing more.

Why it exists
-------------
A directory becomes a *regular package* by containing an ``__init__.py`` (see
docs/learn/concepts/project-layout-and-pyproject.md). Because this file runs on every import of
anything in the package, it must stay **tiny**: every line here slows down every command,
including ``cartographer --version`` (budget: under 150 ms, spec 05 §6).

Later milestones will offer convenient names such as ``cartographer.build_import_graph``
*without* importing the heavy feature code up front. The planned technique is a module-level
``__getattr__`` function (PEP 562): Python calls it only when an attribute is missing, so the
real import can happen on first use. It is not used yet, because there is nothing to re-export.

Python concepts used here
-------------------------
- Packages and ``__init__.py`` (docs/learn/concepts/project-layout-and-pyproject.md).
- ``__all__`` (docs/learn/concepts/how-python-runs-code.md): the list of public names, used by
  ``from cartographer import *`` and by documentation tools.

How to read this file
---------------------
Two statements: import the version, declare it public.
"""

from cartographer.__about__ import __version__

__all__ = ["__version__"]
