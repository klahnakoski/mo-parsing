# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

`mo-parsing` — a fork of pyparsing optimized for speed (originally for mo-sql-parsing). PEG parser combinators defined with Python operators. Published to PyPI.

## Commands

```
pip install -r tests/requirements.txt -r packaging/requirements.txt
set PYTHONPATH=.
python -m unittest discover tests                       # full suite
python -m unittest tests.test_unit.TestParsing.test_x   # single test
```

CI (`.github/workflows/build.yml`) runs `python -m unittest discover .` on Python 3.8–3.13. `setup.py` lives in `packaging/` (CI copies it to the repo root); version and metadata are in `packaging/setuptools.json`. Runtime deps are only `mo-dots` and `mo-future`.

Branches: `dev` is the working branch; `master` is release. Test matrix runs on master/tags, coverage on dev.

## Architecture

Class hierarchy, all rooted at `ParserElement` (`core.py`):

- `tokens.py` — leaf matchers (`Literal`, `Word`, `Keyword`, `CharsNotIn`, positional tokens…)
- `expressions.py` — combinators over child lists: `And`, `Or`, `MatchFirst`, `MatchAll`, plus `Fast` (regex-dispatched MatchFirst)
- `enhancement.py` — single-child wrappers: `Many`/`OneOrMore`/`ZeroOrMore`/`Optional`, `Group`, `Suppress`, `Combine`, `Forward`, lookaheads
- `helpers.py`, `infix.py` — prebuilt grammars; `infix_notation` is the fork's raison d'être (fast operator-precedence parsing)

**ParserElements are immutable.** `add_parse_action()`, `set_token_name()` (`("name")` call syntax), operators — all return *new* elements that must be assigned. Dropping the return value is the classic bug when porting pyparsing code. `Forward` is the one deliberate mutability escape hatch.

**Whitespace context** (`whitespaces.py`): `whitespaces.CURRENT` is a global consulted at *parser-creation* time (not parse time). `with Whitespace() as ws:` scopes it; it defines skipped characters, ignored patterns (comments), and what `Literal`/`Keyword` mean. Operators like `+` call `whitespaces.CURRENT.normalize()` to promote strings to elements, so the active context is baked into every element at construction.

**Circular imports** are broken with `mo_imports` `expect()`/`export()` pairs — the big tuples at the top of `core.py`/`whitespaces.py` are placeholders filled in when the defining module later calls `export()`. Keep this pattern when adding cross-module references.

**Regex acceleration**: every element can emit an equivalent regex via `__regex__()`; used internally to fail fast (e.g. `Fast` dispatch on first character). `regex.py`'s `Regex` goes the other way, parsing a regex string into a grammar.

**Results**: `ParseResults` is an n-ary tree; `.type` points at the ParserElement that produced it (keeps results small). Name lookup (`result["name"]`) walks the tree but stops at `Group` boundaries. Parse actions take `(tokens, index, string)` — the reverse of pyparsing — and `expr / lambda t: ...` is shorthand for `add_parse_action`.

## Layout notes

- `pyparsing/` holds upstream pyparsing's tests and examples for reference/compat checking; not part of the package and not run by CI.
- `mo_parsing/` and `tests/` are also SVN working copies (`.svn/` inside each); the `svn` git branch mirrors SVN state. Sync is done with the `/svn-sync` skill, not by hand.
- `tests/README.md` covers contributor setup; `README.md` documents the pyparsing differences (immutability, whitespace context, no `*` wildcard, no pickle).
- `TODO.md` — live work queue; `SESSION_LOG.md` — dated per-session history; `mo_parsing/BUGS.md` — known module defects (flows to SVN).
