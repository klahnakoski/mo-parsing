# TODO

Things brought up during a session; the seed for continuing work in a new one.

## Open

- `\b` in the regex grammar is dead: `esc_char` precedes `word_edge` in `term`, so
  `Regex(r"\bx").expr` is `Literal("bx")`. The `word_edge` action also looks wrong:
  `NotAny(any_wordchar)` wraps the pattern-grammar element (which matches the literal text
  `\w`), and trailing-edge-only is not boundary semantics. Needs a test, then a fix.
- `\A` is still mis-modelled as `Literal("A")` by `esc_char` — same defect class as `\Z`,
  which now maps to `StringEnd`.
- Non-greedy `*?`/`+?` are modelled as minimum-match `Many` (streamlines to `Empty`/operand);
  a true non-greedy construct does not exist.
- BUGS.md coverage asks "regex construction does not get slower" — no perf check written.
- `mo_parsing/BUGS.md` is stale: all three defects are fixed and tested here. Decide update
  vs delete before the next svn-sync (the other repo's `parse_powershell.py` still carries
  the bug-1 workaround).

## Done this session

- svn-sync ×2: published mo_parsing@r3069, tests@r3070; BUGS.md arrived inbound.
- CLAUDE.md created.
- Tests for all three BUGS.md defects in `tests/test_regex.py`; bug 1 (literal run swallows
  `?`) was already fixed on dev.
- Fixed bug 2: `repeat()` mode dispatch (`?`→`Optional`, `*?`/`+?`→min-match `Many`).
- Fixed bug 3: pattern parse anchored (`parse_all=True`); `(?#…)`→`Empty`, `\Z`→`StringEnd`;
  space added to the literal char classes (required once the parse is anchored).
- The MatchFirst min_length leak BUGS.md predicted did not reproduce;
  `test_overestimated_min_length_does_not_hide_match` guards it.
