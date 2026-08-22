# Faster

Plan for making mo-parsing much faster. Numbers are from one benchmark; re-measure
before and after each phase and update this file.

## Benchmark

`python tests/bench.py` — json (Forward/MatchFirst/delimited_list), infix
(`infix_notation`, six levels), sql (mo-sql-parsing, sibling checkout or installed).
Best of 5 rounds, wall clock, quiet machine:

| state                          | json | infix |  sql |
|--------------------------------|-----:|------:|-----:|
| baseline (`d60251c`)           | 42.9 |  49.4 | 52.6 |
| phase 1 (`2ad06c9`)            | 26.0 |  19.1 | 14.2 |
| phase 2 (`1c2a8f5`)            | 16.0 |  13.9 |  7.0 |
| phase 3 (`6f46e28`)            | 13.9 |  11.9 |  6.3 |
| phase 5.1 (`d3f95bb`)          | 10.8 |  11.1 |  6.0 |
| phase 5.2 (`9979b89`)          |  7.5 |   9.1 |  4.3 |

The phase-2 pair was measured back to back on a busier machine, which read phase 1
as 28.5 / 21.0 / 15.3; against that the change is −44% json, −34% infix, −54% sql.

The phase-3 pair was measured the same way, alternating with phase 2 in the same
sitting, which read phase 2 as 16.6 / 14.0 / 7.3: −16% json, −15% infix, −14% sql.

The phase-5.1 pair alternated with phase 3 three times in one sitting, which read
phase 3 as 12.6 / 11.4 / 5.9: −14% json, −3% infix, sql unchanged.

The phase-5.2 pair alternated with phase 5.1 three times in one sitting, which read
phase 5.1 as 10.2 / 10.5 / 5.8: −27% json, −13% infix, −25% sql.  Overall against the
baseline: 5.7× json, 5.4× infix, 12.2× sql.

The original profile, mo-sql-parsing (sibling checkout `../mo-sql-parsing`), Python
3.10, one 403-char `SELECT` with joins, subquery, `IN`, `GROUP BY`, `HAVING`,
`ORDER BY`:

```python
import sys; sys.path[:0] = [".", "../mo-sql-parsing"]
import time, mo_sql_parsing as msp
SQL = """SELECT a.id, b.name, SUM(c.amount) AS total, COUNT(*) cnt
FROM accounts a JOIN customers b ON a.cust_id = b.id
LEFT JOIN transactions c ON c.acct = a.id AND c.ts > '2020-01-01'
WHERE a.status IN ('open','pending') AND (b.region = 'EU' OR b.region = 'NA')
  AND NOT EXISTS (SELECT 1 FROM blocked x WHERE x.id = a.id)
GROUP BY a.id, b.name HAVING SUM(c.amount) > 100 ORDER BY total DESC, b.name LIMIT 10"""
msp.parse(SQL); t = time.time()
for _ in range(20): msp.parse(SQL)
print((time.time() - t) / 20 * 1000, "ms")
```

| state                                             | ms/parse |
|---------------------------------------------------|---------:|
| baseline (9.694)                                  |     54   |
| + cache `ParseException.loc`                      |     44   |
| + no cause sorting on the success path            |     34   |
| + no failure accumulation at all (ceiling, no retry yet) |  20 |

Per parse: 3337 `_parse` calls, 3659 `ParseException`s, 1906 `ParseResults` — about
nine exceptions per input character. 29% of `_parse` calls repeat an (element,
position) pair already tried; max recursion depth 58.

cProfile, baseline: ~50% of time is `ParseException.loc` → `causes` → `sort_causes`
→ `compare_causes`, i.e. building and sorting failure-cause trees for a parse that
succeeds. The rest is interpretive overhead: `And.parse_impl`, `_parse`, `isinstance`
(430k calls), `ParseResults` construction and iteration.

## Phase 1 — diagnostics off the hot path (measured 2.7×) — landed in `0d419d2`

Every combinator merges child `failures` into its successful result and every
`ParseException` re-walks its cause tree to answer `.loc`. None of that is needed
unless the top-level parse fails.

- `ParseException.loc` is recursive and uncached (`exceptions.py:69`); `compare_causes`
  calls it up to four times per comparison. Cache it in a slot. −17% alone.
- `And`, `Many`, `MatchFirst`, `Or`, `Forward`, `Group` stop doing
  `failures.extend(result.failures)` (`expressions.py:281,422,523`,
  `enhancement.py:260`); `ParseResults.__init__` stops sorting when `len > 30`
  (`results.py:42`). Successful results carry `failures == []`.
