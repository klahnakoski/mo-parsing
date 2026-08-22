# encoding: utf-8

# UNDER THE MIT LICENSE
#
# Contact: kyle@lahnakoski.com
from collections import OrderedDict
from string import whitespace

from mo_future import unichr, is_text
from mo_imports import export

from mo_parsing.core import add_reset_action
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
    LookAhead,
    ParseEnhancement,
    LookBehind,
)
from mo_parsing.exceptions import FAIL, failure
from mo_parsing.expressions import MatchFirst, And
from mo_parsing.infix import delimited_list
from mo_parsing.results import ParseResults, Annotation
from mo_parsing.tokens import (
    Literal,
    AnyChar,
    LineStart,
    LineEnd,
    StringEnd,
    StringStart,
    Word,
    SingleCharLiteral,
    Empty,
)
from mo_parsing.utils import (
    printables,
    alphas,
    alphanums,
    nums,
    hexnums,
    Log,
    enlist,
    regex_compile,
    ParseException,
)
from mo_parsing.whitespaces import Whitespace, NO_WHITESPACE

__all__ = ["Regex"]


def hex_to_char(t):
    return Literal(unichr(int(t.value().lower().split("x")[1], 16)))


def to_range(tokens):
    min_ = tokens["min"].parser_config.match
    max_ = tokens["max"].parser_config.match
    return Char("".join(unichr(i) for i in range(ord(min_), ord(max_) + 1)))


def to_bracket(tokens):
    acc = []
    for e in enlist(tokens["body"].value()):
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


def INC():
    global num_captures
    num_captures += 1


def DEC():
    global num_captures
    num_captures -= 1


def name_token(tokens):
    with NO_WHITESPACE:
        n = tokens["name"]
        v = tokens["value"]
        if not n:
            n = str(num_captures)
        return Combine(v).set_token_name(n)


def repeat(tokens):
    if tokens.length() == 1:
        return tokens.value()

    try:
        operand, operator = tokens
    except Exception as cause:
        Log.error("not expected", cause=cause)

    mode = operator["mode"]
    if not mode:
        if operator["exact"]:
            return Many(operand, NO_WHITESPACE, exact=int(operator["exact"]))
        else:
            return Many(
                operand,
                NO_WHITESPACE,
                min_match=int(operator["min"]),
                max_match=int(operator["max"]),
            )
    elif mode == "*?":
        # NON-GREEDY, WITH NOTHING FOLLOWING, MATCHES ZERO
        return Many(operand, NO_WHITESPACE, min_match=0, max_match=0)
    elif mode == "+?":
        # NON-GREEDY, WITH NOTHING FOLLOWING, MATCHES ONE
        return Many(operand, NO_WHITESPACE, exact=1)
    elif mode == "*":
        return ZeroOrMore(operand, NO_WHITESPACE)
    elif mode == "+":
        return OneOrMore(operand, NO_WHITESPACE)
    elif mode == "?":
        return Optional(operand, NO_WHITESPACE)
    else:
        Log.error("not expected")


NO_WHITESPACE.use()

#########################################################################################
# SQUARE BRACKETS

any_whitechar = Literal("\\s") / (lambda: Char(whitespace))
not_whitechar = Literal("\\S") / (lambda: Char(exclude=whitespace))
any_wordchar = Literal("\\w") / (lambda: Char(alphanums + "_"))
not_wordchar = Literal("\\W") / (lambda: Char(exclude=alphanums + "_"))
any_digitchar = Literal("\\d") / (lambda: Char(nums))
not_digitchar = Literal("\\D") / (lambda: Char(exclude=nums))
bs_char = Literal("\\\\") / (lambda: Literal("\\"))
tab_char = Literal("\\t") / (lambda: Literal("\t"))
CR = Literal("\\n") / (lambda: Literal("\n"))
LF = Literal("\\r") / (lambda: Literal("\r"))
any_char = Literal(".") / (lambda: AnyChar())

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
escaped_char = (~macro + Combine("\\" + AnyChar())) / (lambda t: Literal(t.value()[1]))
plain_char = Char(exclude=r"\]") / (lambda t: Literal(t.value()))

