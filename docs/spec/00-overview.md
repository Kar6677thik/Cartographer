# 00 — Overview: what Cartographer is, and why it exists

> **Status:** Approved spec, revision 1 (2026-11-03).
> **Read this first.** Every other spec document assumes you have read this one.
> **Source research:** [`docs/research/python-mastery-research.md`](../research/python-mastery-research.md). References like "§2.3" in any spec point to sections of that file.

---

## 1. Cartographer in one paragraph

Cartographer is a **command-line tool and Python library that reads someone else's Python project and explains it to you**. It never needs the project to be installed or running (with two clearly marked exceptions, see §6). You point it at a folder and it tells you:

| Question it answers | Command | Milestone |
|---|---|---|
| "Which modules import which, and where are the circular imports?" | `cartographer graph` | C1 |
| "Why does this program take so long to start, and which imports could be made lazy?" | `cartographer startup` | C2 |
| "Are there known-bad code patterns, such as blocking calls inside `async def`?" | `cartographer check` | C3 |
| "How much of this code has type annotations, and where does `Any` sneak in?" | `cartographer typecov` | C4 |
| "Where are strings built with f-strings flowing into SQL, shell or HTML, and can you rewrite them safely as t-strings?" | `cartographer tstring` | C5 |
| "If I upgrade dependency X from 1.4 to 1.5, what new things does it start doing?" | `cartographer depdiff` | C6 |
| "Are this repo's GitHub Actions workflows open to the Ultralytics-style attack?" | `cartographer ci` | C7 |
| "Give me all of the above as a single report." | `cartographer report` | C8 |

The name comes from the idea of **drawing a map of unfamiliar territory**.

## 2. Why build it: learning first, novelty second

This is a **learning project**. Its main output is **you understanding Python deeply**. The tool comes second. Concretely:

1. Each milestone is modelled on a **real incident at a real company** (Dropbox's import tangle, Meta's lazy imports, the Ultralytics supply-chain attack, and others; see research §2). Building the tool teaches the part of Python that the incident is about.
2. Most milestones **rebuild something that already exists**, on purpose. Each one names a **reference implementation** (import-linter, ruff, zizmor and so on). We build our own version first, *then* read theirs and write down what they did differently. That comparison is where much of the learning happens.
3. Two pieces are, as far as the research could find, genuinely new: the **f-string → t-string migration with a processor verifier** (C5 ★). In Kiln, the sibling project, it is the fork-assumption checker.

Because the goal is learning, **documentation is a deliverable with the same weight as code**. A milestone with working code but missing explanations is *not done*. See [`04-documentation-standard.md`](04-documentation-standard.md).

## 3. Who does what (roles)