- `And.parse_impl` re-raises with `pe.loc` (`expressions.py:290,294`) — that is what
  triggers the sort on every failed alternative; use `pe.start`.
- `Fast.parse_impl` builds `"expecting one of " + json.dumps(self.all_keys)` on every
  miss (`expressions.py:705,719`); once sorting is gone this is the single largest
  entry (92 misses/parse × a long keyword list). Build the message in
  `ParseException.message`, not in the constructor.
- Keep the messages: `Parser._parseString` catches the failure and re-parses once in
  diagnostic mode (a flag on `Parser` the combinators consult, same shape as
  `do_actions`) to produce the current cause tree. Failures are rare relative to
  successes; paying for diagnostics only then is the standard trade.
- Guards: `tests/test_errors.py`, mo-sql-parsing's error-message tests. Compat:
  `ParseResults.failures` stays as an attribute (mo-sql-parsing parse actions pass it
  through), just empty.

### Which failure cause to keep

Unknowable during the parse: the outer context may still discard the whole subtree,
and only a failed parse ever needs a cause. So do not pick during parsing.

- Fast pass records nothing — no `failures` lists, no `.loc`, no ranking.
- Diagnostic re-parse collects the raw cause trees exactly as today but never ranks
  mid-parse: `best_cause` is already lazy; the eager ranking is `And`'s `pe.loc`
  (`expressions.py:290,294`) and the `len > 30` sort in `ParseResults.__init__`
  (`results.py:42`). Drop both; sort once at the top.
- Cost: a failing parse ≈ fast attempt + diagnostic attempt, about what a failing parse
  costs today (the 54 ms already includes the eager sorts). Net loss only if most
  inputs fail.
- Cheaper option for later: farthest-failure — one `max(pos)` compare per failure and
  the expected set at that position, what most PEG engines do. O(1), but it changes
  messages: `best_cause` prefers named exprs and `msg` over position, and
  `test_errors.py` pins those strings. Keep the full tree on the rare path; revisit
  only if diagnostic mode shows up in a profile.

## Phase 2 — failure is a return value, not an exception (measured −54% sql) — landed in `1c2a8f5`

A three-frame raise/catch chain costs 1.64 µs; the same chain returning costs 0.17 µs.
At 3659 exceptions per parse that was ~6 ms of the 20 ms left after phase 1.

- `parse_impl` and `_parse` return either a `ParseResults` or a failure value.
  `ParseResults.failed` is False and `ParseException.failed` is True, so one attribute
  read decides; truthiness already means something else.
- The failure value is a `ParseException` that is returned, never raised. While
  diagnosing it is a fresh exception carrying the same cause tree as before; otherwise
  it is the shared `FAIL` singleton, so the hot path allocates nothing. Both come from
  `failure()`/`failure_at()` in `exceptions.py`, the one place the mode is consulted.
- `_parse` wraps a returned failure exactly where it used to wrap a caught one, so
  cause trees, `best_cause`, `__contains__` and every message are unchanged.
- Parse actions and `add_condition` still raise `ParseException`; `_parse` catches that
  around the action call only and converts it.
- `ParseSyntaxException` (the `-` guard) is still returned as an ordinary failure and
  still does not stop backtracking — same as before, and still worth revisiting.
- `Many` and `MatchAll` format their expression into the failure message; that string
  is built only while diagnosing.
- Bonus: `NotAny` on an expression with no regex equivalent always succeeded (it raised
  inside its own `try` under a bare `except`). It now consults the child's result.

## Phase 3 — fewer nodes per parse (measured −16% json, −15% infix, −14% sql) — landed in `44d4341`, `83ce94b`, `6f46e28`

1906 `ParseResults` for the 447-char sql benchmark, now 1648; `isinstance` calls per
parse 11535, now 7717.

- `And` asks `isinstance(expr, LookBehind)` and `isinstance(expr, And.SyntaxErrorGuard)`
  once per child at `streamline()` instead of once per child per call: `self.plan` is a
  tuple of `(expr, is_look_behind, is_syntax_guard)` that the loop unpacks. Over half
  the `isinstance` calls in a parse were these two.
- Unannotated `MatchFirst` and `Forward` return the child's result instead of wrapping
  it in a fresh `ParseResults`. The extra level is invisible to `__iter__` and
  `_get_item_by_name`, which already look through an unnamed, non-`Group` result — but
  only from above: the walkers test the *children* of the result they start on, so at
  the root of a lookup the wrapper is what makes a named or `Group` child visible (and,
  for `Forward`, what hides it). So `streamline()` marks the wrapper transparent and the
  parse keeps it for exactly those results. `MatchFirst` also keeps it while diagnosing,
  where the earlier alternatives' failures are the cause tree.
