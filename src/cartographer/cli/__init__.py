"""The command-line interface: turns what you type into calls to ``cartographer.api``.

What this module does
---------------------
``cartographer.cli`` is the package holding the command-line layer. ``main.py`` builds the
argument parser and dispatches to one module per subcommand (``cli/commands/``, from phase 4 of
M0). This ``__init__`` file is empty on purpose: importing it must cost nothing.

Why it exists
-------------
Decision D-031 keeps analysis out of the CLI. This package parses arguments, prints results
and chooses exit codes (spec 03 §3), and nothing else. Keeping it separate means the same
features can be used from Python code via ``cartographer.api``.

Python concepts used here
-------------------------
- Packages and ``__init__.py`` (docs/learn/concepts/project-layout-and-pyproject.md).

How to read this file
---------------------
Open ``main.py``. It's the entry point for the ``cartographer`` and ``carto`` commands.
"""
