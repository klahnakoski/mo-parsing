# mo_parsing — known defects

The three defects found writing the PowerShell grammar are fixed and tested
(`tests/test_regex.py`): the literal run swallowing `?`, `repeat()`'s unreachable
`Optional`/non-greedy-read-as-greedy, and the unanchored pattern parse. `(?#…)` and `\Z` now
model as zero-width; construction raises on what the grammar cannot parse. Two defects
remain, found while fixing those.

## `\b` never builds a word boundary

`esc_char` precedes `word_edge` in `term`, so `\b` becomes `Literal("b")` —
`Regex(r"\bx").expr` is `Literal("bx")` — and `word_edge` is unreachable. Its action is also
wrong twice over: `NotAny(any_wordchar)` wraps the pattern-grammar element (which matches the
literal text `\w`), and not-followed-by-wordchar is only the trailing edge, not boundary
semantics.

Coverage: `Regex(r"\bcat\b")` matches `cat` in `a cat sat` and not in `concatenate`.

## `\A` is read as `Literal("A")`

`esc_char` turns any unmodelled escape into its bare character. `\Z` maps to `StringEnd`;
`\A` still falls through, so the tree for `\Aab` matches `Aab`.

Coverage: `Regex(r"\Aab").min_length()` is 2 and the tree matches `ab`, not `Aab`.