- `Or` parses each alternative once, with the caller's `do_actions`, and keeps the
  longest result. It used to measure every alternative with actions and then parse the
  winner again, running the winning subtree's parse actions twice; neither a parse
  action nor a condition can change the end of the match it is attached to (`_parse` and
  `wrap_parse_action` both refuse), so the second parse could only repeat the first.
  Measuring without actions instead — the original plan — is not viable: it lets
  alternatives that a condition rejects into the running, and mo-sql-parsing's
  `test_issue_218_udf` goes from milliseconds to minutes. The re-measuring loop that
  goes away had two unreachable, broken exits (one returned the `(end, result)` tuple
  instead of the result, the other fell off the end and returned `None`); two tests in
  `test_unit.py` pin what is left of the behaviour.
- Not worth doing, measured in-process against the sql benchmark (both under 1%,
  i.e. inside the noise): returning `FAIL` from `_parse` without calling `failure()`
  (2960 calls per parse), and guarding `And`'s `failures.extend` on the fast path.
- Not transparent: `ParseEnhancement.parse_impl` (`Group` inherits it, and Suppress,
  Dict and OpenDict all carry a parse action, so there is nothing there to win); `Or`
  (13 results per sql parse); `Many`/`Optional`/`ZeroOrMore`/`Combine`/`Group`, whose
  results are real containers — `And` reads `isinstance(result.type, Many)` to tell an
  empty `Optional` from a match.
- `ParseResults.__bool__`/`__iter__`/`_get_item_by_name` walk the tree on every
  `tokens["name"]` (`results.py:44,137,159`); see phase 6.

## Phase 4 — memoization: measure, probably skip

Only 29% of `_parse` calls repeat an (element, position); `Forward` repeats 7 of 87.
A dict probe per call costs about what a token match costs, so a packrat table would
only pay for `And`/`MatchFirst` nodes, and only if phases 1–3 leave them expensive.
Re-measure after phase 3; do not build this first.

## Phase 5 — compile the grammar

This is where "much faster" comes from; the phases above just stop paying for things
nobody asked for.

1. Regex fusion — landed in `a02dd44`, `5df7ee2`, `65cf5ea`, `d3f95bb` (below).
2. Closure compilation — landed (below).

Measured on a small grammar, `ident "=" (number | quoted) ";"` × 100 (1109 chars),
hand-written stand-ins for what each generator would emit:

| variant                                                   | µs/parse | speedup |
|-----------------------------------------------------------|---------:|--------:|
| current engine                                            |     5381 |       — |
| closures: constants captured, `FAIL` return, tuple results|     1103 |    4.9× |
| flat source: leaves inlined, no config loads, no calls    |      925 |    5.8× |
| one fused regex for the whole statement                   |      173 |     31× |

The closure figure includes dropping failure tracking and `ParseResults`, so it is
phases 1–3 plus codegen together. Inlining leaves into flat source adds ~15% over
closures — the parameter-lookup removal is the small part.

The 31× row is a grammar with no parse actions and no names, so all of it fuses.
Phase 5.1 measured how much of a real grammar does, and the answer is: a third of
json, almost none of mo-sql-parsing. Closure compilation is the lever, because it
pays on every element rather than only on the ones a regex can stand in for.

### Phase 5.1 — regex fusion (measured −14% json, −3% infix, 0% sql)

Per parse the benchmarks went 10033 → 7391 `_parse` and 8769 → 5767 `ParseResults`
(json), 4161 → 4001 and 4957 → 4637 (infix), 3290 → 3208 and 1648 → 1630 (sql).

`fuse()` is the protocol: a leaf returns the pattern that matches it, the tokens a
match produces (`None` means the matched text, a tuple is the canonical text a
`Keyword` or `Literal` reports), and how many characters it always consumes.
`__regex__()` is left alone — `Fast` and `NotAny` still own it.

What fuses:

- `Suppress(X)` where X is one regex match. `Suppress` now has its own `parse_impl`
  and no post-parse action, so a suppressed token costs one `ParseResults` instead
  of three, and none at all for the child.
- A run of two or more adjacent children of an `And` that each fuse: one compiled
  pattern joined by the `And`'s own whitespace, one named group per child, and the
  parse loop emits the same N results from `m.span()`. Token names are fine — the
  name is on the element, and the element is what the emitted result points at.
