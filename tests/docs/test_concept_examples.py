"""Every interactive example in the concept notes actually runs (spec 04 §2.1, §8).

A concept note that shows ``>>> len("é".encode())`` followed by ``2`` makes a promise. This test
keeps it. For each ``docs/learn/concepts/*.md`` file it:

1. extracts every fenced code block whose language is ``pycon`` (a Python console session);
2. skips a block whose first line is ``# Python 3.N+`` when the running Python is older;
3. runs the blocks **in order, sharing one namespace per note** (so a later block can use a
   name defined earlier, like a real REPL session) with the standard ``doctest`` module;
4. fails with doctest's own report if any output differs.

``ELLIPSIS`` lets an example write ``...`` for output that varies (addresses, paths), and
``NORMALIZE_WHITESPACE`` ignores differences in spacing.
"""

from __future__ import annotations

import doctest
import io
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
CONCEPTS = ROOT / "docs" / "learn" / "concepts"
NOTES = sorted(CONCEPTS.glob("*.md"))

FENCE_OPEN = re.compile(r"^```pycon\s*$")
VERSION_GATE = re.compile(r"^#\s*Python\s+(\d+)\.(\d+)\+")
FLAGS = doctest.ELLIPSIS | doctest.NORMALIZE_WHITESPACE


def pycon_blocks(text: str) -> list[tuple[int, str]]:
    """Return ``(first_line_number, block_text)`` for every ```` ```pycon ```` block."""
    blocks: list[tuple[int, str]] = []
    lines = text.split("\n")
    i = 0
    while i < len(lines):
        if FENCE_OPEN.match(lines[i]):
            start = i + 1
            j = start
            while j < len(lines) and not lines[j].startswith("```"):
                j += 1
            blocks.append((start + 1, "\n".join(lines[start:j]) + "\n"))
            i = j
        i += 1
    return blocks


def too_new(block: str) -> str | None:
    """Return a skip reason if the block is gated to a newer Python, else ``None``."""
    first = block.lstrip("\n").split("\n", 1)[0]
    match = VERSION_GATE.match(first)
    if match and sys.version_info[:2] < (int(match.group(1)), int(match.group(2))):
        return f"needs Python {match.group(1)}.{match.group(2)}"
    return None


@pytest.mark.parametrize("note", NOTES, ids=lambda p: p.stem)
def test_concept_note_examples_run(note: Path) -> None:
    """All pycon examples in one note produce exactly the output the note shows."""
    globs: dict[str, object] = {"__name__": f"concept_{note.stem.replace('-', '_')}"}
    parser = doctest.DocTestParser()
    runner = doctest.DocTestRunner(optionflags=FLAGS)
    report = io.StringIO()
    for lineno, block in pycon_blocks(note.read_text(encoding="utf-8")):
        if too_new(block):
            continue
        test = parser.get_doctest(block, globs, f"{note.name}:{lineno}", str(note), lineno)
        runner.run(test, out=report.write, clear_globs=False)
        # DocTest works on a *copy* of the globals it was given, so carry the names this block
        # defined into the shared namespace for the next block (like one long REPL session).
        globs.update(test.globs)
    result = runner.summarize(verbose=False)
    assert result.failed == 0, report.getvalue()


def test_block_extraction_and_version_gates() -> None:
    """T-M0-26: the extractor finds only pycon blocks and honours ``# Python 3.N+`` gates."""
    text = (
        "intro\n```pycon\n>>> 1 + 1\n2\n```\n"
        "```python\nx = 1\n```\n"
        "```pycon\n# Python 9.9+\n>>> x\n```\n"
    )
    blocks = pycon_blocks(text)
    assert [b for _, b in blocks] == [">>> 1 + 1\n2\n", "# Python 9.9+\n>>> x\n"]
    assert too_new(blocks[0][1]) is None
    assert too_new(blocks[1][1]) == "needs Python 9.9"
