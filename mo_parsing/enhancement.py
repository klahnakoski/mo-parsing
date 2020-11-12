# encoding: utf-8
import re

from mo_dots import Null, is_null
from mo_future import text, is_text

from mo_parsing.core import ParserElement
from mo_parsing.engine import noop, Engine
from mo_parsing.exceptions import (
    ParseException,
    RecursiveGrammarException,
)
from mo_parsing.results import ParseResults, Annotation
from mo_parsing.utils import Log, listwrap, empty_tuple, regex_iso
from mo_parsing.utils import MAX_INT, is_forward

# import later
(
    Token,
    NoMatch,
    Literal,
    Keyword,
    Word,
    CharsNotIn,
    _PositionToken,
    StringEnd,
    Empty,
    Char,
) = [None] * 10

_get = object.__getattribute__


class ParseElementEnhance(ParserElement):
    """Abstract subclass of `ParserElement`, for combining and
    post-processing parsed tokens.
    """

    def __init__(self, expr):
        ParserElement.__init__(self)
        self.expr = expr = engine.CURRENT.normalize(expr)
        if is_forward(expr):
            expr.track(self)

    def copy(self):
        output = ParserElement.copy(self)
        if self.engine is engine.CURRENT:
            output.expr = self.expr
        else:
            output.expr = self.expr.copy()
        return output

    def min_length(self):
        return self.expr.min_length()

    def parseImpl(self, string, start, doActions=True):
        output = self.expr._parse(string, start, doActions)
        return ParseResults(self, output.start, output.end, [output])

    def leaveWhitespace(self):
        with Engine(""):
            output = self.copy()
            output.expr = self.expr.leaveWhitespace()
            return output

    def streamline(self):
        if self.streamlined:
            return self
        self.streamlined = True
        self.expr.streamline()

        if not self.expr or isinstance(self.expr, Empty):
            self.__class__ = Empty

        return self

    def checkRecursion(self, seen=empty_tuple):
        if self in seen:
            raise RecursiveGrammarException(seen + (self,))
        if self.expr != None:
            self.expr.checkRecursion(seen + (self,))

    def __str__(self):
        if self.parser_name:
            return self.parser_name
        return f"{self.__class__.__name__}:({self.expr})"


class FollowedBy(ParseElementEnhance):
    """Lookahead matching of the given parse expression.
    ``FollowedBy`` does *not* advance the parsing position within
    the input string, it only verifies that the specified parse
    expression matches at the current position.  ``FollowedBy``
    always returns a null token list. If any results names are defined
    in the lookahead expression, those *will* be returned for access by
    name.
    """

    def __init__(self, expr):
        super(FollowedBy, self).__init__(expr)

    def parseImpl(self, string, start, doActions=True):
        # by using self._expr.parse and deleting the contents of the returned ParseResults list
        # we keep any named results that were defined in the FollowedBy expression
        result = self.expr._parse(string, start, doActions=doActions)
        result.__class__ = Annotation

        return ParseResults(self, start, start, [result])

    def __regex__(self):
        return "*", f"(?={self.expr.__regex__()[1]})"


class NotAny(ParseElementEnhance):
    """Lookahead to disallow matching with the given parse expression.
    ``NotAny`` does *not* advance the parsing position within the
    input string, it only verifies that the specified parse expression
    does *not* match at the current position.  Also, ``NotAny`` does
    *not* skip over leading whitespace. ``NotAny`` always returns
    a null token list.  May be constructed using the '~' operator.
    """

    def __init__(self, expr):
        super(NotAny, self).__init__(expr)
        # do NOT use self.leaveWhitespace(), don't want to propagate to exprs

    def parseImpl(self, string, start, doActions=True):
        if self.expr.canParseNext(string, start):
            raise ParseException(self, start, string)
        return ParseResults(self, start, start, [])

    def streamline(self):
        output = ParseElementEnhance.streamline(self)
        if isinstance(output.expr, NoMatch):
            return Empty()
        if isinstance(output.expr, Empty):
            return NoMatch()
        return output

    def min_length(self):
        return 0

    def __regex__(self):
        prec, regex = self.expr.__regex__()
        return "*", f"(?!({regex}))"

    def __str__(self):
        if self.parser_name:
            return self.parser_name
        return "~{" + str(self.expr) + "}"


