"""Facts about the Python interpreter that is running Cartographer.

What this module does
---------------------
Answers questions such as "which Python version is this?" and "is this the free-threaded
build?", and formats them for ``cartographer --version``. In phase 3 of M0 it grows the
``requires-python`` parser and the "this file needs a newer Python" hint (spec M0 §6.12).

Why it exists
-------------
Decision D-004: Cartographer runs on 3.13, 3.14, 3.15 and 3.15t, and it can only parse syntax
the *running* interpreter understands. Several features therefore need to know exactly what
they're running on. Keeping those checks in one module means the rest of the code asks
``versions.HAS_TEMPLATELIB`` instead of scattering ``sys.version_info`` comparisons around.

Python concepts used here
-------------------------
- ``sys.version_info`` and ``sysconfig`` (docs/learn/concepts/how-python-runs-code.md): what
  the interpreter knows about itself.
- Free-threaded builds (docs/learn/glossary.md, "Free-threaded build"): CPython compiled
  without the GIL. ``sysconfig.get_config_var("Py_GIL_DISABLED")`` is ``1`` on those builds.

How to read this file
---------------------
Three constants at the top, then ``python_description()``, which ``--version`` uses.
"""

import sys
import sysconfig

#: ``(major, minor)`` of the running interpreter, e.g. ``(3, 15)``.
RUNNING: tuple[int, int] = (sys.version_info.major, sys.version_info.minor)

#: ``True`` on a free-threaded ("t") build such as ``python3.15t``.
# CONCEPT(how-python-runs-code): a build's compile-time options are recorded by `sysconfig`.
# `Py_GIL_DISABLED` is 1 only when CPython was compiled without the GIL. It says nothing about
# whether the GIL is *currently* off (an extension can turn it back on at runtime; for that,
# see `sys._is_gil_enabled()`).
FREE_THREADED: bool = sysconfig.get_config_var("Py_GIL_DISABLED") == 1

#: ``True`` when ``string.templatelib`` (PEP 750 t-strings) exists, i.e. Python 3.14+.
HAS_TEMPLATELIB: bool = RUNNING >= (3, 14)


def python_description(
    version: tuple[int, int, int] | None = None, *, free_threaded: bool | None = None
) -> str:
    """Describe the running Python for ``cartographer --version``.

    The format is fixed by spec M0 §5.1: the dotted version, followed by
    ``", free-threaded"`` on free-threaded builds.

    Args:
        version: ``(major, minor, micro)`` to describe. Defaults to the running interpreter.
            Tests pass explicit values so they don't depend on which Python runs them.
        free_threaded: Override for the build type. Defaults to :data:`FREE_THREADED`.

    Returns:
        A string such as ``"3.15.2"`` or ``"3.15.2, free-threaded"``.

    Example:
        >>> python_description((3, 15, 2), free_threaded=False)
        '3.15.2'
        >>> python_description((3, 15, 2), free_threaded=True)
        '3.15.2, free-threaded'
    """
    if version is None:
        version = (sys.version_info.major, sys.version_info.minor, sys.version_info.micro)
    if free_threaded is None:
        free_threaded = FREE_THREADED
    text = ".".join(str(part) for part in version)
    return f"{text}, free-threaded" if free_threaded else text
