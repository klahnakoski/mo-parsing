# TODO

The live work queue; the seed for continuing work in a new session. History is in
SESSION_LOG.md.

- svn-sync to publish phase 5.2 and the mo-black pass (`mo_parsing`, `tests`)
- the four defects the fusion work added to `mo_parsing/BUGS.md`: `CharsNotIn` quantifier,
  `CaselessLiteral` escape, `NotAny` backtracking, `Combine` skipping child actions
- fix `\b` and `\A` modelling in the regex grammar — defects stated in `mo_parsing/BUGS.md`
- a true non-greedy construct does not exist: `*?`/`+?` are modelled as minimum-match `Many`
  (streamlines to `Empty`/operand)
- BUGS.md coverage asks "regex construction does not get slower" — `tests/bench.py` measures
  parse time, not construction time
- grammar construction dominates first use downstream: building mo-sql-parsing's grammar costs
  ~250ms, against ~1.5ms to then parse a statement. No hotspot in the caller — it is all element
  construction here. Two candidates were measured and neither pays, so do not re-derive them:
  giving `Fast.__init__` a cheap exception instead of `Log.error("not useful")` and removing the
  dict churn in `ParserElement.set_config` together move 251ms to 246ms.
- `Fast.__init__` uses `Log.error("not useful")` as control flow — `expressions.py`, raised 234
  times per mo-sql-parsing build and swallowed by the two `except` blocks in `_alternating`. Each
  raise builds an `Except` with a full `get_stacktrace()`. Worth fixing as a design matter (an
  expected outcome is not an error), not as a speed matter; see the measurement above.
- a built parser cannot be pickled — `wrap_parse_action.<locals>.wrapper` is a local closure — so
  downstream projects cannot cache a finalized grammar to skip the construction cost.
