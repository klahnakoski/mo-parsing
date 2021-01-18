# encoding: utf-8

# UNDER THE MIT LICENSE
#
# Contact: kyle@lahnakoski.comd
from string import whitespace

from mo_future import unichr

from mo_parsing.core import add_reset_action
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
from mo_parsing.tokens import Literal, AnyChar, Keyword, LineStart, LineEnd, Word, SingleCharLiteral
from mo_parsing.utils import printables, alphanums, nums, hexnums, Log, listwrap, regex_compile


def hex_to_char(t):
    return Literal(unichr(int(t.value().lower().split("x")[1], 16)))


def to_range(tokens):
    min_ = tokens["min"].parser_config.match
    max_ = tokens["max"].parser_config.match
    return Char("".join(unichr(i) for i in range(ord(min_), ord(max_) + 1)))


def to_bracket(tokens):
    acc = []
    for e in listwrap(tokens["body"].value()):
        if isinstance(e, SingleCharLiteral):
            acc.append(e.parser_config.match)
        elif isinstance(e, Char):
            acc.extend(e.parser_config.include)
        else:
            Log.error("programmer error")
    if tokens["negate"]:
        return Char(exclude=acc)
    else:
        return Char(acc)


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

    operand, operator = tokens
    mode = operator["mode"]
    if mode == "*":
        return ZeroOrMore(operand)
    elif mode == "+":
        return OneOrMore(operand)
    elif mode == "?":
        return Optional(operand)
    elif operator["exact"]:
        return Many(operand, exact=int(operator["exact"]))
    else:
        return Many(operand, min_match=int(operator["min"]), max_match=int(operator["max"]))

engine = Engine("")
engine.use()

#########################################################################################
# SQUARE BRACKETS

any_whitechar = Literal("\\s").addParseAction(lambda: Char(whitespace))
not_whitechar = Literal("\\S").addParseAction(lambda: Char(exclude=whitespace))
any_wordchar = Literal("\\w").addParseAction(lambda: Char(alphanums + "_"))
not_wordchar = Literal("\\W").addParseAction(lambda: Char(exclude=alphanums + "_"))
any_digitchar = Literal("\\d").addParseAction(lambda: Char(nums))
not_digitchar = Literal("\\D").addParseAction(lambda: Char(exclude=nums))
bs_char = Literal("\\\\").addParseAction(lambda: Literal("\\"))
tab_char = Literal("\\t").addParseAction(lambda: Literal("\t"))
CR = Literal("\\n").addParseAction(lambda: Literal("\n"))
LF = Literal("\\r").addParseAction(lambda: Literal("\r"))
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
escapedChar = (~macro + Combine("\\" + AnyChar())).addParseAction(lambda t: Literal(t.value()[1]))
plainChar = Char(exclude=r"\]").addParseAction(lambda t: Literal(t.value()))

escapedHexChar = Combine(
    (Literal("\\0x") | Literal("\\x") | Literal("\\X"))  # lookup literals is faster
    + OneOrMore(Char(hexnums))
).addParseAction(hex_to_char)

escapedOctChar = Combine(
    Literal("\\0") + OneOrMore(Char("01234567"))
).addParseAction(lambda t: Literal(unichr(int(t.value()[2:], 8))))

singleChar = escapedHexChar | escapedOctChar | escapedChar | plainChar

charRange = Group(singleChar("min") + "-" + singleChar("max")).addParseAction(to_range)

brackets = (
    "["
    + Optional("^")("negate")
    + OneOrMore(Group(charRange | singleChar | macro )("body"))
    + "]"
).addParseAction(to_bracket)

#########################################################################################
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

repetition = Group("{" + repetition | (Literal("*?") | Literal("+?") | Char("*+?"))("mode"))

ahead = ("(?=" + regex + ")").addParseAction(lambda t: FollowedBy(t["value"]))
not_ahead = ("(?!" + regex + ")").addParseAction(lambda t: NotAny(t["value"]))
behind = ("(?<=" + regex + ")").addParseAction(lambda t: Log.error("not supported"))
not_behind = ("(?<!" + regex + ")").addParseAction(lambda t: Log.error("not supported"))
non_capture = ("(?:" + regex + ")").addParseAction(lambda t: t["value"])
named = (
    "(?P<" + Word(alphanums + "_")("name") + ">" + regex + ")"
).addParseAction(name_token)
group = ("(" + regex + ")").addParseAction(name_token)

term = (
    macro
    | simple_char
    | brackets
    | ahead
    | not_ahead
    | behind
    | not_behind
    | non_capture
    | named
    | group
)

more = (term + Optional(repetition)).addParseAction(repeat)
sequence = OneOrMore(more).addParseAction(lambda t: And(t))
regex << (
    delimitedList(sequence, separator="|")
    .set_token_name("value")
    .addParseAction(lambda t: MatchFirst(t).streamline())
    .streamline()
)


def srange(expr):
    pattern = brackets.parseString(expr).value()
    chars = set()

    def drill(e):
        if isinstance(e, Literal):
            chars.add(e.parser_config.match)
        elif isinstance(e, Char):
            chars.update(c for c in e.parser_config.include)
        elif isinstance(e, MatchFirst):
            for ee in e.exprs:
                drill(ee)
        elif isinstance(e, And):
            drill(e.exprs[0].expr)
        else:
            Log.error("logic error")
    drill(pattern)
    return "".join(sorted(chars))


def Regex(pattern):
    output = Combine(regex.parseString(pattern).value()).streamline()
    # WE ASSUME IT IS SAFE TO ASSIGN regex (NO SERIOUS BACKTRACKING PROBLEMS)
    output.regex = regex_compile(pattern)
    return output


engine.release()
