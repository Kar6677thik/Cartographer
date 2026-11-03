"""The most basic CLI behaviour: ``--version`` and "no command given" (spec M0 §5.1, §5.6).

Covers T-M0-19 (version format; identical output from all three entry points) and the
"No command" row of the M0 §5.6 error table. The rest of T-M0-19/T-M0-21 arrives with the full
CLI in M0 phase 4.
"""

from __future__ import annotations

import re
import runpy
import subprocess
import sys
from pathlib import Path

import pytest

from cartographer import __version__
from cartographer.cli.main import main, version_string
from cartographer.core import versions

#: ``cartographer 0.0.1 (Python 3.15.2, win32)`` or ``(Python 3.15.2, free-threaded, linux)``.
VERSION_RE = re.compile(
    r"^cartographer \d+\.\d+\.\d+ \(Python \d+\.\d+\.\d+(, free-threaded)?, \S+\)$"
)


def test_version_flag_prints_version_to_stdout_and_returns_zero(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """T-M0-19: ``--version`` prints one line to stdout and exits 0 without killing pytest."""
    assert main(["--version"]) == 0
    out, err = capsys.readouterr()
    assert err == ""
    assert out == version_string() + "\n"
    assert VERSION_RE.match(out.strip())
    assert f"cartographer {__version__} " in out


def test_version_string_mentions_free_threaded_builds(monkeypatch: pytest.MonkeyPatch) -> None:
    """T-M0-19: on a free-threaded build the description gains ``, free-threaded``."""
    monkeypatch.setattr(versions, "FREE_THREADED", True)
    assert ", free-threaded, " in version_string()
    monkeypatch.setattr(versions, "FREE_THREADED", False)
    assert "free-threaded" not in version_string()


def test_no_command_is_a_usage_error(capsys: pytest.CaptureFixture[str]) -> None:
    """M0 §5.6 "No command": usage + error message on stderr, exit code 2."""
    assert main([]) == 2
    _, err = capsys.readouterr()
    assert err.startswith("usage: cartographer")
    assert "the following arguments are required: command" in err


def test_python_dash_m_runs_the_cli(monkeypatch: pytest.MonkeyPatch) -> None:
    """``python -m cartographer`` executes ``__main__.py``, which exits with main()'s code.

    ``runpy.run_module`` is what ``python -m`` uses internally, so running it in-process is a
    faithful (and coverage-visible) imitation.
    """
    monkeypatch.setattr(sys, "argv", ["cartographer", "--version"])
    with pytest.raises(SystemExit) as excinfo:
        runpy.run_module("cartographer", run_name="__main__", alter_sys=True)
    assert excinfo.value.code == 0


def _script(name: str) -> str:
    """Path of a console script installed next to the running interpreter."""
    folder = Path(sys.executable).parent
    candidates = [folder / f"{name}.exe", folder / name]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    pytest.skip(f"console script {name!r} not installed next to {sys.executable}")


def test_all_three_entry_points_print_the_same_version() -> None:
    """T-M0-19 / A-M0-02: ``cartographer``, ``carto`` and ``python -m cartographer`` agree."""
    commands = [
        [_script("cartographer"), "--version"],
        [_script("carto"), "--version"],
        [sys.executable, "-m", "cartographer", "--version"],
    ]
    outputs = []
    for command in commands:
        completed = subprocess.run(
            command, capture_output=True, text=True, encoding="utf-8", timeout=60, check=False
        )
        assert completed.returncode == 0, completed.stderr
        outputs.append(completed.stdout)
    assert outputs[0] == outputs[1] == outputs[2]
    assert VERSION_RE.match(outputs[0].strip())
