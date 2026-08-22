# Session Log

## 2026-08-22
- suite 313 ran / 0 err / 44 skip (py 3.10); mo-sql-parsing subset (test_simple, test_errors,
  test_mysql, test_bigquery, test_null, test_postgres) 339 / 0 / 4 skip against this checkout
- speed campaign (faster.md) phases 1, 2, 3, 5.1 landed on dev via opus sub-agent worktrees;
  tests/bench.py json/infix/sql 42.9/49.4/52.6 → 10.1/10.5/5.7 ms; error messages unchanged
- phase 5.2 (closure compilation) in flight: sub-agent in worktree .claude/worktrees/phase5b,
  branch phase5b-closures, unmerged — merge, re-run both suites and bench, remove the worktree
- phase 4 dropped by decision; four defects found by fusion recorded in mo_parsing/BUGS.md (58d2dfd)
- mo-black run on tests/bench.py and tests/test_fusion.py only; mo_parsing/*.py formatting
  deferred until phase 5.2 merges (it would conflict with that branch)
- svn-sync pending for mo_parsing and tests (the 08-20 BUGS.md rewrite is still unpublished too)
- next: merge phase 5.2, then phase 6 (result layout)
