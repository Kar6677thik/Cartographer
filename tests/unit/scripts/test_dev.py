"""``scripts/dev.py``: the task runner builds the right commands and keeps going after failures.

Nothing here actually runs ruff, mypy or pytest. The ``run`` function is replaced
("monkeypatched") with a fake that records what *would* have run. That keeps the test fast and
shows how to test code that starts other programs.
"""

from __future__ import annotations

import sys
from collections.abc import Callable, Sequence
from types import ModuleType

import pytest


@pytest.fixture
def dev(load_script: Callable[[str], ModuleType]) -> ModuleType:
    return load_script("dev")


def test_commands_use_the_current_interpreter(dev: ModuleType) -> None:
    """Tools must come from the project's environment, never from whatever is on PATH."""
    assert dev.lint_commands() == [[sys.executable, "-m", "ruff", "check", "."]]
    assert dev.format_commands(check=True)[0][-2:] == ["--check", "."]


def test_test_gates_enforce_both_coverage_thresholds(dev: ModuleType) -> None:
    pytest_cmd, coverage_cmd = dev.test_commands(["-k", "x"], gates=True)
    assert "--cov-fail-under=85" in pytest_cmd
    assert pytest_cmd[-2:] == ["-k", "x"]
    assert coverage_cmd[-2:] == ["--include=*/cartographer/core/*", "--fail-under=90"]
    assert dev.test_commands([], gates=False) == [[sys.executable, "-m", "pytest"]]


def test_mypy_runs_for_315_and_for_the_313_floor(dev: ModuleType) -> None:
    first, second = dev.types_commands()
    assert first == [sys.executable, "-m", "mypy"]
    assert "--python-version" in second
    assert "3.13" in second


def test_all_runs_every_step_even_after_a_failure(
    dev: ModuleType, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    ran: list[Sequence[str]] = []

    def fake_run(args: Sequence[str]) -> int:
        ran.append(args)
        return 1 if "ruff" in args and "check" in args else 0

    monkeypatch.setattr(dev, "run", fake_run)
    assert dev.main(["all"]) == 1
    out = capsys.readouterr().out
    assert "lint             FAIL" in out
    assert "test --gates     PASS" in out
    assert any("pytest" in cmd for cmd in ran)
