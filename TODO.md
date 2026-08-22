# TODO

The live work queue; the seed for continuing work in a new session. History is in
SESSION_LOG.md.

- speed campaign (`faster.md`): phase 5.2 closure compilation, then phase 6 result layout
- mo-black pass over the `mo_parsing/*.py` the speed work touched, once phase 5.2 lands
- the four defects the fusion work added to `mo_parsing/BUGS.md`: `CharsNotIn` quantifier,
  `CaselessLiteral` escape, `NotAny` backtracking, `Combine` skipping child actions
- fix `\b` and `\A` modelling in the regex grammar — defects stated in `mo_parsing/BUGS.md`
- a true non-greedy construct does not exist: `*?`/`+?` are modelled as minimum-match `Many`
  (streamlines to `Empty`/operand)
- BUGS.md coverage asks "regex construction does not get slower" — `tests/bench.py` measures
  parse time, not construction time
