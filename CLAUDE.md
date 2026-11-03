# CLAUDE.md: instructions for AI implementers

Read this at the start of every session working on Cartographer.

## What this project is
Cartographer is a **learning project**. It's a Python code-intelligence and safety CLI. The owner is a **beginner**: they learn from the docs and code you write, not from prior knowledge. **Teaching documentation is a deliverable equal to code** (D-001, D-028).

## Before you write anything
1. Read `docs/spec/00-overview.md`, `01-decisions.md`, `02-architecture.md`, `03-cli-config-output.md`, `04-documentation-standard.md` and `05-engineering-standards.md`.
2. Read the milestone spec you're working on (`docs/spec/milestones/<ID>-*.md`) in full.
3. Check `docs/learn/predictions/<ID>.md` exists. If it doesn't, ask the owner to write predictions first (07 §2 Stage A). Don't start building without it.
4. If the phase depends on a spike (`docs/spec/08-spikes-and-risks.md`), run the spike first and record it in `docs/learn/spikes/`.

## Hard rules
- **Specs are the source of truth.** If you must deviate, update the spec (and `01-decisions.md` via `docs/templates/decision-record.md`) in the same PR, and say so in the PR description.
- **Documentation standard (spec 04) is mandatory:** module docstrings with the three required headings; Google-style docstrings with examples; `CONCEPT(x)` and `INCIDENT(…)` comments; concept notes written before or alongside the code; walkthrough, write-up and comparison at milestone end; glossary and FAQ updated in the same PR. No "simply", "just" or "obviously".
- **Don't read a reference implementation's source code before our version is accepted** (D-008). Never copy code from one.
- **Never execute target or corpus code on the host.** The three opt-in execution paths are C2 `--execute` (our own fixtures and trusted code only), C6 `--dynamic` (Docker sandbox only) and C5 `tstring verify` (D-036). Corpus code runs only through the no-network Docker harness `scripts/corpus_startup.py` (D-052).
- **Source under `src/` must be valid Python 3.13 syntax** (D-005). No t-string literals or `lazy import` statements in `src/`.
- **No new runtime dependency** without a decision record (D-006).
- **No pushing, PRs or publishing** unless the owner asked in the current session. Real PyPI needs explicit approval (D-011).
- Diagnostics are filtered exactly once, in `api.py` (D-046). Commands report only codes in their scope (D-047). Dogfood runs always use root `.` (D-048).
- One phase = one branch + one PR (D-009). Use Conventional Commits. PR descriptions follow 04 §6, including "What you'll learn from this PR".
- Every acceptance criterion maps to a named test that cites its ID (`T-…`/`A-…`) in the docstring.

## Commands
```powershell
uv sync
uv run python scripts/dev.py all     # lint, types, tests, doc checks
uv run pytest -m "not network and not docker and not corpus"
uv run cartographer --help
```

## When the owner asks a question
Answer it, then add it to `docs/learn/faq.md` (and the glossary, if a term was involved) in the current or next PR.
