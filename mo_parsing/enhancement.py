# encoding: utf-8

from mo_dots import Null, is_null
from mo_future import text, is_text

from mo_parsing.core import ParserElement
from mo_parsing.engine import noop, Engine
from mo_parsing.exceptions import (
    ParseException,
    RecursiveGrammarException,
)
from mo_parsing.results import ParseResults, Annotation
from mo_parsing.utils import Log, listwrap, empty_tuple
from mo_parsing.utils import MAX_INT, is_forward

# import later
Token, Literal, Keyword, Word, CharsNotIn, _PositionToken, StringEnd, Empty = [None] * 8

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

    def consume_at_least_one_char(self):
        return self.expr.consume_at_least_one_char()

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

    Example::

        # use FollowedBy to match a label only if it is followed by a ':'
        data_word = Word(alphas)
        label = data_word + FollowedBy(':')
        attr_expr = Group(label + Suppress(':') + OneOrMore(data_word, stopOn=label).addParseAction(' '.join))

        OneOrMore(attr_expr).parseString("shape: SQUARE color: BLACK posn: upper left")

    prints::

        [['shape', 'SQUARE'], ['color', 'BLACK'], ['posn', 'upper left']]
    """

    def __init__(self, expr):
        super(FollowedBy, self).__init__(expr)

    def parseImpl(self, string, start, doActions=True):
        # by using self._expr.parse and deleting the contents of the returned ParseResults list
        # we keep any named results that were defined in the FollowedBy expression
        result = self.expr._parse(string, start, doActions=doActions)
        result.__class__ = Annotation

        return ParseResults(self, start, result.end, [result])


class NotAny(ParseElementEnhance):
    """Lookahead to disallow matching with the given parse expression.
    ``NotAny`` does *not* advance the parsing position within the
    input string, it only verifies that the specified parse expression
    does *not* match at the current position.  Also, ``NotAny`` does
    *not* skip over leading whitespace. ``NotAny`` always returns
    a null token list.  May be constructed using the '~' operator.

    Example::

        AND, OR, NOT = map(CaselessKeyword, "AND OR NOT".split())

        # take care not to mistake keywords for identifiers
        ident = ~(AND | OR | NOT) + Word(alphas)
        boolean_term = Optional(NOT) + ident

        # very crude boolean expression - to support parenthesis groups and
        # operation hierarchy, use infixNotation
        boolean_expr = boolean_term + ZeroOrMore((AND | OR) + boolean_term)

        # integers that are followed by "." are actually floats
        integer = Word(nums) + ~Char(".")
    """

    def __init__(self, expr):
        super(NotAny, self).__init__(expr)
        # do NOT use self.leaveWhitespace(), don't want to propagate to exprs

    def parseImpl(self, string, start, doActions=True):
        if self.expr.canParseNext(string, start):
            raise ParseException(self, start, string)
        return ParseResults(self, start, start, [])

    def __str__(self):
        if self.parser_name:
            return self.parser_name
        return "~{{self.expr}}"


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
        self.min_match = min_match
        self.max_match = max_match
        self.stopOn(stopOn)

    def copy(self):
        output = ParseElementEnhance.copy(self)
        output.min_match = self.min_match
        output.max_match = self.max_match
        output.not_ender = self.not_ender
        return output

    def stopOn(self, ender):
        self.not_ender = ~self.engine.normalize(ender) if ender else None
        return self

    def consume_at_least_one_char(self):
        if self.min_match == 0:
            return False
        return self.expr.consume_at_least_one_char()

    def parseImpl(self, string, start, doActions=True):
        if self.not_ender is None:
            try_not_ender = noop
        else:
            try_not_ender = self.not_ender.tryParse

        acc = []
        end = start
        try:
            while end < len(string):
                try_not_ender(string, end)
                tmptokens = self.expr._parse(string, end, doActions)
                end = tmptokens.end
                if tmptokens:
                    acc.append(tmptokens)
        except ParseException as e:
            if self.min_match <= len(acc) <= self.max_match:
                pass
            else:
                raise e
        num = len(acc)
        if num:
            if num < self.min_match or self.max_match < num:
                raise ParseException(
                    self,
                    acc[0].start,
                    msg=(
                        f"Expecting between {self.min_match} and {self.max_match} of"
                        f" {self}"
                    ),
                )
            else:
                return ParseResults(self, acc[0].start, acc[-1].end, acc)
        else:
            if not self.min_match:
                return ParseResults(self, start, start, [])
            else:
                raise ParseException(
                    self,
                    start,
                    string,
                    msg=f"Expecting at least {self.min_match} of {self}",
                )

    def streamline(self):
        if self.streamlined:
            return self
        if self.min_match == self.max_match and self.min_match == 1:
            return self.expr.streamline()

        self.streamlined = True
        return self

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
        self.parser_config.lock_engine = expr.parser_config.lock_engine
        self.parser_config.engine = expr.parser_config.engine

    def __str__(self):
        if self.parser_name:
            return self.parser_name
        return "{" + text(self.expr) + "}..."

    def copy(self):
        output = Many.copy(self)
        output.not_ender = self.not_ender
        return output


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
        self.defaultValue = listwrap(default)

    def copy(self):
        output = Many.copy(self)
        output.defaultValue = self.defaultValue
        return output

    def parseImpl(self, string, start, doActions=True):
        try:
            tokens = self.expr._parse(string, start, doActions)
            return ParseResults(self, tokens.start, tokens.end, [tokens])
        except ParseException:
            return ParseResults(self, start, start, self.defaultValue)

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
        self.includeMatch = include
        self.failOn = engine.CURRENT.normalize(failOn)
        self.ignoreExpr = ignore
        self.parser_name = str(self)

    def copy(self):
        output = ParseElementEnhance.copy(self)
        output.ignoreExpr = self.ignoreExpr
        output.includeMatch = self.includeMatch
        output.failOn = self.failOn
        return output

    def consume_at_least_one_char(self):
        return False

    def parseImpl(self, string, start, doActions=True):
        instrlen = len(string)
        self_failOn_canParseNext = (
            self.failOn.canParseNext if self.failOn is not None else None
        )
        self_ignoreExpr_tryParse = (
            self.ignoreExpr.tryParse if self.ignoreExpr is not None else None
        )

        loc = start
        while loc <= instrlen:
            if self_failOn_canParseNext is not None:
                # break if failOn expression matches
                if self_failOn_canParseNext(string, loc):
                    before_end = loc
                    break

            if self_ignoreExpr_tryParse is not None:
                # advance past ignore expressions
                while 1:
                    try:
                        loc = self_ignoreExpr_tryParse(string, loc)
                    except ParseException:
                        break
            try:
                before_end = loc
                loc = self.expr._parse(string, loc, doActions=False).end
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

        if self.includeMatch:
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

        self.strRepr = None  # avoid recursion
        if expr:
            self << engine.CURRENT.normalize(expr)

    def copy(self):
        output = ParserElement.copy(self)
        output.expr = self
        output.strRepr = None
        output.used_by = []
        return output

    @property
    def name(self):
        return self.type.expr.token_name

    def track(self, expr):
        self.used_by.append(expr)

    def __lshift__(self, other):
        self.strRepr = ""
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

    def consume_at_least_one_char(self):
        if self.expr:
            return self.expr.consume_at_least_one_char()
        return False

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

        if self.strRepr:
            return self.strRepr

        # Avoid infinite recursion by setting a temporary strRepr
        self.strRepr = "Forward: ..."
        try:
            self.strRepr = "Forward: " + text(self.expr)[:1000]
        except Exception:
            pass
        return self.strRepr

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
        self.separator = separator
        self.parseAction.append(_combine_post_parse)

    def copy(self):
        output = TokenConverter.copy(self)
        output.separator = self.separator
        return output


def _combine_post_parse(tokens, start, string):
    type_ = tokens.type
    retToks = ParseResults(
        tokens.type, start, tokens.end, [tokens.asString(sep=type_.separator)]
    )
    return retToks


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
        self.expr = self.expr.leaveWhitespace()

        self.exact = False
        if isinstance(expr, str):
            retreat = len(expr)
            self.exact = True
        elif isinstance(expr, (Literal, Keyword)):
            retreat = expr.matchLen
            self.exact = True
        elif (
            isinstance(expr, (Word, CharsNotIn))
            and expr.parser_config.max_len != MAX_INT
        ):
            retreat = expr.parser_config.max_len
            self.exact = True
        elif isinstance(expr, _PositionToken):
            retreat = 0
            self.exact = True
        self.retreat = retreat

    def copy(self):
        output = ParseElementEnhance.copy(self)
        output.expr = self.expr
        output.exact = self.exact
        output.retreat = self.retreat
        return output

    def parseImpl(self, string, start=0, doActions=True):
        if self.exact:
            if start < self.retreat:
                raise ParseException(self, start, string)
            start = start - self.retreat
            ret = self.expr._parse(string, start)
        else:
            # retreat specified a maximum lookbehind window, iterate
            test_expr = self.expr + StringEnd()
            instring_slice = string[:start]
            last_expr = ParseException(self, start, string)
            for offset in range(1, min(start, self.retreat + 1)):
                try:
                    ret = test_expr._parse(instring_slice, start - offset)
                except ParseException as pbe:
                    last_expr = pbe
                else:
                    break
            else:
                raise last_expr
        # return empty list of tokens, but preserve any defined results names

        ret.__class__ = Annotation
        return ParseResults(self, start, ret.end, [ret])


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
