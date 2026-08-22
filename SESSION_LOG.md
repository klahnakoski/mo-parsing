# Session Log

## 2026-08-22
- suite 328 ran / 0 err / 44 skip (py 3.10); mo-sql-parsing subset (test_simple, test_errors,
  test_mysql, test_bigquery, test_null, test_postgres) 339 / 0 / 4 skip against this checkout
- speed campaign (faster.md) phases 1, 2, 3, 5.1, 5.2 landed on dev via opus sub-agent worktrees
  (all merged, worktrees removed); tests/bench.py json/infix/sql 42.9/49.4/52.6 → 7.9/9.4/4.4 ms;
  error messages unchanged; no interpreted _parse call left on the benches
- phase 4 dropped by decision; four defects found by fusion recorded in mo_parsing/BUGS.md (58d2dfd)
- mo-black run over all touched mo_parsing/*.py and tests (98a7b4e)
- svn-sync: published mo_parsing@r3088, tests@r3089 (before 5.2); no inbound. 5.2 + formatting
  still to publish
- next: phase 6 (result layout)
