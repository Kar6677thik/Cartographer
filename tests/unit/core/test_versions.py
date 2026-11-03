"""Facts about the running interpreter (``cartographer.core.versions``, spec M0 §6.12).

Phase 1 covers only the constants and ``python_description``. The ``requires-python`` parser
and ``syntax_hint`` tests (T-M0-25) arrive in phase 3.
"""

from __future__ import annotations

import sys
import sysconfig

from cartographer.core import versions


def test_running_matches_sys_version_info() -> None:
    assert sys.version_info[:2] == versions.RUNNING


def test_free_threaded_matches_the_build_configuration() -> None:
    assert versions.FREE_THREADED is (sysconfig.get_config_var("Py_GIL_DISABLED") == 1)


def test_has_templatelib_matches_whether_the_module_exists() -> None:
    """``string.templatelib`` (PEP 750) exists exactly on Python 3.14 and later.

    We try the import instead of calling ``importlib.util.find_spec("string.templatelib")``.
    On 3.13 ``string`` is a plain *module*, not a package, and ``find_spec`` of a submodule of a
    non-package raises ``ModuleNotFoundError`` instead of returning ``None``. ``string`` only
    became a package in 3.14, when ``templatelib`` was added to it. (Found while writing this
    test; recorded in the M0 write-up.)
    """
    try:
        import string.templatelib  # noqa: F401  (imported only to see whether it exists)
    except ImportError:
        exists = False
    else:
        exists = True
    assert exists is versions.HAS_TEMPLATELIB


def test_python_description_defaults_to_the_running_interpreter() -> None:
    expected = ".".join(str(part) for part in sys.version_info[:3])
    description = versions.python_description()
    assert description.startswith(expected)
    assert description.endswith(", free-threaded") is versions.FREE_THREADED
