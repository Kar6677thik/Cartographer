# 04 — Documentation standard (mandatory)

> **Why this file exists:** Cartographer is a learning project, and the owner is a beginner (D-001). The documentation has to teach: someone who knows almost no Python should be able to read the code and the docs and understand **what** each piece does, **why** it exists, **how** it works, and **which Python concepts** it uses.
>
> **Every rule here is part of the Definition of Done** (D-028). A PR that breaks a rule is not mergeable, however good the code is.

---

## 1. The five layers of documentation

Every milestone produces all five layers:

| # | Layer | Where | Answers | Written when |
|---|---|---|---|---|
| 1 | **Concept notes** | `docs/learn/concepts/<topic>.md` | "What is X in Python, from zero?" (e.g. *What is an AST?*) | **Before** or alongside the code that first uses X |
| 2 | **In-code docs** | docstrings + comments in `src/` and `tests/` | "What does *this* function do, and why is *this* line like this?" | With the code, in the same commit |
| 3 | **Walkthrough** | `docs/learn/walkthroughs/<milestone>.md` | "In what order should I read the code, and how does data flow through it?" | When the milestone's code is complete |
| 4 | **Milestone write-up** | `docs/learn/writeups/<milestone>.md` | "What did we predict, what happened, what did we measure, what surprised us?" | At milestone end |
| 5 | **Reference comparison** | `docs/learn/comparisons/<milestone>.md` | "How does the real tool (ruff, zizmor…) do it differently, and why?" | After the write-up (D-008) |

Plus three running documents that are **updated continuously**:
- [`docs/learn/glossary.md`](../learn/glossary.md): every new term, on the day it first appears.
- [`docs/learn/faq.md`](../learn/faq.md): every question the owner asks in a review or conversation, with its answer. This is the "doubts log".
- [`docs/learn/README.md`](../learn/README.md): the curriculum index. Mark each concept note ✅ when it is written.

## 2. Concept notes (layer 1)

### 2.1 Rules
- Use [`docs/templates/concept-note.md`](../templates/concept-note.md). Every section is required.
- **Assume zero prior knowledge** beyond "I can run a Python script". If the note uses another concept, link to that concept's note or glossary entry.
- **Runnable examples only.** Every code block in a concept note must run as shown on Python 3.15, or be marked as needing a specific version (`# Python 3.15+`). Expected output goes in a comment or a `>>>` session. **These examples are tested:** `tests/docs/test_concept_examples.py` extracts every `pycon` code block from `docs/learn/concepts/*.md` and runs it with `doctest`. So write interactive examples as `pycon` blocks (`>>>` prompts).
- **Every concept is tied to Cartographer.** A section "Where Cartographer uses this" links to the exact files and functions.
- **Pitfalls section.** List the mistakes beginners (and experts) actually make, each with a tiny demo.
- **Exercises.** 2–4 small exercises with answers in a collapsed `<details>` block.
- **Length:** as long as needed, usually 150–500 lines. Prefer many small examples to one big one.
- **Sources:** link the official Python docs and PEPs first. Third-party blogs only as extras.

### 2.2 Required concept notes
Each milestone spec has a "Concept notes to write" section listing the notes it must produce. The full curriculum index (with which milestone owns each note) is in [`docs/learn/README.md`](../learn/README.md). A note is written **once**, by the first milestone that needs it. Later milestones extend it with a new section and say so in their PR.

## 3. In-code documentation (layer 2)

### 3.1 Module docstrings (every `.py` file in `src/`, including `__init__.py`)

