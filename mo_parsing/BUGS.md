# mo_parsing — known defects

The five defects found writing the PowerShell grammar are fixed and tested
(`tests/test_regex.py`): the literal run swallowing `?`, `repeat()`'s unreachable
`Optional`/non-greedy-read-as-greedy, the unanchored pattern parse, `\A` read as
`Literal("A")`, and `__regex__` stacking a quantifier on a pattern that already carries one
(`Optional(CharsNotIn(...))`, `Optional(OneOrMore(...))`). `(?#…)`, `\Z`, `\A`, and `\b`
model as zero-width, and `\x41`/`\012` are their character.

Construction raises on what the grammar cannot parse. An escaped letter or digit the grammar
does not model is an error, never a literal — `\a`, `\f`, `\v`, `\B`, and backreferences
(`\1`) are all rejected, because Python's `re` accepts them and silence would build a tree
that disagrees with the pattern. Escaped punctuation (`\.`, `\-`) stays literal.

## `\0x41` disagrees with Python

`escaped_hex` reads `\0x` as a hex escape, so `\0x41` builds `Literal("A")`. Python's `re`
reads the same text as NUL followed by `x41`, and `Regex` matches with the compiled pattern —
so the tree and the matcher disagree. The spelling predates the escape rules reaching the top
level; `\x41` is unambiguous and should be used instead.

Coverage: `Regex(r"\0x41").parse_string("A")` raises, while its tree matches `A`.