- `And.plain_plan` keeps the unfused rows and is what `parse_impl` walks while
  diagnosing, so failure messages and cause trees are untouched.

Every piece is atomic, because PEG never backtracks into an earlier child:
`Word(alphas) + "x"` must fail on `"abcx"`. Variable-length pieces use the portable
`(?=(?P<f0>…))(?P=f0)` emulation (lookarounds are atomic in `re`); native `(?>…)`
would need Python 3.11. A fixed-length piece is a plain group, and whitespace with
no ignored patterns is `[chars]*(?![chars])`, so only what can give back pays.

What does not fuse, and the counts that say so — measured by instrumenting the
three benchmarks and counting what each shape would absorb:

- Anything with a parse action, a token name on a container, a `Group`, a `Forward`,
  a lookbehind, the `-` guard, or a pattern carrying a backreference. Allowing parse
  actions on leaves was measured: it adds 2 sites and 4 `_parse` calls on sql, none
  elsewhere.
- `Combine(X)`: zero sites on all three benchmarks — mo-sql-parsing's `Combine`s all
  contain elements with parse actions.
- `MatchFirst` of leaves: zero sites on json and infix, one site and 10 calls on sql;
  `Fast` already dispatches these on the first character.
- `Many`/`Optional` of leaves: expressible (an atomic `(?:WS B WS|WS)` alternation
  reproduces the commit), but zero sites — every `Optional` in the benchmarks holds a
  subtree, not a leaf.
- Whole `And`/`MatchFirst` subtrees under a `Suppress`: every `Suppress` site on all
  three benchmarks wraps a single leaf, so the recursive walker would earn nothing.

sql is unchanged because mo-sql-parsing hangs a parse action on nearly every token:
only 7 run sites are reached by the benchmark query, all multi-word keyword phrases
(`select as struct`, `for system_time as of`) that mostly fail, and 9 `Suppress`es,
all of single characters. json wins because `Suppress` of one character is 34% of its
`_parse` calls and its `key : value` member fuses.

### Phase 5.2 — closure compilation (measured −27% json, −13% infix, −25% sql)

`element.compile()` returns a plain function `(string, start) -> ParseResults | FAIL`
that captures what it needs — the children's compiled functions, the whitespace `skip`,
literal strings, compiled patterns, the element itself, the action list. Nothing is read
through `self.parser_config` at parse time.

- `_parse` stays the reference implementation: the diagnostic re-parse, `Debugger` and
  `profile.py` all use it, and the last two install themselves by patching
  `ParserElement._parse`. `Parser._parse_fn()` therefore hands back `self.element._parse`
  while diagnosing or while that attribute is patched, and `self.compiled` otherwise.
  `_scan_string` picks once, outside its loop.
- So compiled code never reads `exceptions.DIAGNOSTICS`, never calls `failure()` — every
  failure is `FAIL` — and `And` always walks its fused `plan`, never `plain_plan`.
- `ParserElement.compile()` is `_with_actions(self, self._compile())`; the default
  `_compile()` is `self.parse_impl`, so an unspecialized class (and any user subclass)
  gets exactly what `_parse` did, one frame cheaper. `_with_actions` returns its argument
  unchanged for the elements with no actions and no `fail_action`, and emits a
  no-fail_action, one-action variant for the rest — which is nearly every mo-sql-parsing
  token.
- `do_actions` is gone from compiled code. `SkipTo` was the only caller that passed
  `False` (its scan), and it stays interpreted; `callDuringTry` then means nothing,
  because compiled code always runs the actions.
- Specialized: `And` (a compile-time tuple of rows, with a tighter loop when no row is a
  lookbehind, a fused run, or a child that can return an empty `Many`; the `-` guard row
  is dropped, since in fast mode it only picks a failure type), `MatchFirst` (with the
  `transparent` shortcut), `Or`, `Fast`, `MatchAll`, `Many`/`ZeroOrMore`/`Optional`,
  `ParseEnhancement` (so `Group`, `Dict`, `OpenDict`), `Suppress`, `Combine`, `LookAhead`,
  `NotAny`, `Forward`, and the leaves `Literal`, `SingleCharLiteral`, `Keyword`,
  `CaselessLiteral`, `Word`, `Char`, `CharsNotIn`, `AnyChar`, `Empty`, `StringEnd`,
  `Regex`. Interpreted: `SkipTo`, `PrecededBy`, and the positional tokens
  (`LineStart`/`LineEnd`/`StringStart`/`WordStart`/`WordEnd`/`White`/`CloseMatch`).
