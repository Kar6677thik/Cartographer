"""Check that every ``CONCEPT(slug)`` comment points to an existing concept note.

Usage::

    uv run python scripts/check_concepts.py [--root DIR]

Spec 04 §3.3: the first time a file uses a Python feature a beginner wouldn't know, the code
carries a comment like ``# CONCEPT(descriptors-and-cached-property): ...``. The slug must name a
file ``docs/learn/concepts/<slug>.md``. Otherwise the comment promises an explanation that
doesn't exist. This script finds every such comment and reports the ones without a note.

Why ``tokenize`` and not a regular expression over each line: a regex can't tell a comment from
text inside a string. With ``x = "# CONCEPT(nope)"``, a line-based regex would complain about a
comment that doesn't exist. The tokenizer knows exactly which characters are a ``COMMENT``
token. (Concept note: ``tokenize-and-comments``.)

Exit code 0 when everything resolves, 1 otherwise. Each problem is printed as
``path:line: CONCEPT(<slug>) has no docs/learn/concepts/<slug>.md``.
"""

from __future__ import annotations

import argparse
import io
import re
import sys
import tokenize
from collections.abc import Iterator, Sequence
from pathlib import Path

#: Matches the tag inside a comment token: the word CONCEPT, then a slug in parentheses.
TAG = re.compile(r"CONCEPT\(([a-z0-9][a-z0-9-]*)\)")

#: Folders (relative to the root) whose Python files are scanned.
SCANNED = ("src", "tests", "scripts")

#: Folders never scanned: fixture projects are *data*, sometimes deliberately broken.
SKIPPED = ("tests/fixtures",)


def python_files(root: Path) -> Iterator[Path]:
    """Yield every ``.py`` file under the scanned folders, in sorted order."""
    skipped = [root / s for s in SKIPPED]
    for folder in SCANNED:
        base = root / folder
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*.py")):
            if any(path.is_relative_to(s) for s in skipped):
                continue
            yield path


def concept_tags(source: str) -> Iterator[tuple[int, str]]:
    r"""Yield ``(line, slug)`` for every ``CONCEPT(slug)`` inside a *comment* token.

    Example:
        >>> list(concept_tags('x = "# CONCEPT(no)"  # CONCEPT(yes)\n'))
        [(1, 'yes')]
    """
    try:
        for token in tokenize.generate_tokens(io.StringIO(source).readline):
            if token.type == tokenize.COMMENT:
                for match in TAG.finditer(token.string):
                    yield token.start[0], match.group(1)
    except (tokenize.TokenError, SyntaxError):
        # A file that doesn't tokenize is reported by other checks (ruff, the test suite).
        return


def check(root: Path) -> list[str]:
    """Return one message per unresolved tag under ``root`` (empty list = all good)."""
    concepts = root / "docs" / "learn" / "concepts"
    problems: list[str] = []
    for path in python_files(root):
        text = path.read_text(encoding="utf-8")
        for line, slug in concept_tags(text):
            if not (concepts / f"{slug}.md").is_file():
                rel = path.relative_to(root).as_posix()
                problems.append(
                    f"{rel}:{line}: CONCEPT({slug}) has no docs/learn/concepts/{slug}.md"
                )
    return problems


def main(argv: Sequence[str] | None = None) -> int:
    """Run the check and print problems. Returns the exit code."""
    parser = argparse.ArgumentParser(description="Check CONCEPT(slug) comments.")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent)
    ns = parser.parse_args(argv)
    problems = check(ns.root.resolve())
    for problem in problems:
        print(problem)
    if problems:
        print(f"{len(problems)} unresolved CONCEPT tag(s).", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