class Many(ParseElementEnhance):
    def __init__(self, expr, stopOn=None, min_match=-1, max_match=-1):
        """
        MATCH expr SOME NUMBER OF TIMES (OR UNTIL stopOn IS REACHED
        :param expr: THE EXPRESSION TO MATCH
        :param stopOn: THE PATTERN TO INDICATE STOP MATCHING
        :param min_match: MINIMUM MATCHES REQUIRED FOR SUCCESS (-1 IS INVALID)
        :param max_match: MAXIMUM MATCH REQUIRED FOR SUCCESS (-1 IS INVALID)
        """
        super(Many, self).__init__(expr)
        self.parser_config.min_match = min_match
        self.parser_config.max_match = max_match
        self.stopOn(stopOn)

    def stopOn(self, ender):
        if ender:
            end = self.engine.normalize(ender)
            self.parser_config.end = re.compile(end.__regex__()[1])
        else:
            self.parser_config.end = None
        return self

    def min_length(self):
        if self.parser_config.min_match == 0:
            return 0
        return self.expr.min_length()

    def parseImpl(self, string, start, doActions=True):
        acc = []
        end = start
        try:
            while end < len(string):
                if self.parser_config.end:
                    end = self.engine.skip(string, end)
                    if self.parser_config.end.match(string, end):
                        if self.parser_config.min_match <= len(acc) <= self.parser_config.max_match:
                            break
                        else:
                            raise ParseException(
                                self, end, string, msg="Not expecting end"
                            )
                tokens = self.expr._parse(string, end, doActions)
                end = tokens.end
                if tokens:
                    acc.append(tokens)
        except ParseException as e:
            if self.parser_config.min_match <= len(acc) <= self.parser_config.max_match:
                pass
            else:
                ParseException(self, start, string, msg="Not correct amount of matches")
        num = len(acc)
        if num:
            if num < self.parser_config.min_match or self.parser_config.max_match < num:
                raise ParseException(
                    self,
                    acc[0].start,
                    string,
                    msg=(
                        f"Expecting between {self.parser_config.min_match} and"
                        f" {self.parser_config.max_match} of {self.expr}"
                    ),
                )
            else:
                return ParseResults(self, acc[0].start, acc[-1].end, acc)
        else:
            if not self.parser_config.min_match:
                return ParseResults(self, start, start, [])
            else:
                raise ParseException(
                    self,
                    start,
                    string,
                    msg=f"Expecting at least {self.parser_config.min_match} of {self}",
                )

    def streamline(self):
        if self.streamlined:
            return self
        expr = self.expr.streamline()
        if (
            self.parser_config.min_match == self.parser_config.max_match
            and self.parser_config.min_match == 1
        ):
            return expr

        if self.expr is expr:
            self.streamlined = True
            return self
        if expr.is_annotated() or not isinstance(expr, Empty):
            output = self.copy()
            output.expr = expr
            output.streamlined = True
            return output
        return Empty()

    def __regex__(self):
        end = self.parser_config.end.pattern if self.parser_config.end else None
        prec, regex = self.expr.__regex__()
        regex = regex_iso(prec, regex, "*")

        if self.parser_config.max_match == MAX_INT:
            if self.parser_config.min_match == 0:
                suffix = "*"
            elif self.parser_config.min_match == 1:
                suffix = "+"
            else:
                suffix = "{" + text(self.parser_config.min_match) + ",}"
        elif self.parser_config.min_match == 1 and self.parser_config.max_match == 1:
            suffix = ""
        else:
            suffix = (
                "{"
                + text(self.parser_config.min_match)
                + ","
                + text(self.parser_config.max_match)
                + "}"
            )

        if end:
            return "+", regex + suffix + end
        else:
            return "*", regex + suffix

    def __call__(self, name):
        if not name:
            return self

        for e in [self.expr]:
            if isinstance(e, ParserElement) and e.token_name == name:
                Log.error(
                    "can not set token name, already set in one of the other"
                    " expressions"
                )

        return ParseElementEnhance.__call__(self, name)