- `Forward` compiles to a trampoline over a one-element cell, so a cycle terminates and a
  `<<` after `finalize()` still takes effect: the cell holds `_recompile` until the first
  parse, and `<<` puts it back. That makes compilation lazy — `Parser.__init__` costs
  0.2 ms on mo-sql-parsing and the first parse pays ~30 ms; the ~0.7 s to build that
  grammar is unchanged.
- `MatchAll` had to be compiled, not left interpreted: its `parse_impl` calls `_parse` on
  every child, which pulled whole subtrees back into the interpreter — 909 of them per
  sql parse. Afterwards the three benchmarks make no interpreted call at all, except the
  `StringEnd` that `parse_all` checks once per parse.
- Not worth doing, measured: a middle `And` loop for rows that need the empty-`Many`
  check but no lookbehind or fused run (no change on any benchmark); a leaner
  `ParseResults.__init__` — dropping the `end == -1` guard and the `DIAGNOSTICS` read is
  20% of that constructor in isolation and 5767 constructions per json parse, but it does
  not show end to end, so `ParseResults` is left alone for phase 6.

What the sql profile looks like now (5 parses, 4.5 ms/parse): `And`'s general loop
3515 calls/0.006 s, `ParseResults.__iter__` 13125/0.006, `_get_item_by_name` 3155/0.003,
`ParseResults.__init__` 8150/0.003, `isinstance` 38030/0.003, `infix.make_tree`
115/0.002, `re.match` 6060/0.002, `Many` 955/0.002. Roughly a quarter of what is left is
result *access* — `__iter__`, `_get_item_by_name`, `items`, `.type`, `.name`,
`__getitem__` — which is phase 6, not the matcher. infix is the extreme case: its own
`make_tree` parse action and `ParseResults.__iter__` are two thirds of its profile, and
`ParserElement.__eq__` is called 55815 times from `make_tree`'s `o == op`. Generated
source (`exec`) is not indicated: no named call overhead is left to remove that codegen
would reach.

### Other targets

1. The regex engine is already another language: fusion hands the matching to `re`'s
   C engine with no toolchain and no wheels. Do this first.
2. Compile the generated flat source with mypyc/Cython. It is the code they like —
   plain functions, ints, strs, no `__class__` games — and mo-sql-parsing's grammar is
   static, so it could ship a pre-generated, pre-compiled parser module. Typically 2–4×
   on what tier 1 leaves; cost is per-Python-version wheels in CI.
3. Emit Rust/C directly: fastest matcher, but parse actions and result materialization
   stay in Python (mo-sql-parsing's actions build the JSON), so every node crosses the
   boundary and the actions cap the win. Pays only if the actions move too, i.e. a
   mo-sql-parsing rewrite. Measure after tiers 1–2; do not start here.

## Phase 6 — typed results ("type markup")

What it does not buy: speed via mypy. mypy checks, it does not compile. mypyc and
Cython compile the *runtime*, not the grammar, and give 1.5–3× on interpretive
overhead; they are blocked today by `result.__class__ = Annotation`
(`enhancement.py:125`), `object.__new__` copies in `copy()`, and the `mo_imports`
placeholder tuples. Revisit after phase 5, when the runtime is small and the
compiled-grammar functions are what a compiler would see.

What it does buy: every annotated element knows the layout of its result at streamline
time. The `ParserElement` is already the type and `ParseResults` its instance; the
missing piece is computing the layout once:

- Precompute `name → child index path` per element so `tokens["name"]` is a slot
  lookup, not the `_get_item_by_name` walk (mo-sql-parsing's parse actions call it
  on nearly every node).
- Emit a `__slots__` class per `Group` (dataclass-like) so consumers get attributes and
  IDE completion; `.type` stays for the tree walkers that need it.

That is the meta-class idea done right, and it is a result-access win; it does not
change match speed.

## Order

0. Land the benchmark above where CI can run it (TODO.md already notes no perf check).
1. Phase 1 — measured, 2.7×, smallest diff.
2. Phase 2, phase 3 — re-measure after each.
3. Phase 5.1 regex fusion and phase 5.2 closures — done. Then phase 6 layout.
4. Phase 4 only if the phase-3 profile says so. mypyc/Cython only after 5.

## Risks

- Error-message equality: `test_errors.py` and mo-sql-parsing's tests pin exact
  strings; the diagnostic re-parse must produce the same cause tree.
- Parse actions that read `tokens.failures` or rely on `callDuringTry` running
  during `Or` measurement.
- Regex fusion changes which element a failure is reported against; diagnostic mode
  must fall back to the unfused tree.
