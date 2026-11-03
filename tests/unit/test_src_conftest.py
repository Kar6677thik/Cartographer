"""T-M0-34: ``src/conftest.py`` keeps risky or version-specific modules out of doctests.

D-055 / spec M0 §6.19. We copy the real ``src/conftest.py`` into a throwaway folder next to fake
modules that **raise an error the moment they're imported**, then run pytest with
``--doctest-modules`` on that folder:

- ``cartographer/__main__.py`` and ``cartographer/depdiff/sandbox/probe.py`` must *never* be
  imported, on any Python version.
- ``cartographer/adapters/sql.py`` must be skipped on 3.13, and collected on 3.14+.

``runpytest_subprocess`` runs that inner pytest in a separate process, so its fake
``cartographer`` package can't collide with the real one already imported in this process.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

#: Repo root: this file is ``<root>/tests/unit/test_src_conftest.py``.
ROOT = Path(__file__).resolve().parents[2]

pytestmark = pytest.mark.slow


def _write(pytester: pytest.Pytester, relpath: str, text: str) -> None:
    path = pytester.path / relpath
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_src_conftest_ignores_main_sandbox_and_old_python_adapters(
    pytester: pytest.Pytester,
) -> None:
    conftest = (ROOT / "src" / "conftest.py").read_text(encoding="utf-8")
    _write(pytester, "conftest.py", conftest)
    explode = 'raise RuntimeError("this module must never be imported by pytest")\n'
    _write(pytester, "cartographer/__main__.py", explode)
    _write(pytester, "cartographer/depdiff/sandbox/probe.py", explode)
    _write(
        pytester,
        "cartographer/adapters/sql.py",
        "import sys\n"
        "if sys.version_info < (3, 14):\n"
        '    raise ImportError("adapters need Python 3.14+")\n'
        "def f():\n"
        '    """\n'
        "    >>> 1 + 1\n"
        "    2\n"
        '    """\n',
    )
    _write(pytester, "cartographer/ok.py", 'def g():\n    """\n    >>> 2 * 2\n    4\n    """\n')

    result = pytester.runpytest_subprocess(
        "--doctest-modules", "--import-mode=importlib", "-p", "no:cacheprovider"
    )

    expected_passed = 2 if sys.version_info >= (3, 14) else 1
    result.assert_outcomes(passed=expected_passed, errors=0)
