"""Tells pytest which files under ``src/`` it must NOT import while collecting doctests.

What this module does
---------------------
``pyproject.toml`` runs pytest with ``--doctest-modules`` over ``src/``. That flag makes pytest
**import every module** so it can find the ``>>>`` examples in docstrings. Some modules must never
be imported that way. This file lists them in ``collect_ignore`` / ``collect_ignore_glob``,
which pytest reads from any ``conftest.py``.

Why it exists
-------------
Decision D-055 and spec M0 §6.19:

- ``cartographer/__main__.py`` runs the whole CLI at import time (that's its job, see its
  docstring). Importing it would call ``main()`` and end with ``SystemExit`` during collection.
- ``cartographer/adapters/*`` (arrives in C5) needs ``string.templatelib``, which exists only on
  Python 3.14+. On 3.13 importing those modules fails, so they are skipped there.
- ``cartographer/depdiff/sandbox/*`` (arrives in C6) contains scripts that run **only inside the
  Docker sandbox**. They install audit hooks and read stdin. They are never imported on the host,
  not even by pytest.

Python concepts used here
-------------------------
- How importing runs code (docs/learn/concepts/how-python-runs-code.md): importing a module
  executes its top level, which is exactly why some modules can't be imported casually.
- pytest's ``conftest.py`` files (docs/learn/concepts/testing-with-pytest.md).

How to read this file
---------------------
Two lists, built from the interpreter version. Paths are relative to this file's folder (``src/``).
"""

import sys

#: Exact files pytest must not import.
collect_ignore: list[str] = ["cartographer/__main__.py"]

#: Glob patterns pytest must not import.
collect_ignore_glob: list[str] = ["cartographer/depdiff/sandbox/*"]

if sys.version_info < (3, 14):
    collect_ignore_glob.append("cartographer/adapters/*")