escaped_hex = (
    Combine(
        (Literal("\\x") | Literal("\\X"))  # lookup literals is faster
        + OneOrMore(Char(hexnums), NO_WHITESPACE)
    )
    / hex_to_char
)

escaped_oct = Combine(
    Literal("\\0") + OneOrMore(Char("01234567"), NO_WHITESPACE)
) / (lambda t: Literal(unichr(int(t.value()[2:], 8))))

single_char = escaped_hex | escaped_oct | escaped_char | plain_char

range_char = Group(single_char("min") + "-" + single_char("max")) / to_range

brackets = (
    "["
    + Optional("^", NO_WHITESPACE)("negate")
    + OneOrMore(Group(range_char | single_char | macro)("body"), NO_WHITESPACE)
    + "]"
) / to_bracket

#########################################################################################
# REGEX
regex = Forward()

line_start = Literal("^") / (lambda: LineStart())
line_end = Literal("$") / (lambda: LineEnd())
word_char = Char(alphanums + "_")
# A BOUNDARY IS A WORD/NON-WORD TRANSITION, EITHER DIRECTION
word_edge = Literal("\\b") / (lambda: MatchFirst([
    And([NotAny(LookBehind(word_char)), LookAhead(word_char)], NO_WHITESPACE),
    And([LookBehind(word_char), NotAny(word_char)], NO_WHITESPACE),
]))
string_end = Literal("\\Z") / (lambda: StringEnd())
string_start = Literal("\\A") / (lambda: StringStart())
# AN UNMODELLED ALPHANUMERIC ESCAPE WOULD SILENTLY BECOME ITSELF
esc_char = ("\\" + Char(exclude=alphanums)) / (lambda t: Literal(t.value()[1]))

with Whitespace():
    # ALLOW SPACES IN THE RANGE
    repetition = (
        Word(nums)("exact") + "}"
        | Word(nums)("min") + "," + Word(nums)("max") + "}"
        | Word(nums)("min") + "," + "}"
        | "," + Word(nums)("max") + "}"
    )

repetition = Group(
    "{" + repetition | (Literal("*?") | Literal("+?") | Char("*+?"))("mode")
)

# A LEADING `?` IS NOT A REPETITION, AS IN THE UNMODELLED `(?P=name)`
lead_char = Char(printables + " ", exclude=r".^$*+{}[]\|()")
tail_char = Char(printables + " ", exclude=r".^$*+?{}[]\|()")
# A REPETITION BINDS THE LAST CHARACTER ONLY, SO THE RUN STOPS BEFORE IT
simple_char = Combine(
    lead_char + ZeroOrMore(~(tail_char + repetition) + tail_char, NO_WHITESPACE)
) / (lambda t: Literal(t.value()))

LB = Char("(")

ahead = ("(?=" + regex + ")") / (lambda t: LookAhead(t["value"]))
not_ahead = ("(?!" + regex + ")") / (lambda t: NotAny(t["value"]))
behind = ("(?<=" + regex + ")") / (lambda t: LookBehind(t["value"]))
not_behind = ("(?<!" + regex + ")") / (lambda t: Log.error("not supported"))
non_capture = ("(?:" + regex + ")") / (lambda t: t["value"])
comment = (
    "(?#" + ZeroOrMore(Char(exclude=")"), NO_WHITESPACE) + ")"
) / (lambda: Empty())
# conditional = ("(?" + try_match + "|" + else_match + ")")
# recursive = ("(?R)")
# TODO: match previous capture (3)

named = (
    (Literal("(?P<") / INC + Word(alphanums + "_")("name") + ">" + regex + ")")
    / name_token
    / DEC
)
group = ((LB / INC) + regex + ")") / name_token / DEC

term = (
    macro
    | simple_char
    | string_end
    | string_start
    | word_edge
    | escaped_hex
    | escaped_oct
    | esc_char
    | brackets
    | ahead
    | not_ahead
    | behind
    | not_behind
    | comment
    | non_capture
    | named
    | group
)

