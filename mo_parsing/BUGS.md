# mo_parsing — known defects

None. The five defects found writing the PowerShell grammar are fixed and tested
(`tests/test_regex.py`): the literal run swallowing `?`, `repeat()`'s unreachable
`Optional`/non-greedy-read-as-greedy, the unanchored pattern parse, `\A` read as
`Literal("A")`, and `__regex__` stacking a quantifier on a pattern that already carries one
(`Optional(CharsNotIn(...))`, `Optional(OneOrMore(...))`). `(?#…)`, `\Z`, `\A`, and `\b` model as zero-width; construction raises on
what the grammar cannot parse.