Required structure:
```python
"""One-line summary of what this module is for.

What this module does
---------------------
2–6 sentences in plain English. What goes in, what comes out.

Why it exists
-------------
Which problem from the spec / research incident it serves. Link the spec:
see docs/spec/milestones/C1-import-graph.md §4.2.

Python concepts used here
-------------------------
- ``ast.NodeVisitor`` (docs/learn/concepts/ast-basics.md): walking the syntax tree.
- ``functools.cached_property`` (docs/learn/concepts/descriptors-and-cached-property.md): lazy, cached attributes.

How to read this file
---------------------
Start at ``build_graph()``; everything else is a helper it calls, in order.
"""
```
Tests check that every module in `src/` has a docstring containing the headings `What this module does`, `Why it exists` and `Python concepts used here` (`tests/docs/test_docstrings.py`).

### 3.2 Function, method and class docstrings
- **Every** public function, method and class, *and* every private one longer than ~10 lines. Format: **Google style** (`Args:`, `Returns:`, `Raises:`, `Example:`).
- The first line says *what* it does, in the imperative: "Resolve a relative import to an absolute module name."
- A paragraph says *how*, if the algorithm is not obvious (e.g. "Uses Tarjan's algorithm: one depth-first search that tracks…").
- An `Example:` section with a doctest wherever the inputs are easy to build. Doctests in `src/` are run by pytest (`--doctest-modules`).
- Type hints are required on all signatures (05 §2). Docstrings do not repeat types already in the signature. They explain *meaning* ("1-based line number"), not type.

### 3.3 Comments: explain "why", and teach
Three kinds of comment are required wherever they apply.

1. **Why-comments.** Anything surprising gets a comment explaining why. A reviewer who asks "why is this here?" means a why-comment is missing.
   ```python
   # ast.col_offset is a UTF-8 *byte* offset, not a character index (D-018).
   # Decode the line prefix to count characters correctly for non-ASCII source.
   ```
2. **`CONCEPT:` comments.** The **first time** a Python feature is used in a file, and it is not something a beginner would know, tag it:
   ```python
   # CONCEPT(descriptors-and-cached-property): cached_property is a descriptor; the first access
   # runs the function and stores the result in the instance __dict__, so
   # later accesses skip the descriptor entirely. See docs/learn/concepts/descriptors-and-cached-property.md
   @cached_property
   def tree(self) -> ast.Module | None: ...
   ```
   The tag name must be an **existing concept-note slug** from the curriculum index (`docs/learn/README.md`). `scripts/check_concepts.py` (M0) checks that every `CONCEPT(x)` tag resolves to a file in `docs/learn/concepts/`. If the note isn't written yet, write it in the same PR.
3. **`INCIDENT:` comments.** Where code exists because of a real-world incident from the research, say so:
   ```python
   # INCIDENT(research §2.11, Ultralytics): the branch name itself was the
   # injection payload: `$(curl …)` inside `${{ github.head_ref }}`.
   ```

What **not** to write: comments that restate the code (`i += 1  # increment i`), commented-out code, and TODOs without an issue or spec reference (`# TODO(C4 §6): …` is fine).

### 3.4 Algorithms get pseudocode first
Any non-trivial algorithm (Tarjan SCC, feedback-arc heuristic, taint propagation, bootstrap CI, expression scanning) gets:
1. A plain-English explanation in the docstring,
2. pseudocode in the docstring or in the concept note,
3. a worked example on a tiny input (which also becomes a unit test),
4. its complexity (`O(V + E)`) and *why*.

### 3.5 Tests are documentation too
- Test names read as sentences: `test_relative_import_beyond_top_level_reports_crt104`.
- Each test module starts with a docstring saying what behaviour it pins down and which spec section it covers.
- Each fixture project (`tests/fixtures/projects/<name>/`) has a `README.md` with: what it simulates, which files matter, and the expected findings.
- Hypothesis tests explain in their docstring **what property** is being tested, in plain English ("For any graph, every node is in exactly one SCC").

## 4. Walkthroughs, write-ups, comparisons (layers 3–5)

