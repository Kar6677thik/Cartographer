# FAQ: the doubts log

> **How this works:** every question the owner asks, in a PR review, a conversation, or a note, gets a written answer here, so nobody has to ask it twice. The implementer adds the entry in the same PR that answers it. Seeded below with the questions a beginner is most likely to have at the start.
>
> Format: question as a heading (it becomes a linkable anchor), short answer first, then detail, then links.

---

## About the project

### What is Cartographer, in one sentence?
A command-line tool that reads a Python project *without running it* and reports on its structure, startup cost, typing, injection risks, dependency changes and CI risks. Details: [spec 00](../spec/00-overview.md).

### Why rebuild tools that already exist (ruff, import-linter, zizmor)?
Because building one teaches you how it works, and that's the goal (learning first). Each milestone ends by comparing ours with the real tool, which is where you see what experts do differently. See D-008.

### Who writes the code? Do I have to?
Claude implements. You read, predict, review and ask (D-001). Tasks marked 🖐 in the specs are good ones to try yourself if you want hands-on practice. It's optional.

### What should I do before each milestone?
Read its "Why this matters" section, read the concept notes it lists, and write your predictions in `docs/learn/predictions/<milestone>.md`. That's about an hour. See [spec 07 §2](../spec/07-roadmap.md#2-the-milestone-ritual).

### What if I don't understand a PR?
Say so in the review. "I don't understand X" is a valid reason to block a PR. The fix is better documentation or simpler code (risk R-12).

## Python basics

### What's the difference between a module and a package?
A **module** is one `.py` file. A **package** is a directory of modules, which you import with dotted names (`cartographer.core.source`). Concept note: `project-layout-and-pyproject`.

### Why src layout?
If the package lived at the repo root, running tests from the root could import the *source folder* instead of the *installed package*. That would hide packaging bugs, such as a file that's missing from the wheel. Putting it under `src/` makes tests use the installed (editable) package. D-003.

### What does "static analysis" mean? Is it safe on untrusted code?
It means reading and parsing code without running it. Yes, parsing is safe: `ast.parse` builds a tree and never executes anything. Only two opt-in features ever run target code, and they warn you first ([spec 00 §6](../spec/00-overview.md#6-safety-model-important-read-this)).

### What is an AST, and why not just use regular expressions on the code?
An AST is a tree that shows the structure of code. Regexes can't tell `import os` in code from `"import os"` in a string or a comment. A parser can. Concept note: `ast-basics`.

### Why does Cartographer run on 3.13 but development uses 3.15?
Users may have older Pythons, so we support them. But Cartographer can only *parse* syntax its own interpreter understands. To analyse code that uses 3.15 features (like `lazy import`), run Cartographer on 3.15. D-004.

### What's `uv`, and do I still need `pip`?
`uv` replaces `pip`, `venv` and Python version managers for this project. You don't need `pip` here. [Setup guide](../spec/06-environment-setup.md).

### What is the free-threaded build (`3.15t`) and why test on it?
It's CPython without the GIL, so threads can run in parallel. Testing on it checks that nothing we depend on breaks there (D-029).

### Why are columns "1-based code points" when `ast` gives 0-based bytes?
Editors count characters from 1. `ast` counts UTF-8 bytes from 0. Mixing them puts the cursor in the wrong place on lines with characters like `é`. We convert once, in one place (D-018).

## Tools and workflow

### What do I run to check everything?
`uv run python scripts/dev.py all` (from M0 onwards). [Spec 05 §1](../spec/05-engineering-standards.md#1-tooling-all-run-through-uv).

### What are the `CRT###` codes?
Every finding has a code. The first digit says which milestone owns it. `cartographer explain CRT101` prints a full explanation. Registry: [spec 03 §6](../spec/03-cli-config-output.md#6-diagnostic-code-registry).

### What's a spike, and why are some specs "Provisional"?
The research describes very recent software (Python 3.15, 2026 tools). Some details need checking on the real thing before we depend on them. A spike is that check. [Spec 08](../spec/08-spikes-and-risks.md).

### Where do I find a word I don't know?
[`glossary.md`](glossary.md). If it's missing, ask, and it gets added.

## (New questions are appended below this line, newest last, grouped by milestone)

### M0
<!-- e.g. ### Why is the logger writing to stderr? -->
