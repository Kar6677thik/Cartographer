"""Shared pytest configuration for Cartographer's test suite (spec M0 §6.19, spec 05 §3).

pytest automatically loads a file named ``conftest.py`` before collecting the tests next to it,
and everything defined here (fixtures, hooks, settings) applies to every test below this folder.
See docs/learn/concepts/testing-with-pytest.md.

What lives here:

- **Hypothesis profiles** ``dev`` / ``ci`` / ``thorough`` (how many random examples each property
  test tries), selected with the ``HYPOTHESIS_PROFILE`` environment variable.
- **Collection rules:** fixture projects under ``tests/fixtures/`` are *data* and must never be
  imported. Test files written in newer syntax (``test_*_py314.py``, ``test_*_py315.py``) are
  skipped on interpreters that couldn't even parse them (spec 05 §3.1).
- **Version markers:** ``@pytest.mark.requires_py314`` / ``requires_py315`` skip a test on older
  Pythons, with a reason that names both versions.
- **Helpers:** ``ROOT`` (the repo root) and the ``load_script`` fixture, which imports one of the
  files in ``scripts/`` so its functions can be tested directly.

The golden-file helper and ``--update-golden`` arrive in M0 phase 4.
"""

from __future__ import annotations

import importlib.util
import os
import sys
from collections.abc import Callable
from pathlib import Path
from types import ModuleType

import pytest
from hypothesis import settings

#: The repository root (this file is ``<root>/tests/conftest.py``).
ROOT = Path(__file__).resolve().parent.parent

# pytester lets a test run pytest itself on a throwaway folder (used by T-M0-34).
pytest_plugins = ["pytester"]

# --------------------------------------------------------------------------- collection rules

#: Paths (relative to this folder) pytest must not import. Fixture projects are data, and many
#: are deliberately broken, so importing them would fail or, worse, run their code.
collect_ignore_glob: list[str] = ["fixtures/*"]

if sys.version_info < (3, 14):
    collect_ignore_glob.append("**/test_*_py314.py")
if sys.version_info < (3, 15):
    collect_ignore_glob.append("**/test_*_py315.py")

# --------------------------------------------------------------------------- Hypothesis profiles

# CONCEPT(testing-with-pytest): a Hypothesis "profile" is a named bundle of settings. `ci` tries
# more examples than `dev` and switches off the per-example deadline, because shared CI machines
# are slow and noisy. Choose one with HYPOTHESIS_PROFILE=ci.
settings.register_profile("dev", max_examples=100)
settings.register_profile("ci", max_examples=500, deadline=None, print_blob=True)
settings.register_profile("thorough", max_examples=5000, deadline=None)
settings.load_profile(os.environ.get("HYPOTHESIS_PROFILE", "dev"))

# --------------------------------------------------------------------------- version markers

_VERSION_MARKERS = {"requires_py314": (3, 14), "requires_py315": (3, 15)}


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Skip tests marked ``requires_py3NN`` when the running Python is too old."""
    running = sys.version_info[:2]
    for item in items:
        for marker, needed in _VERSION_MARKERS.items():
            if item.get_closest_marker(marker) and running < needed:
                reason = f"needs Python {needed[0]}.{needed[1]} (running {running[0]}.{running[1]})"
                item.add_marker(pytest.mark.skip(reason=reason))


# --------------------------------------------------------------------------- helpers


@pytest.fixture
def load_script() -> Callable[[str], ModuleType]:
    """Return a function that imports ``scripts/<name>.py`` as a module.

    ``scripts/`` is not a package, so ``import scripts.dev`` wouldn't work. Instead we load the
    file by path with ``importlib.util``. That's the same machinery ``import`` uses internally.
    """

    def _load(name: str) -> ModuleType:
        path = ROOT / "scripts" / f"{name}.py"
        spec = importlib.util.spec_from_file_location(f"_cartographer_script_{name}", path)
        assert spec is not None
        assert spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        # Registering the module before running it lets dataclasses (and anything else that
        # looks itself up in sys.modules) work inside the script.
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        return module

    return _load