### 4.1 Walkthrough (`docs/learn/walkthroughs/<milestone>.md`)
- A guided tour: "Open `graph/builder.py`. The entry point is `build_graph()` (line ~40). It does three things…"
- Includes **one end-to-end trace** of a tiny fixture through the whole pipeline: input files → intermediate data (show the actual objects) → output.
- Includes a **diagram** (Mermaid, which renders on GitHub) of the main data flow.
- Ends with "If you want to change X, start at Y". That serves as an extension guide.

### 4.2 Milestone write-up (`docs/learn/writeups/<milestone>.md`)
Template: [`docs/templates/milestone-writeup.md`](../templates/milestone-writeup.md). It has to include:
- The owner's **predictions** (copied from `docs/learn/predictions/<milestone>.md`, written *before* implementation) and whether each was right.
- **Measurements**: numbers, how they were measured, on which Python and machine, and repeat counts.
- **Surprises and mistakes**: what went wrong during implementation and what was learned. Honest, not polished.
- Results on the acceptance corpus.

### 4.3 Reference comparison (`docs/learn/comparisons/<milestone>.md`)
Template: [`docs/templates/reference-comparison.md`](../templates/reference-comparison.md). For each reference tool named in the milestone spec: how it solves the same problem, what it does that we don't (and why that matters), what we do differently, and anything we would now change. Where it helps, run both tools on the same fixture and compare the outputs in a table.

## 5. `cartographer explain` texts

Every diagnostic code has a long explanation, stored next to its implementation (in the rule class docstring or a `EXPLANATION` string in `codes.py`) and printed by `cartographer explain CODE`. Required sections, in this order:

```
CRT101 import-cycle (default: warning)

What it means
  Two or more modules import each other, directly or through a chain.

Why it matters
  …(the real incident: Dropbox's "tangle", research §2.3)…

Example
  # a.py               # b.py
  import b             import a

How to fix it
  …(move the shared code; import inside a function; use TYPE_CHECKING)…

When it is OK to ignore
  …

Learn more
  docs/learn/concepts/import-system.md, https://docs.python.org/3/reference/import.html
```
A test checks that every registered code has an explanation with all six sections.

## 6. PR descriptions

Every PR description has these sections:
```markdown
## What this PR does
## Spec sections covered        (links, e.g. C1 §4.2–4.4)
## What you'll learn from this PR
   3–8 bullets for the owner: concepts introduced, links to concept notes,
   the most interesting lines to read (file:line).
## Docs added/updated           (checklist of the five layers + glossary/FAQ)
## How it was tested
## Open questions / follow-ups
```

## 7. Style for all prose

- Plain English, short sentences, active voice. Write "we" for the project and "you" for the reader.
- **Define every term on first use** in a document, even if it's in the glossary: "the AST (abstract syntax tree, a tree of objects representing the structure of code)".
- Prefer tables for comparisons and numbered lists for procedures.
- Show, don't just tell: a 3-line example beats a paragraph.
- Never write "simply", "just", "obviously" or "trivially". Those words make a beginner feel stupid when something isn't simple for them.
- Code identifiers in backticks. Paths relative to the repo root.
- Diagrams in Mermaid, so they render on GitHub with no image files.

## 8. Doc checks that run in CI (built in M0)

| Check | Script / test |
|---|---|
| Module docstring headings present | `tests/docs/test_docstrings.py` |
| Public API has docstrings | same, using `ast` over `src/` |
| `CONCEPT(x)` tags resolve to an existing concept note | `scripts/check_concepts.py` |
| Concept-note `pycon` examples run | `tests/docs/test_concept_examples.py` |
| Every **implemented** code in `codes.py` has a complete explanation (D-044) | `tests/unit/core/test_codes.py` |
| Codes in `codes.py` match the table in 03 §6 | same |
| Internal Markdown links are not broken | `scripts/check_links.py` (relative links + `#anchors`; headings inside fenced code blocks are ignored; `docs/templates/` is skipped because its links are relative to where a copy will live) |
| Every fixture project has a README.md | `tests/docs/test_fixture_readmes.py` |
