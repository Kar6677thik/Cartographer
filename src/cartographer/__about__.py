"""The single place where Cartographer's version number lives.

What this module does
---------------------
Defines ``__version__``, a plain string such as ``"0.0.1"``. Nothing else.

Why it exists
-------------
Decision D-010 says the version must live in exactly one place. Two places would sooner or
later disagree. The build backend (hatchling, D-033) reads this file *as text* with a regular
expression (``[tool.hatch.version] path = ...`` in ``pyproject.toml``) to stamp the wheel's
metadata. ``cartographer --version`` imports it at runtime. Both see the same string.

Python concepts used here
-------------------------
- Module-level "dunder" names (docs/learn/concepts/how-python-runs-code.md): ``__version__``
  is only a convention, not something Python itself treats specially.

How to read this file
---------------------
There is one line of code. Keep it a simple ``__version__ = "x.y.z"`` assignment, because
hatchling's text matcher would not understand anything cleverer (an f-string, a function call).
"""

__version__ = "0.0.1"
