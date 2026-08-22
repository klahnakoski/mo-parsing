# mo_parsing — known defects

The five defects found writing the PowerShell grammar are fixed and tested
(`tests/test_regex.py`): the literal run swallowing `?`, `repeat()`'s unreachable
`Optional`/non-greedy-read-as-greedy, the unanchored pattern parse, `\A` read as
`Literal("A")`, and `__regex__` stacking a quantifier on a pattern that already carries one
(`Optional(CharsNotIn(...))`, `Optional(OneOrMore(...))`). `(?#…)`, `\Z`, `\A`, and `\b`
model as zero-width, and `\x41`/`\012` are their character.

Construction raises on what the grammar cannot parse. An escaped letter or digit the grammar
does not model is an error, never a literal — `\a`, `\f`, `\v`, `\B`, `\0`, and backreferences
(`\1`) are all rejected, because Python's `re` accepts them and silence would build a tree
that disagrees with the pattern. Escaped punctuation (`\.`, `\-`) stays literal.

## An unmodelled escape inside `[...]` is still its own letter

`escaped_char` is the catch-all for a character class, and it degrades any escape it does not
recognise into the bare character — the defect `esc_char` no longer has. `[\0]` builds the
character `0` where Python builds NUL, so the tree disagrees with the compiled pattern.
Note `\b` is a backspace inside a class and a word boundary outside it, so the two catch-alls
cannot simply share a rule.

Coverage: `Regex(r"[\0]")` raises.

## `CharsNotIn` spells its quantifier with a colon

`CharsNotIn.__init__` (`tokens.py`) builds the repeat suffix as `{min:}` / `{min:max}`.
Python's `re` reads `{2:5}` as the literal text `{2:5}`, so any `min > 1` or finite `max`
produces a pattern that matches the braces instead of repeating. Regex fusion sidesteps it by
claiming a length only when `min == max == 1`.

Coverage: `CharsNotIn("x", min=2).parse_string("ab")` matches `ab`; `CharsNotIn("x",
max=2).parse_string("abc")` matches `ab`.

## `CaselessLiteral` escapes its text twice

`CaselessLiteral` (`tokens.py`) builds `regex_caseless(re.escape(match))`, and
`regex_caseless` escapes on its own (`CaselessKeyword` passes the raw text). Punctuation is
escaped twice, so `CaselessLiteral(".")` cannot match `"."`. Fusion works around it by having
`CaselessLiteral` claim no fixed length.

Coverage: `CaselessLiteral(".").parse_string(".")` matches.

## `NotAny` backtracks where the engine would not

`NotAny` (`enhancement.py`) compiles its child as `(?!child)`. Inside the lookahead `re`
backtracks freely, so `~(Word(alphas) + "x")` finds `abc` + `x` in `"abcx"` and fails, where
the engine's `Word` eats the `x` and the sequence cannot match. Fusion's `regex_atomic`
(`utils.py`) is the building block for the atomic form.

Coverage: `(~(Word(alphas) + "x") + Word(alphas)).parse_string("abcx")` matches `abcx`.

## `Combine` skips its child's parse actions

`Combine.parse_impl` (`enhancement.py`) calls `self.expr.parse_impl` directly instead of
`_parse`, so the actions attached to its immediate child never run; only the grandchildren's
do. `Combine(Suppress(x))` yields `""` because `Suppress` now matches its own regex, but
`Combine(x / action)` still ignores `action`.

Coverage: `Combine(Word(alphas) / (lambda t: "X")).parse_string("ab")` yields `X`.
