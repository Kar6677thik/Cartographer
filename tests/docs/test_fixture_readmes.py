"""Every fixture project explains itself in a README.md (spec 04 §3.5, §8).

A fixture project is a miniature fake repository under ``tests/fixtures/projects/<name>/`` (and,
from C6/C7, ``tests/fixtures/replicas/<name>/``). Without a README a learner can't tell *what*
it simulates or *which* findings a test expects from it.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FIXTURE_GROUPS = ("projects", "replicas")


def missing_readmes(fixtures: Path) -> list[str]:
    """Return the fixture folders (posix, relative to ``fixtures``) that lack a README.md."""
    missing: list[str] = []
    for group in FIXTURE_GROUPS:
        base = fixtures / group
        if not base.is_dir():
            continue
        for folder in sorted(p for p in base.iterdir() if p.is_dir()):
            if not (folder / "README.md").is_file():
                missing.append(folder.relative_to(fixtures).as_posix())
    return missing


def test_every_fixture_project_has_a_readme() -> None:
    assert missing_readmes(ROOT / "tests" / "fixtures") == []


def test_missing_readme_is_detected(tmp_path: Path) -> None:
    """T-M0-26: the check reports a fixture without a README and accepts one with it."""
    (tmp_path / "projects" / "with_readme").mkdir(parents=True)
    (tmp_path / "projects" / "with_readme" / "README.md").write_text("# ok\n", encoding="utf-8")
    (tmp_path / "projects" / "without").mkdir()
    assert missing_readmes(tmp_path) == ["projects/without"]