Decision [D-001](01-decisions.md#d-001-roles) defines this. The short version:

| Role | Who | Responsibilities |
|---|---|---|
| **Learner / owner** | You | Read the concept notes. Answer the *prediction questions* before each milestone. Review pull requests (PRs), ask questions, which get logged in [`docs/learn/faq.md`](../learn/faq.md). Do the optional hands-on exercises. Approve anything public-facing (publishing to PyPI). |
| **Implementer** | Claude (AI coding agent), or you for any task marked 🖐 *hands-on* | Write the code, tests and **all teaching documentation** exactly as the specs say. Explain every non-obvious decision in writing. Never skip the documentation deliverables. |

You are assumed to be a **beginner**. Nothing in these docs or in the code may assume you already know a concept. Every term is defined on first use and collected in the [glossary](../learn/glossary.md).

## 4. Goals

- **G1. Learning:** by the end, you can explain *cold* every topic in the Cartographer column of the research's knowledge map (§3, §7): the import system, `ast`, static analysis, typing, strings and t-strings, packaging, supply-chain security, CI security, testing with Hypothesis, and so on.
- **G2. A working tool:** pointed at a real mid-sized repository, Cartographer surfaces **at least one real import cycle, one startup win, one injection-risky sink with a working rewrite, and one dependency or CI risk** (research §5, "Done when"). [C8](milestones/C8-ship.md#final-acceptance) defines the exact acceptance run.
- **G3. Engineered properly:** tests (including property-based tests), type-checked, CI on every push, documented, packaged, published to TestPyPI with attestations.
- **G4. Original thinking:** every milestone ends with a written comparison against its reference implementation.

## 5. Non-goals (things we deliberately do NOT do)

Writing these down prevents scope creep and confusion later.

- **NG1. Not a replacement for ruff, mypy, zizmor and friends.** We will not chase their rule counts, speed or polish.
- **NG2. No IDE / language-server integration.** It is a CLI and library only.
- **NG3. No incremental cache or daemon in v1.** Every run analyses from scratch. (Dropbox's mypy daemon is discussed in C4's notes as a concept, not built.)
- **NG4. No inter-procedural (whole-program) taint analysis.** C5 analyses one function at a time. See C5 for why.
- **NG5. No executing target code on your machine by default.** See §6.
- **NG6. No Kiln code.** Kiln is a separate project in a separate repository. The two projects share no code (decision D-002).
- **NG7. No support for Python 2 or for Python versions below 3.13**, either for running Cartographer or as analysis targets.
- **NG8. No auto-fixing except in C5** (the t-string codemod) and C2's optional "apply lazy imports to a *copy*" experiment.

## 6. Safety model (important, read this)

Cartographer reads **untrusted code**. A repo you have never seen might contain malicious code. So:

1. **Static by default.** Every command reads files as text and parses them with `ast`, `tokenize` or LibCST. **Parsing code never runs it.** This is safe.
2. **Exactly three features execute code.** All are opt-in (D-013), and all print a warning first:
   - `cartographer startup measure` (C2) runs `python -X importtime -c "import X"` in a **subprocess** using an interpreter *you* choose. This runs the target's import-time code. Only use it on code you trust. It requires the flag `--execute`.
   - `cartographer depdiff --dynamic` (C6) installs and imports a package **only inside a disposable Docker container with no network** (`--network none`). It never runs on your host. It requires Docker and the flag `--dynamic`.
   - `cartographer tstring verify` (C5) imports and calls a t-string *processor* to test it. Our own `cartographer.adapters.*` need no flag. Any other processor needs `--execute` (D-036).
   - **Real third-party repos from the acceptance corpus never run on your host, not even with `--execute`.** When acceptance needs to run them (C2/C8 startup measurements), it does so inside a no-network Docker container (D-013).
3. **Archives are hostile.** When C6 unpacks wheels and sdists, it defends against path traversal ("zip slip"), symlinks, absurd sizes ("zip bombs") and duplicate names. C6 specifies this.
4. **Cartographer's own scripts never live inside unpack directories** (research §6). Python puts the script's directory on `sys.path`, so a planted `json.py` next to a script would hijack `import json`. Subprocesses that touch untrusted files run with `python -I` (isolated mode). The [glossary](../learn/glossary.md) explains `-I`.

## 7. Platforms and Python versions

- **Primary development platform: native Windows 11** (your machine). Everything except the C6 sandbox works natively. The C6 sandbox uses Docker Desktop, which you already have.
- CI runs on **Windows and Ubuntu**, so the code is proven to be portable.
- **Cartographer runs on Python 3.13, 3.14, 3.15 and 3.15t (free-threaded).** Day-to-day development uses **3.15**. Decision D-004 explains the subtle part: *Cartographer can only parse syntax that the interpreter running it understands*.

## 8. Milestones at a glance

The full roadmap is in [`07-roadmap.md`](07-roadmap.md). Summary:

| ID | Name | Size | One-line outcome |
|---|---|---|---|
| M0 | Foundation | M | Repo skeleton, core data model, CLI shell, CI, docs scaffolding, verification spikes |
| C1 | Import graph | L | Module graph, cycles (SCCs), edge-cut suggestions, DOT/Mermaid export |
| C2 | Startup & lazy imports | L | `-X importtime` profiler, side-effect detector, `lazy import` advisor, measured win on 3.15 |
| C3 | Rule engine | M | Plugin-based rules: blocking calls in async, `finally` control flow, mutable defaults |
| C4 | Typing health | M | Annotation coverage, `Any` leaks, type-checker disagreement study, mypyc experiment |
| C5 ★ | t-string migration | XL | Taint finder, LibCST codemod to t-strings, Hypothesis processor verifier |
| C6 | Dependency upgrade diff | XL | Capability manifests (static + sandboxed dynamic), provenance check, diff |
| C7 | CI workflow auditor | M | GitHub Actions parser and rules for the Ultralytics attack chain |
| C8 | Ship | M | Packaging, TestPyPI with Trusted Publishing, combined report, final acceptance |

Sizes are relative: S ≈ a few sessions, M ≈ about a week of evenings, L ≈ about two weeks, XL ≈ three or more weeks.

## 9. How to read the docs

See [`docs/README.md`](../README.md) for the full map. Reading order for a newcomer:

1. This file.
2. [`docs/learn/README.md`](../learn/README.md), the learning path, and [`docs/learn/faq.md`](../learn/faq.md), the beginner FAQ.
3. [`01-decisions.md`](01-decisions.md), which explains *why* things are the way they are.
4. [`02-architecture.md`](02-architecture.md) and [`03-cli-config-output.md`](03-cli-config-output.md), which explain how the code is organised.
5. [`04-documentation-standard.md`](04-documentation-standard.md) and [`05-engineering-standards.md`](05-engineering-standards.md), the rules every change follows.
6. [`06-environment-setup.md`](06-environment-setup.md), which installs everything.
7. [`07-roadmap.md`](07-roadmap.md), then the milestone spec you are working on.
