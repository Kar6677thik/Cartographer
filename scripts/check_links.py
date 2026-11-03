"""Check that relative links (and ``#anchors``) in the repo's Markdown files resolve.

Usage::

    uv run python scripts/check_links.py [--root DIR]

Spec 04 §8 and M0 §6.18. The docs are a big web of cross-references ("see D-018", "read
``ast-basics``"), and a broken link is a dead end for a learner. For every ``*.md`` file this
script finds inline links ``[text](target)`` and images ``![alt](target)`` and checks that:

- a relative path exists (resolved from the Markdown file's own folder), and
- a ``#fragment`` matches a heading in the target file, using GitHub's rules for turning a
  heading into an anchor: lowercase; keep only letters, digits, spaces, ``-`` and ``_``;
  spaces become ``-``; repeated headings get ``-1``, ``-2``, ….

Not checked: external links (``http:``, ``https:``, ``mailto:``), which would need the network.
Ignored: anything inside fenced code blocks or inline code, because examples aren't links.

Skipped folders: dot-folders (``.git``, ``.venv``, caches), ``.corpus``, ``build``, ``dist``,
``tests/fixtures`` (data) and ``docs/templates`` (their links are written relative to where a
*copy* of the template will live, so they can't resolve in place).

Exit code 0 when every link resolves, 1 otherwise. Problems print as ``file:line: …``.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections.abc import Iterator, Sequence
from pathlib import Path
from urllib.parse import unquote

#: An inline link or image: ``[text](target)`` / ``![alt](target)``. Nested brackets aren't
#: needed in our docs, so the simple form is enough.
LINK = re.compile(r"!?\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")

#: Inline code spans (one or two backticks), removed before looking for links.
INLINE_CODE = re.compile(r"``.*?``|`[^`\n]*`")

#: An ATX heading: ``## Title``.
HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")

#: Link targets with a URL scheme are external and not checked.
EXTERNAL = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*:")

#: Folders skipped entirely (relative posix paths from the root).
SKIP_PREFIXES = ("tests/fixtures", "docs/templates", "build", "dist")


def markdown_files(root: Path) -> Iterator[Path]:
    """Yield the Markdown files to check, sorted, skipping the folders listed above."""
    for path in sorted(root.rglob("*.md")):
        rel = path.relative_to(root).as_posix()
        parts = rel.split("/")
        if any(part.startswith(".") for part in parts[:-1]):
            continue
        if any(rel == p or rel.startswith(p + "/") for p in SKIP_PREFIXES):
            continue
        yield path


def prose_lines(text: str) -> Iterator[tuple[int, str]]:
    r"""Yield ``(line_number, line)`` for lines outside fenced code blocks.

    A fence starts with three or more backticks or tildes and ends with the same character.

    Example:
        >>> [n for n, _ in prose_lines("a\n```\nb\n```\nc")]
        [1, 5]
    """
    fence: str | None = None
    for number, line in enumerate(text.split("\n"), start=1):
        stripped = line.lstrip()
        marker = stripped[:3]
        if fence is None and marker in ("```", "~~~"):
            fence = marker[0]
            continue
        if fence is not None:
            if stripped.startswith(fence * 3):
                fence = None
            continue
        yield number, line


def slugify(heading: str) -> str:
    """Turn heading text into a GitHub-style anchor (without duplicate numbering).

    Markdown links inside the heading count only by their text; backticks and other
    punctuation are dropped.

    Example:
        >>> slugify("6. Safety model (important, read this)")
        '6-safety-model-important-read-this'
        >>> slugify("6.7 `core/selection.py`")
        '67-coreselectionpy'
    """
    text = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", heading)
    text = text.strip().lower()
    text = re.sub(r"[^\w\- ]", "", text)
    return text.replace(" ", "-")


def anchors(text: str) -> set[str]:
    """Return every anchor a Markdown document defines, with ``-1``/``-2`` duplicate suffixes."""
    seen: dict[str, int] = {}
    result: set[str] = set()
    for _, line in prose_lines(text):
        match = HEADING.match(line)
        if not match:
            continue
        slug = slugify(match.group(2))
        count = seen.get(slug, 0)
        seen[slug] = count + 1
        result.add(slug if count == 0 else f"{slug}-{count}")
    return result


def links(text: str) -> Iterator[tuple[int, str]]:
    """Yield ``(line, target)`` for every inline link outside code."""
    for number, line in prose_lines(text):
        for match in LINK.finditer(INLINE_CODE.sub("", line)):
            yield number, match.group(1).strip("<>")


def check(root: Path) -> list[str]:
    """Return one message per broken link under ``root`` (empty list = all good)."""
    cache: dict[Path, set[str]] = {}

    def anchors_of(path: Path) -> set[str]:
        if path not in cache:
            cache[path] = anchors(path.read_text(encoding="utf-8"))
        return cache[path]

    problems: list[str] = []
    for md in markdown_files(root):
        rel = md.relative_to(root).as_posix()
        for line, target in links(md.read_text(encoding="utf-8")):
            if EXTERNAL.match(target):
                continue
            path_part, _, fragment = target.partition("#")
            destination = (md.parent / unquote(path_part)).resolve() if path_part else md
            if path_part and not destination.exists():
                problems.append(f"{rel}:{line}: broken link {target} (no such file)")
                continue
            if (
                fragment
                and destination.suffix == ".md"
                and destination.is_file()
                and fragment not in anchors_of(destination)
            ):
                problems.append(f"{rel}:{line}: broken link {target} (no heading #{fragment})")
    return problems


def main(argv: Sequence[str] | None = None) -> int:
    """Run the check and print problems. Returns the exit code."""
    parser = argparse.ArgumentParser(description="Check relative Markdown links.")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent)
    ns = parser.parse_args(argv)
    problems = check(ns.root.resolve())
    for problem in problems:
        print(problem)
    if problems:
        print(f"{len(problems)} broken link(s).", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
