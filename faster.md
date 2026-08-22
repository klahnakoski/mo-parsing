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

## Phase 2 — failure is a return value, not an exception (est. −25% of what remains)

A three-frame raise/catch chain costs 1.64 µs; the same chain returning costs 0.17 µs.
At 3659 exceptions per parse that is ~6 ms of the 20 ms left after phase 1.

- `parse_impl` returns a `FAIL` sentinel; `_parse` and every combinator test
  `is FAIL`. ~30 `parse_impl` sites, mechanical.
- Only `ParseFatalException` and `And.SyntaxErrorGuard` still raise. Parse actions and
  `add_condition` that raise `ParseException` are caught at the `_parse` boundary and
  converted to `FAIL`.
- Diagnostic mode (phase 1) is where the exception objects get built; the fast path
  records nothing but the farthest failure position if even that.

## Phase 3 — fewer nodes per parse (est. −15–25%)

- Transparent wrappers: unannotated `MatchFirst`, `Forward`, `Optional`, `Group`-less
  `ParseEnhancement` each wrap the child in a fresh `ParseResults`
  (`expressions.py:524`, `enhancement.py:67,671`). 1906 results for 403 chars.
  `streamline()` already collapses some; mark the rest transparent and return the
  child's result as-is.
- `Or` parses every alternative with actions enabled to measure its end, then parses the
  winner again (`expressions.py:400,421`). Parse without actions, keep the winning
  result when only one matched.
- `And.parse_impl` does two `isinstance` checks per child per call
  (`expressions.py:272,276`); precompute per-child flags at streamline.
- `ParseResults.__bool__`/`__iter__`/`_get_item_by_name` walk the tree on every
  `tokens["name"]` (`results.py:44,137,159`); see phase 6.

## Phase 4 — memoization: measure, probably skip

Only 29% of `_parse` calls repeat an (element, position); `Forward` repeats 7 of 87.
A dict probe per call costs about what a token match costs, so a packrat table would
only pay for `And`/`MatchFirst` nodes, and only if phases 1–3 leave them expensive.
Re-measure after phase 3; do not build this first.

## Phase 5 — compile the grammar (est. 2–5× over the phase-3 result)

This is where "much faster" comes from; the phases above just stop paying for things
nobody asked for.

1. Regex fusion, pure Python. `__regex__()` already exists on every element. At
   streamline, a run of adjacent children inside an `And` (or a whole `MatchFirst`)
   that have no parse actions and no names fuses into one compiled pattern: one
   `re.match` with groups replaces N `_parse` calls, N `ParseResults`, N whitespace
   skips. `Fast` is this idea for first-character dispatch only; generalize it.
2. Closure compilation. `element.compile()` returns a plain function
   `(string, start) -> result | FAIL` with children captured as locals — no
   `_parse` → `parse_impl` dispatch, no `self.parser_config.x` namedtuple loads, no
   `isinstance` at parse time. `Parser.__init__` compiles once. Source-text generation
   (`exec`) only if closures still show measurable call overhead.

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
closures — the parameter-lookup removal is the small part. Regex fusion is the lever.

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
3. Phase 5.1 regex fusion, then phase 6 layout, then phase 5.2 closures.
4. Phase 4 only if the phase-3 profile says so. mypyc/Cython only after 5.

## Risks

- Error-message equality: `test_errors.py` and mo-sql-parsing's tests pin exact
  strings; the diagnostic re-parse must produce the same cause tree.
- Parse actions that read `tokens.failures` or rely on `callDuringTry` running
  during `Or` measurement.
- Regex fusion changes which element a failure is reported against; diagnostic mode
  must fall back to the unfused tree.