class OneOrMore(Many):
    """Repetition of one or more of the given expression.

    Parameters:
     - expr - expression that must match one or more times
     - stopOn - (default= ``None``) - expression for a terminating sentinel
          (only required if the sentinel would ordinarily match the repetition
          expression)

    """

    def __init__(self, expr, stopOn=None):
        Many.__init__(self, expr, stopOn, min_match=1, max_match=MAX_INT)
        self.parser_config.lock_engine = self.expr.parser_config.lock_engine
        self.parser_config.engine = self.expr.parser_config.engine

    def __str__(self):
        if self.parser_name:
            return self.parser_name
        return "{" + text(self.expr) + "}..."


class ZeroOrMore(Many):
    """Optional repetition of zero or more of the given expression.

    Parameters:
     - expr - expression that must match zero or more times
     - stopOn - (default= ``None``) - expression for a terminating sentinel
          (only required if the sentinel would ordinarily match the repetition
          expression)

    Example: similar to `OneOrMore`
    """

    def __init__(self, expr, stopOn=None):
        super(ZeroOrMore, self).__init__(
            expr, stopOn=stopOn, min_match=0, max_match=MAX_INT
        )

        self.parser_config.lock_engine = self.expr.parser_config.lock_engine
        self.parser_config.engine = self.expr.parser_config.engine

    def parseImpl(self, string, start, doActions=True):
        try:
            return super(ZeroOrMore, self).parseImpl(string, start, doActions)
        except ParseException:
            return ParseResults(self, start, start, [])

    def __str__(self):
        if self.parser_name:
            return self.parser_name

        return "[" + text(self.expr) + "]..."


class Optional(Many):
    """Optional matching of the given expression.

    Parameters:
     - expr - expression that must match zero or more times
     - default (optional) - value to be returned if the optional expression is not found.
    """

    def __init__(self, expr, default=None):
        Many.__init__(self, expr, stopOn=None, min_match=0, max_match=1)
        self.parser_config.defaultValue = listwrap(default)

    def copy(self):
        output = Many.copy(self)
        output.defaultValue = self.parser_config.defaultValue
        return output

    def parseImpl(self, string, start, doActions=True):
        try:
            tokens = self.expr._parse(string, start, doActions)
            return ParseResults(self, tokens.start, tokens.end, [tokens])
        except ParseException:
            return ParseResults(self, start, start, self.parser_config.defaultValue)

    def __str__(self):
        if self.parser_name:
            return self.parser_name

        return "[" + text(self.expr) + "]"


class SkipTo(ParseElementEnhance):
    """Token for skipping over all undefined text until the matched expression is found."""

    def __init__(self, expr, include=False, ignore=None, failOn=None):
        """
        :param expr: target expression marking the end of the data to be skipped
        :param include: if True, the target expression is also parsed
          (the skipped text and target expression are returned as a 2-element list).
        :param ignore: used to define grammars (typically quoted strings and
          comments) that might contain false matches to the target expression
        :param failOn: define expressions that are not allowed to be
          included in the skipped test; if found before the target expression is found,
          the SkipTo is not a match
        """
        ParseElementEnhance.__init__(self, expr)
        self.parser_config.include = include
        self.parser_config.fail = engine.CURRENT.normalize(failOn)
        self.parser_config.ignore = ignore
        self.parser_name = str(self)

    def min_length(self):
        return 0

    def parseImpl(self, string, start, doActions=True):
        instrlen = len(string)
        fail = self.parser_config.fail
        ignore = self.parser_config.ignore

        loc = start
        while loc <= instrlen:
            if fail:
                # break if failOn expression matches
                if fail.canParseNext(string, loc):
                    before_end = loc
                    break

            if ignore:
                # advance past ignore expressions
                while 1:
                    try:
                        loc = ignore.tryParse(string, loc)
                        if loc == None:
                            Log.error("")
                    except ParseException:
                        break
            try:
                before_end = loc
                loc = self.expr._parse(string, loc, doActions=False).end
                if loc == None:
                    Log.error("")
            except ParseException:
                # no match, advance loc in string
                loc += 1
            else:
                # matched skipto expr, done
                break

        else:
            # ran off the end of the input string without matching skipto expr, fail
            raise ParseException(self, start, string)

        # build up return values
        end = loc
        skiptext = string[start:before_end]
        skip_result = []
        if skiptext:
            skip_result.append(skiptext)

        if self.parser_config.include:
            end_result = self.expr._parse(string, before_end, doActions)
            skip_result.append(end_result)
            return ParseResults(self, start, end, skip_result)
        else:
            return ParseResults(self, start, before_end, skip_result)


