# 06 — Environment setup (Windows 11, from zero)

> Follow these steps in order. Each step shows **what to run**, **what you should see**, and **what it means**. This is checked against the state of your machine on 2026-11-03: Python 3.12.10, git 2.51, gh 2.101 and Docker 28.4 (daemon running) were installed. **uv was not**, and **Python 3.13/3.14/3.15 were not**.
>
> All commands are for **PowerShell** (the default Windows terminal shell) unless marked otherwise.

---

## Step 1: Install `uv` (the Python project manager)

**What it is:** `uv` is one tool that replaces `pip`, `venv`, `pyenv` and `pip-tools`. It downloads Python interpreters, creates virtual environments, installs packages and locks versions. It's written in Rust and is very fast. (Glossary: *virtual environment*, *lockfile*.)

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```
Then **close and reopen the terminal**, so the updated `PATH` is picked up, and check:
```powershell
uv --version          # expect: uv 0.x.y (…)
```
If you see *"uv is not recognized"*, the terminal still has the old `PATH`. Open a new window. If that doesn't help, sign out and back in.

## Step 2: Install the Python versions Cartographer supports

```powershell
uv python install 3.13 3.14 3.15 3.15t
uv python list --only-installed
```
You should see four entries, with `3.15t` described as *freethreaded*.

**What these are:**
- `3.13`, `3.14`, `3.15`: normal CPython builds (with the GIL, the Global Interpreter Lock; see the glossary).
- `3.15t`: the **free-threaded** build, where the GIL is off. We test on it (D-029).
- Your existing **Python 3.12 is not touched** and is not used by this project. uv keeps its interpreters separate.

## Step 3: Git settings for a cross-platform repo

```powershell
git config core.autocrlf false              # run INSIDE the repo folder: this repo only; .gitattributes controls line endings
git config --global core.longpaths true     # Windows' 260-character path limit bites in deep fixture trees
git config --global init.defaultBranch main
```
**Why:** Windows uses `\r\n` line endings and Linux uses `\n`. Our `.gitattributes` (M0) stores everything as `\n`, so golden-file tests produce the same bytes on both CI platforms.

## Step 4: GitHub CLI login (for PRs and CI)

```powershell
gh auth status        # if "not logged in": gh auth login  → GitHub.com → HTTPS → browser
```

## Step 5: Docker (needed only from C6)

Docker Desktop is already installed and running Linux containers. Check:
```powershell
docker run --rm --network none python:3.15-slim python -c "print('sandbox ok')"
```
Expected: `sandbox ok`. `--network none` gives the container **no network at all**. That's exactly how C6's sandbox works (00 §6). If the image tag doesn't exist yet, try `python:3.15` and record that in spike S-06.

## Step 6: Create the project environment (done once M0 exists)

```powershell
cd "C:\Users\Karthik Reddy\Documents\Study\Projects\Cartographer"
uv sync                       # creates .venv\ with Python 3.15 (from .python-version) + dev deps
uv run cartographer --version # expect: cartographer 0.0.1 (Python 3.15.x, win32)
uv run python scripts/dev.py all
```
To test another interpreter locally:
```powershell
uv run --python 3.13 pytest
uv run --python 3.15t pytest
```

## Step 7: Editor (recommended, optional)

VS Code with the **Python** extension, plus **Ruff**, plus either **Pylance** or the Pyrefly/ty extension. Point the interpreter at `.venv\Scripts\python.exe`. Turn on "format on save" with Ruff.

## Step 8: Tools used later (no need to install now)

| When | Tool | How it's run |
|---|---|---|
| C1 | Graphviz (to *view* DOT output) | optional: `winget install Graphviz.Graphviz`. Mermaid output needs nothing, since GitHub renders it |
| C4 | `pyright`, `pyrefly`, `ty` | `uvx pyright …`, `uvx pyrefly …`, `uvx ty …`. uv fetches them on demand |
| C4 | `mypyc` | comes with `mypy` |
| C6 | Docker image `cartographer-sandbox` | built by `cartographer depdiff --dynamic` from `src/cartographer/depdiff/sandbox/Dockerfile` |
| C2 | Admin rights? | **No.** `-X importtime` needs no special privileges |

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `uv` not found after install | stale `PATH` | new terminal |
| `UnicodeDecodeError` / mojibake in output on 3.13/3.14 | Windows console code page isn't UTF-8 | Cartographer always writes UTF-8 explicitly (D-019). For your own scripts, set `$env:PYTHONUTF8 = "1"`. Python 3.15 defaults to UTF-8 (PEP 686) |
| Tests are very slow on Windows | Defender scanning `.venv` | add the project folder to Defender exclusions (optional) |
| `docker: error during connect` | Docker Desktop not running | start Docker Desktop |
| Golden tests fail only on Windows | `\r\n` crept in | check `.gitattributes`, and run `git add --renormalize .` |
| `Filename too long` | long paths | Step 3 `core.longpaths` |
