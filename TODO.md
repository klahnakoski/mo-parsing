# TODO

The live work queue; the seed for continuing work in a new session. History is in
SESSION_LOG.md.

- fix `\b` and `\A` modelling in the regex grammar — defects stated in `mo_parsing/BUGS.md`
- a true non-greedy construct does not exist: `*?`/`+?` are modelled as minimum-match `Many`
  (streamlines to `Empty`/operand)
- BUGS.md coverage asks "regex construction does not get slower" — no perf check written
- svn-sync to publish the BUGS.md rewrite and the fixes