class Forward(ParserElement):
    """Forward declaration of an expression to be defined later -
    used for recursive grammars, such as algebraic infix notation.
    When the expression is known, it is assigned to the ``Forward``
    variable using the '<<' operator.

    Note: take care when assigning to ``Forward`` not to overlook
    precedence of operators.

    Specifically, '|' has a lower precedence than '<<', so that::

        fwdExpr << a | b | c

    will actually be evaluated as::

        (fwdExpr << a) | b | c

    thereby leaving b and c out as parseable alternatives.  It is recommended that you
    explicitly group the values inserted into the ``Forward``::

        fwdExpr << (a | b | c)

    Converting to use the '<<=' operator instead will avoid this problem.

    See `ParseResults.pprint` for an example of a recursive
    parser created using ``Forward``.
    """

    def __init__(self, expr=Null):
        ParserElement.__init__(self)
        self.expr = None
        self.used_by = []

        self._str = None  # avoid recursion
        self._min_length = None  # avoid recursion
        if expr:
            self << engine.CURRENT.normalize(expr)

    def copy(self):
        output = ParserElement.copy(self)
        output.expr = self
        output._str = None
        output._min_length = None

        output.used_by = []
        return output

    @property
    def name(self):
        return self.type.expr.token_name

    def track(self, expr):
        self.used_by.append(expr)

    def __lshift__(self, other):
        self._str = ""
        if is_null(other):
            Log.error("can not set to None")
        if is_forward(self.expr):
            return self.expr << other

        while is_forward(other):
            other = other.expr
        self.expr = engine.CURRENT.normalize(other)
        return self

    def addParseAction(self, action):
        if not self.expr:
            Log.error("not allowed")
        self.expr = self.expr.addParseAction(action)

    def leaveWhitespace(self):
        with Engine(""):
            output = self.copy()
            output.expr = self.expr.leaveWhitespace()
            return output

    def streamline(self):
        if self.streamlined:
            return self

        if self.expr:
            self.checkRecursion()
            self.expr = self.expr.streamline()
            self.streamlined = True
        return self

    def checkRecursion(self, seen=empty_tuple):
        if self in seen:
            raise RecursiveGrammarException(seen + (self,))
        if self.expr != None:
            self.expr.checkRecursion(seen + (self,))

    def min_length(self):
        if self._min_length is None and self.expr:
            self._min_length = 0  # BREAK CYCLE
            try:
                return self.expr.min_length()
            finally:
                self._min_length = None
        return 0

    def parseImpl(self, string, loc, doActions=True):
        try:
            result = self.expr._parse(string, loc, doActions)
            return ParseResults(self, result.start, result.end, [result])
        except Exception as cause:
            if is_null(self.expr):
                Log.warning(
                    "Ensure you have assigned a ParserElement (<<) to this Forward",
                    cause=cause,
                )
            raise cause

    def __str__(self):
        if self.parser_name:
            return self.parser_name

        if self._str:
            return self._str

        # Avoid infinite recursion by setting a temporary strRepr
        self._str = "Forward: ..."
        try:
            self._str = "Forward: " + text(self.expr)[:1000]
        except Exception:
            pass
        return self._str

    def __call__(self, name):
        output = self.copy()
        output.token_name = name
        return output


class TokenConverter(ParseElementEnhance):
    """
    Abstract subclass of `ParseExpression`, for converting parsed results.
    """

    pass


class Combine(TokenConverter):
    """
    Converter to concatenate all matching tokens to a single string.
    """

    def __init__(self, expr, separator=""):
        super(Combine, self).__init__(expr)
        self.parser_config.separator = separator
        self.parseAction.append(_combine)

def _combine(tokens, start, string):
    output = ParseResults(
        tokens.type, tokens.start, tokens.end, [tokens.asString(sep=tokens.type.parser_config.separator)]
    )
    return output


class Group(TokenConverter):
    """
    MARK A CLOSED PARSE RESULT
    """

    def __init__(self, expr):
        ParserElement.__init__(self)
        self.expr = self.engine.normalize(expr)


