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
