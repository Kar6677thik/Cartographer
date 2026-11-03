"""The public library API of Cartographer (empty until the first command arrives).

What this module does
---------------------
This module will hold one function per feature: ``scan`` (M0 phase 4), ``build_import_graph``
(C1), ``profile_startup`` (C2), and so on. Each takes a project root plus options and returns a
:class:`Result`. Right now it exports nothing, because no analysis exists yet.

Why it exists
-------------
Decision D-031: the CLI is a *thin* layer over this module. The CLI parses arguments and prints
results, and it never analyses anything itself. That gives one obvious place to look for
"what can Cartographer do?", and it means the library (``import cartographer.api``) and the
command line can never disagree.

Decision D-046 adds a second job: this is the **only** place where diagnostics are filtered
(``select``/``ignore``/suppressions/severity overrides), exactly once per command. Analyzers
below this layer return *raw* findings, and the CLI above it prints what it's given.

Python concepts used here
-------------------------
- ``__all__`` (docs/learn/concepts/how-python-runs-code.md): the explicit list of public names.

How to read this file
---------------------
Nothing to read yet. In phase 4 of M0, ``scan()`` and the private ``_finish()`` filtering step
arrive (spec M0 §6.3).
"""

__all__: list[str] = []
