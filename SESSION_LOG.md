# Session Log

## 2026-08-20
- suite 284 ran / 0 failed / 44 skipped (py 3.12)
- svn-sync ×2: published mo_parsing@r3069, tests@r3070 (first publish of tests dir);
  BUGS.md arrived inbound
- CLAUDE.md created (33d5bec)
- tests for all three BUGS.md defects (9cef9ae); bug 1 (literal run swallows `?`) was
  already fixed on dev
- fixed bugs 2 and 3 in regex.py (c334ab8): `repeat()` mode dispatch (`?`→Optional,
  `*?`/`+?`→min-match Many); pattern parse anchored with parse_all=True; `(?#…)`→Empty,
  `\Z`→StringEnd; space added to literal char classes (required once anchored)
- the MatchFirst min_length leak BUGS.md predicted did not reproduce;
  test_overestimated_min_length_does_not_hide_match guards it
- BUGS.md rewritten to current truth: three fixed entries removed, two new entries
  (`\b` dead and wrong, `\A` read as literal) — needs svn-sync to publish
- next: `\b` word boundary (see mo_parsing/BUGS.md)
