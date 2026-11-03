"""``scripts/check_links.py``: relative Markdown links and anchors resolve (spec 04 §8, T-M0-26)."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def check_links(load_script: Callable[[str], ModuleType]) -> ModuleType:
    return load_script("check_links")


def _write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_good_links_pass(check_links: ModuleType, tmp_path: Path) -> None:
    _write(tmp_path, "docs/b.md", "# Title\n## 6.7 `core/selection.py`\n## Same\n## Same\n")
    _write(
        tmp_path,
        "docs/a.md",
        "[b](b.md) [anchor](b.md#67-coreselectionpy) [dup](b.md#same-1) [self](#local)\n"
        "## Local\n[web](https://example.com) [mail](mailto:x@example.com)\n",
    )
    assert check_links.check(tmp_path) == []


def test_missing_file_and_missing_anchor_fail(check_links: ModuleType, tmp_path: Path) -> None:
    _write(tmp_path, "b.md", "# Real\n")
    _write(tmp_path, "a.md", "intro\n[x](nope.md)\n[y](b.md#unreal)\n")
    assert check_links.check(tmp_path) == [
        "a.md:2: broken link nope.md (no such file)",
        "a.md:3: broken link b.md#unreal (no heading #unreal)",
    ]
    assert check_links.main(["--root", str(tmp_path)]) == 1


def test_code_is_not_checked(check_links: ModuleType, tmp_path: Path) -> None:
    """Links inside fenced code blocks and inline code are examples, not links."""
    _write(tmp_path, "a.md", "```\n[x](nope.md)\n```\n`[y](nope.md)`\n~~~md\n[z](nope.md)\n~~~\n")
    assert check_links.check(tmp_path) == []


def test_templates_and_fixtures_are_skipped(check_links: ModuleType, tmp_path: Path) -> None:
    _write(tmp_path, "docs/templates/t.md", "[x](../../spec/<file>.md)\n")
    _write(tmp_path, "tests/fixtures/projects/p/README.md", "[x](nope.md)\n")
    _write(tmp_path, ".venv/lib/README.md", "[x](nope.md)\n")
    assert check_links.check(tmp_path) == []


def test_headings_inside_code_blocks_are_not_anchors(check_links: ModuleType) -> None:
    assert check_links.anchors("# Real\n```\n# Fake\n```\n") == {"real"}


def test_real_repository_has_no_broken_links(check_links: ModuleType) -> None:
    """A-M0-10: zero broken links across the repo's Markdown."""
    assert check_links.check(ROOT) == []