more = (term + Optional(repetition, NO_WHITESPACE)) / repeat
sequence = OneOrMore(more, NO_WHITESPACE) / (lambda t: And(t, NO_WHITESPACE))
regex << (
    delimited_list(sequence, separator="|").set_token_name("value")
    / (lambda t: MatchFirst(enlist(t.value())).streamline())
).streamline()
regex = regex.finalize()

parameters = (
    "\\" + Char(alphanums)("name") | "\\g<" + Word(alphas, alphanums)("name") + ">"
) / (lambda t: t["name"])
NO_WHITESPACE.release()


class Regex(ParseEnhancement):
    """
    Converter to concatenate all matching tokens to a single string.
    """

    __slots__ = ["regex"]

    def __init__(self, pattern):
        """
        :param pattern:  THE REGEX PATTERN
        :param asGroupList: RETURN A LIST OF CAPTURED GROUPS /1, /2, /3, ...
        """
        parsed = regex.parse_string(pattern, parse_all=True)
        ParseEnhancement.__init__(self, parsed.value().streamline())
        # WE ASSUME IT IS SAFE TO ASSIGN regex (NO SERIOUS BACKTRACKING PROBLEMS)
        self.streamlined = True
        self.regex = regex_compile(pattern)

    def copy(self):
        output = ParseEnhancement.copy(self)
        output.regex = self.regex
        return output

    def capture_groups(self):
        """
        ADD A SPECIAL PARSE ACTION TO PROVIDE THE NUMBERED (eg "1") AND
        NAMED GROUPS (eg (?P<name>...)
        """

        def group_list(tokens):
            start, end = tokens.start, tokens.end
            # RE-MATCH  :(
            sub_string = tokens.tokens[0]
            found = tokens.type.regex.match(sub_string)
            lookup = dict(reversed(p) for p in found.re.groupindex.items())
            ann = []
            pe = 0
            for i, (s, e) in enumerate(found.regs[1:], start=1):
                if s == -1:
                    continue  # NOT FOUND
                g = sub_string[s:e]
                if pe <= s:
                    ann.append(g)
                pe = e
                ii = chr(i + ord("0"))
                ann.append(Annotation(ii, s + start, e + start, [g]))
                n = lookup.get(i)
                if n:
                    ann.append(Annotation(n, s + start, e + start, [g]))
            return ParseResults(_plain_group, start, end, ann, [])

        return self / group_list

    def sub(self, replacement):
        # MIMIC re.sub
        if is_text(replacement):
            # USE PYTHON REGEX
            def pa(tokens):
                return tokens.type.regex.sub(replacement, tokens[0])

            output = self / pa
            return output
        else:
            # A FUNCTION
            def pf(tokens):
                regex_result = tokens.type.regex.match(tokens.tokens[0])
                return replacement(regex_result)

            return self / pf

    def parse_impl(self, string, start, do_actions=True):
        found = self.regex.match(string, start)
        if found:
            return ParseResults(self, start, found.end(), [found[0]], [])
        else:
            return failure(self, start, string)

    def _compile(self):
        # the child grammar is not parsed; only the pattern is
        regex = self.regex

        def parse(string, start):
            found = regex.match(string, start)
            if found:
                return ParseResults(self, start, found.end(), [found[0]], [])
            return FAIL

        return parse

    def streamline(self):
        # WE RUN THE DANGER OF MAKING PATHELOGICAL REGEX, SO WE DO NOT TRY
        if self.streamlined:
            return self

        expr = self.expr.streamline()
        if expr is self:
            self.streamlined = True
            return self
        output = self.copy()
        output.expr = expr
        output.streamlined = True
        return output

    def expecting(self):
        return OrderedDict((k, [self]) for k in self.expr.expecting().keys())

    def min_length(self):
        return self.expr.min_length()

    def fuse(self):
        if self.regex:
            return self.regex.pattern, None, None
        return None

    def __regex__(self):
        if self.regex:
            return "|", self.regex.pattern
        else:
            return self.expr.__regex__()


_plain_group = Group(None)

export("mo_parsing.core", "regex_parameters", parameters)
export("mo_parsing.tokens", Regex)
