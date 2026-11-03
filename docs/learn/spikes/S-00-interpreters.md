# Spike S-00: can we get Python 3.13, 3.14, 3.15 and 3.15t locally and on CI?

> **Needed by:** M0 phase 1 · **Date:** 2026-11-03 · **Time box:** 1 hour
> **Spec reference:** [`08-spikes-and-risks.md`](../../spec/08-spikes-and-risks.md#1-spikes)

## Question

Does `uv python install 3.13 3.14 3.15 3.15t` work on the owner's Windows machine, and do the GitHub runners (`windows-latest`, `ubuntu-latest`) get all four interpreters via `astral-sh/setup-uv`? CI's 8-cell test matrix (spec 05 §4) depends on it.

## What we ran

Locally (Windows 11, PowerShell / Git Bash), starting with only Python 3.12.10 installed and no uv:

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
uv --version
uv python install 3.13 3.14 3.15 3.15t
uv python list --only-installed
```

Then the phase-1 test suite on each interpreter:

```powershell
uv run --python 3.13  pytest -q
uv run --python 3.14  pytest -q
uv run --python 3.15  pytest -q
uv run --python 3.15t pytest -q
```

On CI, the `test` job runs `uv python install "$PYTHON"` and `uv sync --locked --python "$PYTHON"` in all 8 cells (see the first CI run of the `m0/skeleton` pull request).

## What we saw

```text
uv 0.13.7 (316c827e0 2026-11-03 x86_64-pc-windows-msvc)
 Downloaded cpython-3.15.2-windows-x86_64-none
 Downloaded cpython-3.14.10-windows-x86_64-none
 Downloaded cpython-3.15.2+freethreaded-windows-x86_64-none
Installed 4 versions in 5.27s
 + cpython-3.13.5-windows-x86_64-none (python3.13.exe)
 + cpython-3.14.10-windows-x86_64-none (python3.14.exe)
 + cpython-3.15.2+freethreaded-windows-x86_64-none (python3.15t.exe)
 + cpython-3.15.2-windows-x86_64-none (python3.15.exe)
```

All 45 phase-1 tests passed on each of the four interpreters locally.

CI: all 8 test cells installed their interpreter with `uv python install` and passed (first run of PR #1, commit `93943d3`). Details under "CI result".

## Conclusion

**Locally: yes.** uv provides all four builds on Windows with no admin rights. They live under `%APPDATA%\uv\python\` and don't touch the pre-existing Python 3.12.

**CI: yes.** `astral-sh/setup-uv` v10.3.3 plus `uv python install` provides all four builds, including `3.15t`, on both `windows-latest` and `ubuntu-latest`. The fallback in spec 08 (drop 3.15t on Windows) isn't needed.

## Spec changes made

- None needed for the interpreters themselves.
- Found along the way: the owner's *global* git config had `core.autocrlf=true`. We set `core.autocrlf=false` **for this repository only** (`git config core.autocrlf false`, no `--global`), so other repositories on the machine are unaffected, and rely on `.gitattributes`. Step 3 of [`06-environment-setup.md`](../../spec/06-environment-setup.md) now says the same.

## CI result

First run of PR #1 (`m0/skeleton`, commit `93943d3`, 2026-11-03): **11 of 11 jobs passed.**

| Job | Interpreter installed | Duration |
|---|---|---|
| test (ubuntu-latest, 3.13) | 3.13.18 | 13 s |
| test (ubuntu-latest, 3.14) | 3.14.10 | 15 s |
| test (ubuntu-latest, 3.15) + coverage gates | 3.15.2 | 12 s |
| test (ubuntu-latest, 3.15t) | 3.15.2 free-threaded | 13 s |
| test (windows-latest, 3.13) | 3.13.18 | 26 s |
| test (windows-latest, 3.14) | 3.14.10 | 31 s |
| test (windows-latest, 3.15) | 3.15.2 | 28 s |
| test (windows-latest, 3.15t) | 3.15.2 free-threaded | 38 s |
| lint / types / docs | 3.15.2 | 12 s / 12 s / 15 s |

Each interpreter download took under 4 s. Windows cells run about twice as long as Linux ones.

**One local mismatch:** CI got **3.13.18**, but the owner's machine has **3.13.5**. uv found an older 3.13 already in its cache and reused it instead of downloading the newest patch release. Patch releases contain bug fixes, so to match CI, run `uv python upgrade 3.13` (or `uv python install --reinstall 3.13`). The lesson: "3.13" names a *series*, not one exact interpreter.

## What this taught us

uv's standalone Python builds make "test on four interpreters" a one-line install, including the free-threaded build, which used to require compiling CPython yourself. Using `uv run --python X` also *rebuilds* `.venv` for that version each time you switch, which takes about a second thanks to uv's cache.
