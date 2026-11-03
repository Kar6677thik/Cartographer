"""Entry point of the ``cartographer`` / ``carto`` commands (minimal phase-1 version).

What this module does
---------------------
``main(argv)`` reads the command-line arguments, does what they ask, and **returns** an integer
exit code (0 = success, 2 = usage error, …; spec 03 §3). In phase 1 of M0 the only working
feature is ``--version``. Every subcommand (``scan``, ``explain``, then one per milestone) is
added in phase 4 by registering a command module.

Why it exists
-------------
``pyproject.toml`` declares two console scripts, ``cartographer`` and ``carto``, both pointing at
``cartographer.cli.main:main`` (D-054). When you install the package, the installer generates a
tiny launcher program (on Windows, ``cartographer.exe`` in the venv's ``Scripts`` folder) that
imports this module and runs ``sys.exit(main())``.

``main`` itself never calls ``sys.exit``. A function that exits the process can't be tested
easily: calling it inside pytest would end the test run. Returning the code instead means a
test can write ``assert main(["--version"]) == 0``.

Python concepts used here
-------------------------
- ``argparse`` (docs/learn/concepts/cli-with-argparse.md, written in phase 4): the standard
  library's command-line parser.
- ``SystemExit`` (docs/learn/concepts/how-python-runs-code.md): argparse ends the program on
  ``--version`` or on bad input by raising ``SystemExit``; we catch it and return its code.
- Lazy imports (docs/learn/concepts/how-python-runs-code.md): heavy modules are imported inside
  functions, so ``--version`` stays fast (spec M0 §6.17, "import discipline").

How to read this file
---------------------
Start at ``main()`` at the bottom. It calls ``build_parser()`` and converts argparse's
``SystemExit`` into a return value with ``_exit_code()``.
"""

import argparse
import sys
from collections.abc import Sequence

from cartographer.__about__ import __version__

#: The program name shown in help and errors, whether you typed ``cartographer`` or ``carto``.
PROG = "cartographer"


def version_string() -> str:
    """Build the text printed by ``cartographer --version`` (spec M0 §5.1).

    Returns:
        For example ``"cartographer 0.0.1 (Python 3.15.2, win32)"``, or
        ``"cartographer 0.0.1 (Python 3.15.2, free-threaded, linux)"`` on a free-threaded build.
    """
    # Imported here, not at the top, to follow the import discipline of spec M0 §6.17: this
    # module's top level imports only argparse, sys, collections.abc and __about__.
    from cartographer.core.versions import python_description

    return f"{PROG} {__version__} (Python {python_description()}, {sys.platform})"


def build_parser() -> argparse.ArgumentParser:
    """Create the root argument parser.

    In phase 1 the parser knows only ``--version`` and an (empty) set of subcommands.
    Phase 4 adds the global options from spec 03 §1.1 and registers each command module.

    Returns:
        A configured :class:`argparse.ArgumentParser`.
    """
    parser = argparse.ArgumentParser(
        prog=PROG,
        description="Map an unfamiliar Python codebase. See docs/README.md for everything.",
    )
    # CONCEPT(how-python-runs-code): action="version" prints the string to stdout and raises
    # SystemExit(0) while parse_args() is still running, so nothing after parsing happens.
    parser.add_argument("--version", action="version", version=version_string())
    # `required=True` makes "no command given" an error (exit 2) instead of silently doing
    # nothing. `metavar` controls how the placeholder appears in the usage line.
    parser.add_subparsers(dest="command", metavar="command", required=True)
    return parser


def _exit_code(exc: SystemExit) -> int:
    """Turn the payload of a ``SystemExit`` into an integer exit code.

    ``SystemExit.code`` can be ``None`` (meaning success), an ``int``, or any other object (Python
    prints it to stderr and uses exit code 1). argparse always uses ``0`` or ``2``, but handling
    every case keeps this helper honest.

    Args:
        exc: The exception argparse raised.

    Returns:
        The exit code the process would have ended with.

    Example:
        >>> _exit_code(SystemExit(2))
        2
        >>> _exit_code(SystemExit(None))
        0
        >>> _exit_code(SystemExit("message"))
        1
    """
    if exc.code is None:
        return 0
    if isinstance(exc.code, int):
        return exc.code
    return 1


def main(argv: Sequence[str] | None = None) -> int:
    """Run Cartographer with the given arguments and return the exit code.

    Args:
        argv: The arguments *after* the program name, e.g. ``["--version"]``. ``None`` means
            "use ``sys.argv[1:]``", which is what the console script does.

    Returns:
        The process exit code (spec 03 §3).
    """
    parser = build_parser()
    try:
        parser.parse_args(argv)
    except SystemExit as exc:
        return _exit_code(exc)
    # In phase 1 no subcommands exist, so argparse always exits above: either --version (0) or
    # "the following arguments are required: command" (2). Phase 4 replaces this with dispatch.
    return 0  # pragma: no cover
