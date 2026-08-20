# mo_parsing — known defects

Found while writing this repo's PowerShell grammar. None is fixed in this checkout (pyLibrary
r3066) and none has a test. The first has a fix written, quoted below; the other two are read off
the code and want a test that proves the consequence before anyone changes anything.

## A `?` is swallowed into the literal before it, so `MatchFirst` never tries the alternative

`regex.py` builds a literal run with `Word(printables, exclude=r".^$*+{}[]\|()")`. `?` is missing
from that exclude list and `Word` is greedy, so `Regex(r"-?\d+")` parses as a two-character
`Literal("-?")` followed by the digits. `expecting()` reports that tree faithfully, so
`MatchFirst.streamline` files the alternative under `-` and `?` — and input that starts with a
digit never reaches it. The alternative matches `42` on its own and fails inside the `MatchFirst`,
which is how it was found: `parse_powershell.py` spells its number pattern out by hand to dodge it.

A quantifier binds the last character, and the greedy run takes that character too:

| pattern | expecting | min_length | truth |
|---------|-----------|------------|-------|
| `-?\d+` | `-?` | 3 | `-0123456789`, 1 |
| `ab?` | `ab?` | 3 | `a`, 1 |
| `abc*` | `abc` | 0 | `ab`, 2 |
| `colou?r` | `colou?r` | 7 | `colo`, 5 |

Fix: stop the literal run before a character a repetition would bind, using the grammar's own
`repetition` production as the lookahead. `?` stays legal in lead position — the unmodelled
`(?P=name)` backreference parses only because a bare `?` is tolerated there.

    lead_char = Char(printables, exclude=r".^$*+{}[]\|()")
    tail_char = Char(printables, exclude=r".^$*+?{}[]\|()")
    simple_char = Combine(
        lead_char + ZeroOrMore(~(tail_char + repetition) + tail_char, NO_WHITESPACE)
    ) / (lambda t: Literal(t.value()))

Coverage: `expecting()` and `min_length()` for every row of that table; a `MatchFirst` with enough
alternatives to build its lookup matches `42`, `-42` and `3.14` through `Regex(r"-?\d+(?:\.\d+)?")`;
a pattern with a leading `?` still parses; regex construction does not get slower.

## `repeat()` cannot return `Optional`, and reads a non-greedy operator as greedy

`elif mode in "*?"` is a substring test standing in for "is one of", and it is reached first, so
`?`, `*` and the non-greedy `*?` all become `ZeroOrMore`. `elif mode == "?": return Optional(...)`
below it is unreachable, and `+?` becomes `OneOrMore` the same way. `expecting` and `min_length`
cannot tell `Optional` from `ZeroOrMore`, so nothing above notices; the tree is what is wrong, and
non-greedy is silently greedy in it.

Coverage: `Regex("ab?")` builds an `Optional`, not a `ZeroOrMore`; `Regex("ab*?")` and
`Regex("ab+?")` build something that is not their greedy form.

## `Regex.__init__` does not require the whole pattern to parse

`parsed = regex.parse_string(pattern)` has nothing anchoring the end, so a construct the grammar
does not model leaves a tree describing only part of the pattern — while `self.regex` compiles the
whole thing, so matching is right and every question about the tree is wrong. An unmodelled group
is counted character by character:

| pattern | expecting | min_length | truth |
|---------|-----------|------------|-------|
| `ab(?#note)cd` | `ab` | 10 | `ab`, 4 |
| `a\Zb` | `a` | 3 | `a`, 2 |

Over-estimating `min_length` is the dangerous direction: it is what makes a caller skip an
alternative that would have matched, which is the first defect again by another route.

Coverage: a pattern whose unmodelled construct makes `min_length` exceed the input it does match,
inside a `MatchFirst`, still matches — or, if it does not, that is the leak this entry predicts.
