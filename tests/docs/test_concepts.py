"""``scripts/check_concepts.py``: CONCEPT tags must resolve to notes (spec 04 §3.3, T-M0-26).

The script is tested on small fake repositories built in ``tmp_path``, which proves it fails
when it should and passes when it should, and then on the real repository.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def check_concepts(load_script: Callable[[str], ModuleType]) -> ModuleType:
    return load_script("check_concepts")


def _repo(tmp_path: Path, code: str) -> Path:
    (tmp_path / "docs" / "learn" / "concepts").mkdir(parents=True)
    (tmp_path / "docs" / "learn" / "concepts" / "real-note.md").write_text("# x\n", "utf-8")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "mod.py").write_text(code, encoding="utf-8")
    return tmp_path


def test_resolving_tag_passes(check_concepts: ModuleType, tmp_path: Path) -> None:
    root = _repo(tmp_path, "x = 1  # CONCEPT(real-note): explained there\n")
    assert check_concepts.check(root) == []
    assert check_concepts.main(["--root", str(root)]) == 0


def test_missing_note_fails_with_location(check_concepts: ModuleType, tmp_path: Path) -> None:
    root = _repo(tmp_path, "\n# CONCEPT(no-such-note): oops\n")
    assert check_concepts.check(root) == [
        "src/mod.py:2: CONCEPT(no-such-note) has no docs/learn/concepts/no-such-note.md"
    ]
    assert check_concepts.main(["--root", str(root)]) == 1


def test_text_inside_strings_is_not_a_comment(check_concepts: ModuleType, tmp_path: Path) -> None:
    """The reason the script uses tokenize instead of a regex over raw lines."""
    root = _repo(tmp_path, 's = "# CONCEPT(no-such-note)"\n')
    assert check_concepts.check(root) == []


def test_fixture_projects_are_not_scanned(check_concepts: ModuleType, tmp_path: Path) -> None:
    root = _repo(tmp_path, "x = 1\n")
    fixture = root / "tests" / "fixtures" / "projects" / "p"
    fixture.mkdir(parents=True)
    (fixture / "a.py").write_text("# CONCEPT(no-such-note)\n", encoding="utf-8")
    assert check_concepts.check(root) == []


def test_real_repository_has_no_unresolved_tags(check_concepts: ModuleType) -> None:
    """A-M0-10: every CONCEPT(...) tag in this repo resolves."""
    assert check_concepts.check(ROOT) == []