class Dict(Group):
    """
    Convert a list of tuples [(name, v1, v2, ...), ...]
    int dict-like lookup     {name: [v1, v2, ...], ...}

    mo-parsing uses the names of the ParserElement to name ParseResults,
    but this is a static naming scheme. Dict allows dynamic naming;
    Effectively defining new named ParserElements (called Annotations)
    at parse time
    """

    def __init__(self, expr):
        Group.__init__(self, expr)
        self.parseAction.append(_dict_post_parse)


class OpenDict(TokenConverter):
    """
    Same as Dict, but not grouped: Open to previous (or subsequent) name: value pairs
    """

    def __init__(self, expr):
        TokenConverter.__init__(self, expr)
        self.parseAction.append(_dict_post_parse)


def _dict_post_parse(tokens, loc, string):
    acc = tokens.tokens
    for a in list(acc):
        for tok in list(a):
            if not tok:
                continue
            if is_text(tok):
                new_tok = Annotation(tok, a.start, a.end, [])
            else:
                kv = list(tok)
                key = kv[0]
                value = kv[1:]
                new_tok = Annotation(text(key), tok.start, tok.end, value)
            acc.append(new_tok)

    return tokens


class Suppress(TokenConverter):
    """
    Converter for ignoring the results of a parsed expression.
    """

    def __init__(self, expr):
        TokenConverter.__init__(self, expr)
        self.parseAction.append(_suppress_post_parse)

    def suppress(self):
        return self

    def __str__(self):
        if self.parser_name:
            return self.parser_name
        return text(self.expr)


def _suppress_post_parse(tokens, start, string):
    return ParseResults(tokens.type, tokens.start, tokens.end, [])


class PrecededBy(ParseElementEnhance):
    """Lookbehind matching of the given parse expression.
    ``PrecededBy`` does not advance the parsing position within the
    input string, it only verifies that the specified parse expression
    matches prior to the current position.  ``PrecededBy`` always
    returns a null token list, but if a results name is defined on the
    given expression, it is returned.

    Parameters:

     - expr - expression that must match prior to the current parse
       location
     - retreat - (default= ``None``) - (int) maximum number of characters
       to lookbehind prior to the current parse location

    If the lookbehind expression is a string, Literal, Keyword, or
    a Word or CharsNotIn with a specified exact or maximum length, then
    the retreat parameter is not required. Otherwise, retreat must be
    specified to give a maximum number of characters to look back from
    the current parse position for a lookbehind match.

    Example::

        # VB-style variable names with type prefixes
        int_var = PrecededBy("#") + identifier
        str_var = PrecededBy("$") + identifier

    """

    def __init__(self, expr, retreat=None):
        super(PrecededBy, self).__init__(expr)
        expr = self.expr = self.expr.leaveWhitespace()

        if isinstance(expr, (Literal, Keyword, Char)):
            self.parser_config.retreat = expr.min_length()
            self.parser_config.exact = True
        elif isinstance(expr, (Word, CharsNotIn)):
            self.parser_config.retreat = expr.min_length()
            self.parser_config.exact = False
        elif isinstance(expr, _PositionToken):
            self.parser_config.retreat = 0
            self.parser_config.exact = True
        else:
            self.parser_config.retreat = expr.min_length()
            self.parser_config.exact = False

    def parseImpl(self, string, start=0, doActions=True):
        if self.parser_config.exact:
            loc = start - self.parser_config.retreat
            if loc < 0:
                raise ParseException(self, start, string)
            ret = self.expr._parse(string, loc)
        else:
            # retreat specified a maximum lookbehind window, iterate
            test_expr = self.expr + StringEnd()
            instring_slice = string[:start]
            last_cause = ParseException(self, start, string)

            with self.engine.backup():
                for offset in range(self.parser_config.retreat, start + 1):
                    try:
                        ret = test_expr._parse(instring_slice, start - offset)
                        break
                    except ParseException as cause:
                        last_cause = cause
                else:
                    raise last_cause
        # return empty list of tokens, but preserve any defined results names

        ret.__class__ = Annotation
        return ParseResults(self, start, start, [ret])


# export
from mo_parsing import core, engine, results

core.SkipTo = SkipTo
core.Many = Many
core.ZeroOrMore = ZeroOrMore
core.OneOrMore = OneOrMore
core.Optional = Optional
core.NotAny = NotAny
core.Suppress = Suppress
core.Group = Group

results.Group = Group
results.Dict = Dict
results.Suppress = Suppress
