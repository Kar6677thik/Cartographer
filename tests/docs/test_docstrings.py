"""Every module and public definition under ``src/`` is documented (spec 04 §3.1-3.2, §8).

These rules make the teaching documentation *enforced* rather than hoped for (D-028):

1. Every ``.py`` file under ``src/`` starts with a module docstring containing the headings
   ``What this module does``, ``Why it exists`` and ``Python concepts used here``.
2. Every public function, method and class (name not starting with ``_``) has a docstring.
3. Every private function or method longer than 10 lines has a docstring too.
4. Dunder methods (``__init__``, ``__repr__`` …) are exempt: their meaning is standard.

The check parses each file with ``ast``. That reads the code without running it, which is the
same safe technique Cartographer itself uses (docs/learn/concepts/ast-basics.md, phase 3).
"""

from __future__ import annotations

import ast
from collections.abc import Iterator
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
REQUIRED_HEADINGS = ("What this module does", "Why it exists", "Python concepts used here")
PRIVATE_LINE_LIMIT = 10

type Definition = ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef

SOURCE_FILES = sorted(SRC.rglob("*.py"))


def _definitions(body: list[ast.stmt], prefix: str = "") -> Iterator[tuple[str, Definition]]:
    """Yield ``(qualified_name, node)`` for module-level and class-level definitions."""
    for node in body:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            name = f"{prefix}{node.name}"
            yield name, node
            if isinstance(node, ast.ClassDef):
                yield from _definitions(node.body, prefix=f"{name}.")


def problems_in(path: Path) -> list[str]:
    """Return a human-readable list of documentation problems in one source file."""
    rel = path.relative_to(ROOT).as_posix()
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=rel)
    problems: list[str] = []
    module_doc = ast.get_docstring(tree) or ""
    if not module_doc:
        problems.append(f"{rel}: missing module docstring")
    for heading in REQUIRED_HEADINGS:
        if module_doc and heading not in module_doc:
            problems.append(f"{rel}: module docstring lacks the heading {heading!r}")
    for name, node in _definitions(tree.body):
        short = name.rsplit(".", 1)[-1]
        if short.startswith("__") and short.endswith("__"):
            continue
        if ast.get_docstring(node):
            continue
        length = (node.end_lineno or node.lineno) - node.lineno + 1
        if not short.startswith("_"):
            problems.append(f"{rel}:{node.lineno}: public {name} has no docstring")
        elif length > PRIVATE_LINE_LIMIT:
            problems.append(
                f"{rel}:{node.lineno}: private {name} is {length} lines but has no docstring"
            )
    return problems


@pytest.mark.parametrize("path", SOURCE_FILES, ids=lambda p: p.relative_to(SRC).as_posix())
def test_source_file_is_documented(path: Path) -> None:
    """Each file under src/ satisfies the four rules in this module's docstring."""
    assert problems_in(path) == []


def test_the_checker_catches_missing_documentation(tmp_path: Path) -> None:
    """T-M0-26: the check itself fails on a badly documented file (a test of the test)."""
    bad = ROOT / "src" / "_tmp_doc_check_probe.py"
    try:
        bad.write_text(
            '"""Only a summary."""\n\n'
            "def public():\n    pass\n\n"
            "def _long():\n" + "    x = 1\n" * 11 + "\n"
            "class Thing:\n    def __repr__(self):\n        return 'x'\n",
            encoding="utf-8",
        )
        found = problems_in(bad)
    finally:
        bad.unlink()
    assert any("lacks the heading 'Why it exists'" in p for p in found)
    assert any("public public has no docstring" in p for p in found)
    assert any("private _long is 12 lines" in p for p in found)
    assert any("public Thing has no docstring" in p for p in found)
    assert not any("__repr__" in p for p in found)
