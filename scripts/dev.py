"""Cross-platform task runner: one command runs everything CI runs.

Usage (from the repo root)::

    uv run python scripts/dev.py lint            # ruff check .
    uv run python scripts/dev.py format          # ruff format .   (add --check to only verify)
    uv run python scripts/dev.py types           # mypy, twice: for 3.15 and for the 3.13 floor
    uv run python scripts/dev.py test [ARGS...]  # pytest, passing ARGS through
    uv run python scripts/dev.py test --gates    # pytest with the coverage gates of spec 05 §3.2
    uv run python scripts/dev.py docs            # documentation checks (spec 04 §8)
    uv run python scripts/dev.py bench           # run benchmarks/*.py
    uv run python scripts/dev.py all             # lint, format --check, types, docs, test --gates

Why this exists: Windows has no ``make``, and shell scripts differ between PowerShell and bash.
A small Python script behaves the same everywhere, including on CI (spec 05 §1).

How it works: each step is a list of commands. Every command is started with
``subprocess.run([sys.executable, "-m", tool, ...])``, which means:

- ``sys.executable`` is the Python running this script, i.e. the project's ``.venv`` when you
  use ``uv run``. So the tools come from the locked environment, not from whatever is on PATH.
- Arguments are passed as a **list** and never through a shell, so no quoting problems and no
  shell injection (spec 05 §2, "Subprocesses").

``all`` keeps going after a failed step, so you see every problem at once, then prints a
summary table and exits 1 if anything failed.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

#: Repository root: this file lives in ``<root>/scripts/``.
ROOT = Path(__file__).resolve().parent.parent

#: Overall and ``core/`` coverage gates (spec 05 §3.2).
OVERALL_GATE = 85
CORE_GATE = 90

#: Hard ceiling for any single tool run, so a hung process can't block CI forever.
TIMEOUT_S = 1800


@dataclass(frozen=True)
class StepResult:
    """The outcome of one named step, for the summary table."""

    name: str
    ok: bool
    seconds: float


def run(args: Sequence[str]) -> int:
    """Run one command from the repo root, streaming its output, and return its exit code.

    Args:
        args: The command as a list, e.g. ``[sys.executable, "-m", "ruff", "check", "."]``.

    Returns:
        The command's exit code (124 if it timed out, like the Unix ``timeout`` tool).
    """
    print(f"    $ {' '.join(args)}", flush=True)
    try:
        completed = subprocess.run(list(args), cwd=ROOT, check=False, timeout=TIMEOUT_S)
    except subprocess.TimeoutExpired:
        print(f"    timed out after {TIMEOUT_S} s", flush=True)
        return 124
    return completed.returncode


def tool(*args: str) -> list[str]:
    """Build a ``python -m <tool> ...`` command for the current interpreter."""
    return [sys.executable, "-m", *args]


def lint_commands() -> list[list[str]]:
    """Commands for the ``lint`` step."""
    return [tool("ruff", "check", ".")]


def format_commands(*, check: bool) -> list[list[str]]:
    """Commands for the ``format`` step (``check=True`` only verifies, never rewrites)."""
    return [tool("ruff", "format", *(["--check"] if check else []), ".")]


def types_commands() -> list[list[str]]:
    """Commands for the ``types`` step: mypy for 3.15 (pyproject) and for the 3.13 floor."""
    return [
        tool("mypy"),
        tool("mypy", "--python-version", "3.13", "--exclude", "src/cartographer/adapters/"),
    ]


def test_commands(extra: Sequence[str], *, gates: bool) -> list[list[str]]:
    """Commands for the ``test`` step.

    Args:
        extra: Arguments passed straight through to pytest (e.g. ``-k scan``).
        gates: Also enforce the coverage gates: >= 85 % overall, >= 90 % for ``core/``.
    """
    if not gates:
        return [tool("pytest", *extra)]
    return [
        tool(
            "pytest",
            "--cov=cartographer",
            "--cov-branch",
            "--cov-report=term-missing",
            f"--cov-fail-under={OVERALL_GATE}",
            *extra,
        ),
        tool("coverage", "report", "--include=*/cartographer/core/*", f"--fail-under={CORE_GATE}"),
    ]


def docs_commands() -> list[list[str]]:
    """Commands for the ``docs`` step (spec 04 §8)."""
    return [
        [sys.executable, str(ROOT / "scripts" / "check_concepts.py")],
        [sys.executable, str(ROOT / "scripts" / "check_links.py")],
        tool("pytest", "tests/docs", "-q"),
    ]


def bench_commands() -> list[list[str]]:
    """Commands for the ``bench`` step: every ``benchmarks/*.py``, in name order."""
    return [[sys.executable, str(path)] for path in sorted((ROOT / "benchmarks").glob("*.py"))]


def run_step(name: str, commands: Sequence[Sequence[str]]) -> StepResult:
    """Run all commands of a step, stopping at the first failure inside the step."""
    print(f"==> {name}", flush=True)
    start = time.perf_counter()
    ok = True
    if not commands:
        print("    (nothing to run)")
    for command in commands:
        if run(command) != 0:
            ok = False
            break
    return StepResult(name, ok, time.perf_counter() - start)


def print_summary(results: Sequence[StepResult]) -> None:
    """Print a small table: step, PASS/FAIL, duration."""
    print("\n==> summary")
    for result in results:
        status = "PASS" if result.ok else "FAIL"
        print(f"    {result.name:<16} {status}  {result.seconds:6.1f} s")


def build_parser() -> argparse.ArgumentParser:
    """Create the argument parser with one subcommand per step."""
    parser = argparse.ArgumentParser(prog="dev.py", description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="step", required=True)
    sub.add_parser("lint", help="ruff check")
    fmt = sub.add_parser("format", help="ruff format")
    fmt.add_argument("--check", action="store_true", help="verify only, don't rewrite")
    sub.add_parser("types", help="mypy (3.15 and the 3.13 floor)")
    test = sub.add_parser("test", help="pytest (extra arguments are passed through)")
    test.add_argument("--gates", action="store_true", help="enforce coverage gates")
    test.add_argument("pytest_args", nargs=argparse.REMAINDER, help="passed to pytest")
    sub.add_parser("docs", help="documentation checks")
    sub.add_parser("bench", help="benchmarks")
    sub.add_parser("all", help="everything CI runs")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the requested step(s) and return 0 if all passed, else 1."""
    ns = build_parser().parse_args(argv)
    if ns.step == "all":
        results = [
            run_step("lint", lint_commands()),
            run_step("format --check", format_commands(check=True)),
            run_step("types", types_commands()),
            run_step("docs", docs_commands()),
            run_step("test --gates", test_commands([], gates=True)),
        ]
        print_summary(results)
        return 0 if all(r.ok for r in results) else 1

    commands = {
        "lint": lint_commands,
        "format": lambda: format_commands(check=ns.check),
        "types": types_commands,
        "test": lambda: test_commands(ns.pytest_args, gates=ns.gates),
        "docs": docs_commands,
        "bench": bench_commands,
    }[ns.step]()
    return 0 if run_step(ns.step, commands).ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
