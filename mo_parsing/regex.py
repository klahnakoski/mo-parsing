# encoding: utf-8

# UNDER THE MIT LICENSE
#
# Contact: kyle@lahnakoski.comd
from string import whitespace

from mo_future import unichr

from mo_parsing.core import add_reset_action
from mo_parsing.debug import Debugger
from mo_parsing.engine import Engine
from mo_parsing.enhancement import (
    Char,
    NotAny,
    ZeroOrMore,
    OneOrMore,
    Optional,
    Many,
    Combine,
    Group,
    Forward,
    FollowedBy,
)
from mo_parsing.expressions import MatchFirst, And
from mo_parsing.infix import delimitedList
from mo_parsing.tokens import Literal, AnyChar, Keyword, LineStart, LineEnd, Word
from mo_parsing.utils import printables, alphanums, nums, hexnums, Log


def to_range(tokens):
    min_ = tokens["min"].parser_config.match
    max_ = tokens["max"].parser_config.match
    return Char([unichr(i) for i in range(ord(min_), ord(max_) + 1)])


def to_bracket(tokens):
    output = MatchFirst(tokens["body"].value())
    if tokens["negate"]:
        output = NotAny(output)+AnyChar()
    return output


num_captures = 0


def _reset():
    global num_captures
    num_captures = 0


add_reset_action(_reset)


def name_token(tokens):
    global num_captures
    num_captures += 1

    n = tokens["name"]
    v = tokens["value"]
    if not n:
        n = str(num_captures)
    return v.set_token_name(n)


def repeat(tokens):
    if tokens.length() == 1:
        return tokens.value()

    operand, operator = tokens.value()
    mode = operator["mode"]
    if mode == "*":
        return ZeroOrMore(operand)
    elif mode == "+":
        return OneOrMore(operand)
    elif mode == "?":
        return Optional(operand)
    elif operator["exact"]:
        return Many(operand, exact=operator["exact"])
    else:
        return Many(operand, min_match=operator["min"], max_match=operator["max"])


def cleanup(tokens):
    return tokens.value()


engine = Engine("")
engine.use()

# DEFINE PATTERN IN SQUARE BRACKETS

any_whitechar = Literal("\\s").addParseAction(lambda: Char(whitespace))
not_whitechar = Literal("\\S").addParseAction(lambda: ~Char(whitespace) + AnyChar())
any_wordchar = Literal("\\w").addParseAction(lambda: Char(alphanums + "_"))
not_wordchar = Literal("\\W").addParseAction(lambda: ~Char(alphanums + "_") + AnyChar())
any_digitchar = Literal("\\d").addParseAction(lambda: Char(nums))
not_digitchar = Literal("\\D").addParseAction(lambda: ~Char(nums) + AnyChar())
bs_char = Literal("\\\\").addParseAction(lambda: "\\")
tab_char = Literal("\\t").addParseAction(lambda: "\t")
CR = Literal("\\n").addParseAction(lambda: "\n")
LF = Literal("\\r").addParseAction(lambda: "\r")
any_char = Literal(".").addParseAction(lambda: AnyChar())

macro = (
    any_whitechar
    | any_wordchar
    | any_digitchar
    | not_digitchar
    | not_wordchar
    | not_whitechar
    | CR
    | LF
    | any_char
    | bs_char
    | tab_char
)
escapedChar = (
    ~macro + Combine("\\" + Char(printables))
).addParseAction(lambda t: Literal(t.value()[1]))
plainChar = Char(
    "".join(c for c in printables if c not in r"-\]") + " "
).addParseAction(lambda t: Literal(t.value()))

escapedHexChar = (
    Literal("\\")
    + Optional(Literal("0"))
    + Keyword("x", caseless=True)
    + OneOrMore(Char(hexnums))
).addParseAction(lambda t: Literal(unichr(int(t.value(), 16))))

escapedOctChar = (
    Literal("\\")
    + Optional(Literal("0"))
    + Keyword("x", caseless=True)
    + OneOrMore(Char("01234567"))
).addParseAction(lambda t: Literal(unichr(int(t, 16))))

singleChar = macro | escapedHexChar | escapedOctChar | escapedChar | plainChar

charRange = Group(singleChar("min") + "-" + singleChar("max")).addParseAction(to_range)

brackets = (
    "["
    + Optional("^")("negate")
    + Group(OneOrMore(charRange | singleChar))("body")
    + "]"
).addParseAction(to_bracket)

# REGEX
regex = Forward()

more_macros = (
    Literal("^").addParseAction(lambda: LineStart())
    | Literal("$").addParseAction(lambda: LineEnd())
    | Literal("\\b").addParseAction(lambda: NotAny(any_wordchar))
)

simple_char = Char(
    "".join(c for c in printables if c not in r".^$*+{}[]\|()") + " "
).addParseAction(lambda t: Literal(t.value()))


with Engine():
    # ALLOW SPACES IN THE RANGE
    repetition = (
        Word(nums)("exact") + "}"
        | Word(nums)("min") + "," + Word(nums)("max") + "}"
        | Word(nums)("min") + "," + "}"
        | "," + Word(nums)("max") + "}"
    )

repetition = Group("{" + repetition | Char("*+?")("mode"))

ahead = ("(?=" + regex + ")").addParseAction(lambda t: FollowedBy(t))
not_ahead = ("(?!" + regex + ")").addParseAction(lambda t: NotAny(t))
behind = ("(?<=" + regex + ")").addParseAction(lambda t: Log.error("not supported"))
not_behind = ("(?<!" + regex + ")").addParseAction(lambda t: Log.error("not supported"))
non_capture = "(?:" + regex + ")"
named = (
    "(?P<" + Word(alphanums + "_")("name") + ">" + regex("value") + ")"
).addParseAction(name_token)
group = ("(" + regex("value") + ")").addParseAction(name_token)

term = (
    macro
    | brackets
    | ahead
    | not_ahead
    | behind
    | not_behind
    | non_capture
    | named
    | group
    | simple_char
)

more = (term + Optional(repetition)).addParseAction(repeat)
sequence = OneOrMore(more).addParseAction(lambda t: And(t))
regex << delimitedList(sequence).addParseAction(lambda t: MatchFirst(t))


def srange(expr):
    pattern = brackets.parseString(expr)

    chars = set()
    for e in pattern.exprs:
        if isinstance(e, Literal):
            chars.add(e.parser_config.match)
        elif isinstance(e, Char):
            chars.update(c for c in e.parser_config.charset)
        else:
            Log.error("logic error")
    return "".join(sorted(chars))


def Regex(pattern):
    with Debugger():
        return regex.parseString(pattern)


engine.release()
