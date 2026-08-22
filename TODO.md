# TODO

The live work queue; the seed for continuing work in a new session. History is in
SESSION_LOG.md.

- speed campaign (`faster.md`): phase 6 result layout (name → slot lookup; `make_tree`'s `o == op` scan)
- svn-sync to publish phase 5.2 and the mo-black pass (`mo_parsing`, `tests`)
- the four defects the fusion work added to `mo_parsing/BUGS.md`: `CharsNotIn` quantifier,
  `CaselessLiteral` escape, `NotAny` backtracking, `Combine` skipping child actions
- fix `\b` and `\A` modelling in the regex grammar — defects stated in `mo_parsing/BUGS.md`
- a true non-greedy construct does not exist: `*?`/`+?` are modelled as minimum-match `Many`
  (streamlines to `Empty`/operand)
- BUGS.md coverage asks "regex construction does not get slower" — `tests/bench.py` measures
  parse time, not construction time
