# mo_parsing — known defects

The three defects found writing the PowerShell grammar are fixed and tested
(`tests/test_regex.py`): the literal run swallowing `?`, `repeat()`'s unreachable
`Optional`/non-greedy-read-as-greedy, and the unanchored pattern parse. `(?#…)`, `\Z`, and `\b`
now model as zero-width; construction raises on what the grammar cannot parse. One defect
remains, found while fixing those.

## `\A` is read as `Literal("A")`

`esc_char` turns any unmodelled escape into its bare character. `\Z` maps to `StringEnd`;
`\A` still falls through, so the tree for `\Aab` matches `Aab`.

Coverage: `Regex(r"\Aab").min_length()` is 2 and the tree matches `ab`, not `Aab`.
