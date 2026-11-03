# Cartographer

**A Python code-intelligence and safety toolkit, built as a learning project.**

Point it at someone else's Python repository and it maps the territory: import cycles, startup cost and lazy-import opportunities, risky code patterns, typing health, injection-prone strings (with a rewrite to PEP 750 t-strings), what changes when you upgrade a dependency, and how exposed the CI workflows are to supply-chain attacks.

> **Status:** specification complete. Implementation starts with milestone M0. Nothing is installable yet.

## Why it exists
To learn Python deeply by rebuilding, from scratch, the tools real companies needed after real incidents (Dropbox's import tangle, Meta's lazy imports, the Ultralytics supply-chain attack, …). Then compare each one against the established tool. See [`docs/spec/00-overview.md`](docs/spec/00-overview.md).

## Start here
- **New to all this?** → [`docs/learn/README.md`](docs/learn/README.md) (learning path) and [`docs/learn/faq.md`](docs/learn/faq.md)
- **All documentation** → [`docs/README.md`](docs/README.md)
- **Set up your machine** → [`docs/spec/06-environment-setup.md`](docs/spec/06-environment-setup.md)
- **The plan** → [`docs/spec/07-roadmap.md`](docs/spec/07-roadmap.md)

## Planned commands
| Command | What it tells you |
|---|---|
| `cartographer graph` | Import graph, cycles, tangles, which edges to cut |
| `cartographer startup` | What's slow at import time; which imports could be `lazy` |
| `cartographer check` | Blocking calls in `async def`, `return` in `finally`, mutable defaults |
| `cartographer typecov` | Annotation coverage and where `Any` leaks in |
| `cartographer tstring` | f-strings flowing into SQL/shell/HTML, rewritten to safe t-strings |
| `cartographer depdiff` | What a dependency upgrade newly does (static + sandboxed) |
| `cartographer ci` | GitHub Actions risks (Ultralytics-style injection, unpinned actions…) |
| `cartographer report` | All of it, in one Markdown report |

Package name on PyPI (planned): `cartographer-py`. Import name: `cartographer`. Licence: MIT.
