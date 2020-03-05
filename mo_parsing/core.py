# encoding: utf-8
import copy
import warnings
from collections import namedtuple
from contextlib import contextmanager
from copy import copy
from threading import RLock

from mo_dots import Data
from mo_logs import Log
from mo_future import text, is_text

from mo_parsing.cache import packrat_cache
from mo_parsing.exceptions import (
    ParseBaseException,
    ParseException,
    ParseFatalException,
    conditionAsParseAction,
)
from mo_parsing.results import ParseResults
from mo_parsing.utils import (
    PY_3,
    _MAX_INT,
    _defaultExceptionDebugAction,
    _defaultStartDebugAction,
    _defaultSuccessDebugAction,
    _trim_arity,
    basestring,
    __diag__,
    noop,
)

# import later
(
    SkipTo,
    ZeroOrMore,
    OneOrMore,
    Optional,
    NotAny,
    Suppress,
    _flatten,
    replaceWith,
    quotedString,
    And,
    MatchFirst,
    Or,
    Each,
    Empty,
    StringEnd,
    Literal,
    Token,
    Group,
) = [None] * 18

DEBUG = False
DEFAULT_WHITE_CHARS = " \n\t\r"
CURRENT_WHITE_CHARS = list(DEFAULT_WHITE_CHARS)

DebugActions = namedtuple("DebugActions", ["TRY", "MATCH", "FAIL"])


locker = RLock()
def entrypoint(func):
    def output(*args, **kwargs):
        with locker:
            return func(*args, **kwargs)
    return output


@contextmanager
def default_whitespace(chars):
    r"""
    Overrides the default whitespace chars

    Example::

        # default whitespace chars are space, <TAB> and newline
        OneOrMore(Word(alphas)).parseString("abc def\nghi jkl")  # -> ['abc', 'def', 'ghi', 'jkl']

        # change to just treat newline as significant
        ParserElement.setDefaultWhitespaceChars(" \t")
        OneOrMore(Word(alphas)).parseString("abc def\nghi jkl")  # -> ['abc', 'def']
    """
    old_value = CURRENT_WHITE_CHARS
    CURRENT_WHITE_CHARS[:] = list(chars)
    yield
    CURRENT_WHITE_CHARS[:] = old_value


CURRENT_LITERAL = None


def default_literal(cls):
    """
    Set class to be used for inclusion of string literals into a parser.

    Example::

        # default literal class used is Literal
        integer = Word(nums)
        date_str = integer("year") + '/' + integer("month") + '/' + integer("day")

        date_str.parseString("1999/12/31")  # -> ['1999', '/', '12', '/', '31']


        # change to Suppress
        default_literal(Suppress)
        date_str = integer("year") + '/' + integer("month") + '/' + integer("day")

        date_str.parseString("1999/12/31")  # -> ['1999', '12', '31']
    """
    global CURRENT_LITERAL
    CURRENT_LITERAL = cls


class ParserElement(object):
    """Abstract base level parser element class."""

    @staticmethod
    def setDefaultWhitespaceChars(chars):
        r"""
        Overrides the default whitespace chars

        Example::

            # default whitespace chars are space, <TAB> and newline
            OneOrMore(Word(alphas)).parseString("abc def\nghi jkl")  # -> ['abc', 'def', 'ghi', 'jkl']

            # change to just treat newline as significant
            ParserElement.setDefaultWhitespaceChars(" \t")
            OneOrMore(Word(alphas)).parseString("abc def\nghi jkl")  # -> ['abc', 'def']
        """
        return default_whitespace(chars).__enter__()

    @property
    def copyDefaultWhiteChars(self):
        return self.parser_config.whiteChars is CURRENT_WHITE_CHARS

    @copyDefaultWhiteChars.setter
    def copyDefaultWhiteChars(self, do_copy):
        if do_copy:
            self.parser_config.whiteChars = CURRENT_WHITE_CHARS
        else:
            self.parser_config.whiteChars = copy(CURRENT_WHITE_CHARS)

    def __init__(self, savelist=False):
        self.parseAction = list()
        self.resultsName = None
        self.parser_config = Data()
        self.parser_config.failAction = None
        self.parser_config.skipWhitespace = True
        self.parser_config.copyDefaultWhiteChars = True
        self.parser_config.whiteChars = CURRENT_WHITE_CHARS
        self.parser_config.mayReturnEmpty = (
            False  # used when checking for left-recursion
        )
        self.parser_config.keepTabs = False
        self.parser_config.debug = False
        self.streamlined = False
        self.parser_config.mayIndexError = True  # used to optimize exception handling for subclasses that don't advance parse index
        self.parser_config.error_message = ""
        self.parser_config.modalResults = True  # used to mark results names as modal (report only last) or cumulative (list all)
        self.parser_config.debugActions = DebugActions(
            noop, noop, noop
        )  # custom debug actions
        self.parser_config.callPreparse = (
            True  # used to avoid redundant calls to preParse
        )
        self.callDuringTry = False
        self.ignoreExprs = []

    def normalize(self, expr):
        if expr is None:
            return None
        if isinstance(expr, basestring):
            if issubclass(CURRENT_LITERAL, Token):
                return CURRENT_LITERAL(expr)
            else:
                return CURRENT_LITERAL(Literal(expr))
        if not isinstance(expr, ParserElement):
            warnings.warn(
                "Cannot combine element of type %s with ParserElement" % type(expr),
                SyntaxWarning,
                stacklevel=2,
            )
            return None
        return expr

    def copy(self):
        """
        Make a copy of this :class:`ParserElement`.  Useful for defining
        different parse actions for the same parsing pattern, using copies of
        the original parse element.

        Example::

            integer = Word(nums).setParseAction(lambda toks: int(toks[0]))
            integerK = integer.copy().addParseAction(lambda toks: toks[0] * 1024) + Suppress("K")
            integerM = integer.copy().addParseAction(lambda toks: toks[0] * 1024 * 1024) + Suppress("M")

            print(OneOrMore(integerK | integerM | integer).parseString("5K 100 640K 256M"))

        prints::

            [5120, 100, 655360, 268435456]

        Equivalent form of ``expr.copy()`` is just ``expr()``::

            integerM = integer().addParseAction(lambda toks: toks[0] * 1024 * 1024) + Suppress("M")
        """
        cpy = copy(self)
        cpy.parser_config = self.parser_config.copy()
        cpy.parseAction = self.parseAction[:]
        cpy.ignoreExprs = self.ignoreExprs[:]
        if self.parser_config.copyDefaultWhiteChars:
            cpy.parser_config.whiteChars = CURRENT_WHITE_CHARS
        return cpy

    def setName(self, name):
        """
        Define name for this expression, makes debugging and exception messages clearer.

        Example::

            Word(nums).parseString("ABC")  # -> Exception: Expected W:(0123...) (at char 0), (line:1, col:1)
            Word(nums).setName("integer").parseString("ABC")  # -> Exception: Expected integer (at char 0), (line:1, col:1)
        """
        self.name = name
        self.parser_config.error_message = "Expected " + self.name
        if __diag__.enable_debug_on_named_expressions:
            self.setDebug()
        return self

    def setResultsName(self, name, listAllMatches=False):
        """
        Define name for referencing matching tokens as a nested attribute
        of the returned parse results.
        NOTE: this returns a *copy* of the original :class:`ParserElement` object;
        this is so that the client can define a basic element, such as an
        integer, and reference it in multiple places with different names.

        You can also set results names using the abbreviated syntax,
        ``expr("name")`` in place of ``expr.setResultsName("name")``
        - see :class:`__call__`.

        Example::

            date_str = (integer.setResultsName("year") + '/'
                        + integer.setResultsName("month") + '/'
                        + integer.setResultsName("day"))

            # equivalent form:
            date_str = integer("year") + '/' + integer("month") + '/' + integer("day")
        """
        return self._setResultsName(name, listAllMatches)

    def _setResultsName(self, name, listAllMatches=False):
        newself = self.copy()
        if not is_text(name):
            Log.error("not expected")
        if name.endswith("*"):
            name = name[:-1]
            listAllMatches = True
        newself.resultsName = name
        newself.parser_config.modalResults = not listAllMatches
        return newself

    def setBreak(self, breakFlag=True):
        """Method to invoke the Python pdb debugger when this element is
           about to be parsed. Set ``breakFlag`` to True to enable, False to
           disable.
        """
        if breakFlag:
            _parseMethod = self._parse

            def breaker(instring, loc, doActions=True, callPreParse=True):
                import pdb

                # this call to pdb.set_trace() is intentional, not a checkin error
                pdb.set_trace()
                return _parseMethod(instring, loc, doActions, callPreParse)

            breaker._originalParseMethod = _parseMethod
            self._parse = breaker
        else:
            if hasattr(self._parse, "_originalParseMethod"):
                self._parse = self._parse._originalParseMethod
        return self

    def setParseAction(self, *fns, **kwargs):
        """
        Define one or more actions to perform when successfully matching parse element definition.
        Parse action fn is a callable method with 0-3 arguments, called as ``fn(s, loc, toks)`` ,
        ``fn(loc, toks)`` , ``fn(toks)`` , or just ``fn()`` , where:

        - s   = the original string being parsed (see note below)
        - loc = the location of the matching substring
        - toks = a list of the matched tokens, packaged as a :class:`ParseResults` object

        If the functions in fns modify the tokens, they can return them as the return
        value from fn, and the modified list of tokens will replace the original.
        Otherwise, fn does not need to return any value.

        If None is passed as the parse action, all previously added parse actions for this
        expression are cleared.

        Optional keyword arguments:
        - callDuringTry = (default= ``False``) indicate if parse action should be run during lookaheads and alternate testing

        Note: the default parsing behavior is to expand tabs in the input string
        before starting the parsing process.  See :class:`parseString for more
        information on parsing strings containing ``<TAB>`` s, and suggested
        methods to maintain a consistent view of the parsed string, the parse
        location, and line and column positions within the parsed string.

        Example::

            integer = Word(nums)
            date_str = integer + '/' + integer + '/' + integer

            date_str.parseString("1999/12/31")  # -> ['1999', '/', '12', '/', '31']

            # use parse action to convert to ints at parse time
            integer = Word(nums).setParseAction(lambda toks: int(toks[0]))
            date_str = integer + '/' + integer + '/' + integer

            # note that integer fields are now ints, not strings
            date_str.parseString("1999/12/31")  # -> [1999, '/', 12, '/', 31]
        """
        if list(fns) == [
            None,
        ]:
            self.parseAction = []
        else:
            if not all(callable(fn) for fn in fns):
                raise TypeError("parse actions must be callable")
            self.parseAction = list(map(_trim_arity, list(fns)))
            self.callDuringTry = kwargs.get("callDuringTry", False)
        return self

    def addParseAction(self, *fns, **kwargs):
        """
        Add one or more parse actions to expression's list of parse actions. See :class:`setParseAction`.

        See examples in :class:`copy`.
        """
        self.parseAction += list(map(_trim_arity, fns))
        self.callDuringTry = self.callDuringTry or kwargs.get("callDuringTry", False)
        return self

    def addCondition(self, *fns, **kwargs):
        """Add a boolean predicate function to expression's list of parse actions. See
        :class:`setParseAction` for function call signatures. Unlike ``setParseAction``,
        functions passed to ``addCondition`` need to return boolean success/fail of the condition.

        Optional keyword arguments:
        - message = define a custom message to be used in the raised exception
        - fatal   = if True, will raise ParseFatalException to stop parsing immediately; otherwise will raise ParseException

        Example::

            integer = Word(nums).setParseAction(lambda toks: int(toks[0]))
            year_int = integer.copy()
            year_int.addCondition(lambda toks: toks[0] >= 2000, message="Only support years 2000 and later")
            date_str = year_int + '/' + integer + '/' + integer

            result = date_str.parseString("1999/12/31")  # -> Exception: Only support years 2000 and later (at char 0), (line:1, col:1)
        """
        for fn in fns:
            self.parseAction.append(
                conditionAsParseAction(
                    fn, message=kwargs.get("message"), fatal=kwargs.get("fatal", False)
                )
            )

        self.callDuringTry = self.callDuringTry or kwargs.get("callDuringTry", False)
        return self

    def setFailAction(self, fn):
        """Define action to perform if parsing fails at this expression.
           Fail acton fn is a callable function that takes the arguments
           ``fn(s, loc, expr, err)`` where:
           - s = string being parsed
           - loc = location where expression match was attempted and failed
           - expr = the parse expression that failed
           - err = the exception thrown
           The function returns no value.  It may throw :class:`ParseFatalException`
           if it is desired to stop parsing immediately."""
        self.parser_config.failAction = fn
        return self

    def _skipIgnorables(self, instring, loc):
        exprsFound = True
        while exprsFound:
            exprsFound = False
            for e in self.ignoreExprs:
                try:
                    while 1:
                        loc, dummy = e._parse(instring, loc)
                        exprsFound = True
                except ParseException:
                    pass
        return loc

    def preParse(self, instring, loc):
        more = True  # ENSURE ALTERNATING WHITESPACE AND IGNORABLES ARE SKIPPED
        while more:
            more = False
            if self.ignoreExprs:
                next_loc = self._skipIgnorables(instring, loc)
                if next_loc > loc:
                    more = True
                    loc = next_loc

            if self.parser_config.skipWhitespace:
                wt = self.parser_config.whiteChars
                instrlen = len(instring)
                while loc < instrlen and instring[loc] in wt:
                    more = True
                    loc += 1

        return loc

    def parseImpl(self, instring, loc, doActions=True):
        return loc, ParseResults(self, [])

    def postParse(self, instring, loc, tokenlist):
        return tokenlist

    def _parse(self, instring, loc, doActions=True, callPreParse=True):
        lookup = (self, instring, loc, callPreParse, doActions)
        value = packrat_cache.get(lookup)
        if value is not None:
            if isinstance(value, Exception):
                raise value
            return value[0], value[1]

        try:
            if self.parser_config.debug:
                self.parser_config.debugActions.TRY(instring, loc, self)
            start = preloc = loc
            try:
                if callPreParse and self.parser_config.callPreparse:
                    start = preloc = self.preParse(instring, loc)
                try:
                    loc, tokens = self.parseImpl(instring, preloc, doActions)
                except IndexError:
                    if self.parser_config.mayIndexError or preloc >= len(instring):
                        ex = ParseException(
                            instring,
                            len(instring),
                            self.parser_config.error_message,
                            self,
                        )
                        packrat_cache.set(lookup, ex.__class__(*ex.args))
                        raise ex
                    raise
            except Exception as err:
                if self.parser_config.debug:
                    self.parser_config.debugActions.FAIL(instring, start, self, err)
                self.parser_config.failAction(instring, start, self, err)
                raise

            tokens = self.postParse(instring, loc, tokens)

            if not isinstance(tokens, ParseResults):
                Log.error("expecting ParseResult")
            if self.__class__.__name__ == "Forward":
                if self.expr is not tokens.type_for_result:
                    Log.error("expecting correct type to com from self")
                else:
                    pass  # OK
            elif tokens.type_for_result is not self:
                Log.error("expecting correct type to come from self")

            retTokens = tokens
            if self.parseAction and (doActions or self.callDuringTry):
                try:
                    for fn in self.parseAction:
                        try:
                            tokens = fn(instring, start, retTokens)
                        except IndexError as parse_action_exc:
                            exc = ParseException("exception raised in parse action")
                            exc.__cause__ = parse_action_exc
                            raise exc

                        if isinstance(tokens, list):
                            tokens = ParseResults(self, tokens)
                        elif isinstance(tokens, tuple):
                            tokens = ParseResults(self, tokens)
                        elif tokens is None:
                            tokens = ParseResults(self, [])
                        elif isinstance(tokens, ParseResults):
                            pass
                        else:
                            tokens = ParseResults(self, [tokens])

                        retTokens = tokens
                except Exception as err:
                    if self.parser_config.debug:
                        self.parser_config.debugActions.FAIL(instring, start, self, err)
                    raise
            if self.parser_config.debug:
                self.parser_config.debugActions.MATCH(
                    instring, start, loc, self, retTokens
                )
        except ParseBaseException as pe:
            # cache a copy of the exception, without the traceback
            packrat_cache.set(lookup, pe.__class__(*pe.args))
            raise

        try:
            packrat_cache.set(lookup, (loc, retTokens))
        except Exception as e:
            raise e
        return loc, retTokens

    def tryParse(self, instring, loc):
        try:
            return self._parse(instring, loc, doActions=False)[0]
        except ParseFatalException:
            raise ParseException(instring, loc, self.parser_config.error_message, self)

    def canParseNext(self, instring, loc):
        try:
            self.tryParse(instring, loc)
        except (ParseException, IndexError):
            return False
        else:
            return True

    @entrypoint
    def parseString(self, instring, parseAll=False):
        """
        Parse a string with respect to the parser definition. This function is intended as the primary interface to the
        client code.

        :param instring: The input string to be parsed.
        :param parseAll: If set, the entire input string must match the grammar.
        :raises ParseException: Raised if ``parseAll`` is set and the input string does not match the whole grammar.
        :returns: the parsed data as a :class:`ParseResults` object, which may be accessed as a `list`, a `dict`, or
          an object with attributes if the given parser includes results names.

        If the input string is required to match the entire grammar, ``parseAll`` flag must be set to True. This
        is also equivalent to ending the grammar with ``StringEnd()``.

        To report proper column numbers, ``parseString`` operates on a copy of the input string where all tabs are
        converted to spaces (8 spaces per tab, as per the default in ``string.expandtabs``). If the input string
        contains tabs and the grammar uses parse actions that use the ``loc`` argument to index into the string
        being parsed, one can ensure a consistent view of the input string by doing one of the following:

        - calling ``parseWithTabs`` on your grammar before calling ``parseString`` (see :class:`parseWithTabs`),
        - define your parse action using the full ``(s,loc,toks)`` signature, and reference the input string using the
          parse action's ``s`` argument, or
        - explicitly expand the tabs in your input string before calling ``parseString``.

        Examples:

        By default, partial matches are OK.

        >>> res = Word('a').parseString('aaaaabaaa')
        >>> print(res)
        ['aaaaa']

        The parsing behavior varies by the inheriting class of this abstract class. Please refer to the children
        directly to see more examples.

        It raises an exception if parseAll flag is set and instring does not match the whole grammar.

        >>> res = Word('a').parseString('aaaaabaaa', parseAll=True)
        Traceback (most recent call last):
        ...
        mo_parsing.ParseException: Expected end of text, found 'b'  (at char 5), (line:1, col:6)
        """
        cache.resetCache()
        if not self.streamlined:
            self.streamline()
            for e in self.ignoreExprs:
                e.streamline()
        if not self.parser_config.keepTabs:
            instring = instring.expandtabs()
        try:
            loc, tokens = self._parse(instring, 0)
            if parseAll:
                loc = self.preParse(instring, loc)
                se = Empty() + StringEnd()
                se._parse(instring, loc)
        except ParseBaseException as exc:
            raise exc
        else:
            return tokens

    @entrypoint
    def scanString(self, instring, maxMatches=_MAX_INT, overlap=False):
        """
        Scan the input string for expression matches.  Each match will return the
        matching tokens, start location, and end location.  May be called with optional
        ``maxMatches`` argument, to clip scanning after 'n' matches are found.  If
        ``overlap`` is specified, then overlapping matches will be reported.

        Note that the start and end locations are reported relative to the string
        being parsed.  See :class:`parseString` for more information on parsing
        strings with embedded tabs.

        Example::

            source = "sldjf123lsdjjkf345sldkjf879lkjsfd987"
            print(source)
            for tokens, start, end in Word(alphas).scanString(source):
                print(' '*start + '^'*(end-start))
                print(' '*start + tokens[0])

        prints::

            sldjf123lsdjjkf345sldkjf879lkjsfd987
            ^^^^^
            sldjf
                    ^^^^^^^
                    lsdjjkf
                              ^^^^^^
                              sldkjf
                                       ^^^^^^
                                       lkjsfd
        """
        if not self.streamlined:
            self.streamline()
            for e in self.ignoreExprs:
                e.streamline()

        if not self.parser_config.keepTabs:
            instring = text(instring).expandtabs()
        instrlen = len(instring)
        loc = 0
        preparseFn = self.preParse
        parseFn = self._parse
        cache.resetCache()
        matches = 0
        while loc <= instrlen and matches < maxMatches:
            try:
                preloc = preparseFn(instring, loc)
                nextLoc, tokens = parseFn(instring, preloc, callPreParse=False)
            except ParseException as e:
                loc = preloc + 1
            else:
                if nextLoc > loc:
                    matches += 1
                    yield tokens, preloc, nextLoc
                    if overlap:
                        nextloc = preparseFn(instring, loc)
                        if nextloc > loc:
                            loc = nextLoc
                        else:
                            loc += 1
                    else:
                        loc = nextLoc
                else:
                    loc = preloc + 1

    def transformString(self, instring):
        """
        Extension to :class:`scanString`, to modify matching text with modified tokens that may
        be returned from a parse action.  To use ``transformString``, define a grammar and
        attach a parse action to it that modifies the returned token list.
        Invoking ``transformString()`` on a target string will then scan for matches,
        and replace the matched text patterns according to the logic in the parse
        action.  ``transformString()`` returns the resulting transformed string.

        Example::

            wd = Word(alphas)
            wd.setParseAction(lambda toks: toks[0].title())

            print(wd.transformString("now is the winter of our discontent made glorious summer by this sun of york."))

        prints::

            Now Is The Winter Of Our Discontent Made Glorious Summer By This Sun Of York.
        """
        out = []
        lastE = 0
        # force preservation of <TAB>s, to minimize unwanted transformation of string, and to
        # keep string locs straight between transformString and scanString
        self.parser_config.keepTabs = True
        for t, s, e in self.scanString(instring):
            out.append(instring[lastE:s])
            if t:
                if isinstance(t, ParseResults):
                    out.append("".join(t))
                elif isinstance(t, list):
                    out.append("".join(t))
                else:
                    out.append(t)
            lastE = e
        out.append(instring[lastE:])
        out = [o for o in out if o]
        return "".join(map(text, _flatten(out)))

    def searchString(self, instring, maxMatches=_MAX_INT):
        """
        Another extension to :class:`scanString`, simplifying the access to the tokens found
        to match the given parse expression.  May be called with optional
        ``maxMatches`` argument, to clip searching after 'n' matches are found.

        Example::

            # a capitalized word starts with an uppercase letter, followed by zero or more lowercase letters
            cap_word = Word(alphas.upper(), alphas.lower())

            print(cap_word.searchString("More than Iron, more than Lead, more than Gold I need Electricity"))

            # the sum() builtin can be used to merge results into a single ParseResults object
            print(sum(cap_word.searchString("More than Iron, more than Lead, more than Gold I need Electricity")))

        prints::

            [['More'], ['Iron'], ['Lead'], ['Gold'], ['I'], ['Electricity']]
            ['More', 'Iron', 'Lead', 'Gold', 'I', 'Electricity']
        """

        g = Group(None)
        output = ParseResults(
            self,
            [ParseResults(g, [t]) for t, s, e in self.scanString(instring, maxMatches)],
        )
        return output

    def split(self, instring, maxsplit=_MAX_INT, includeSeparators=False):
        """
        Generator method to split a string using the given expression as a separator.
        May be called with optional ``maxsplit`` argument, to limit the number of splits;
        and the optional ``includeSeparators`` argument (default= ``False``), if the separating
        matching text should be included in the split results.

        Example::

            punc = oneOf(list(".,;:/-!?"))
            print(list(punc.split("This, this?, this sentence, is badly punctuated!")))

        prints::

            ['This', ' this', '', ' this sentence', ' is badly punctuated', '']
        """
        splits = 0
        last = 0
        for t, s, e in self.scanString(instring, maxMatches=maxsplit):
            yield instring[last:s]
            if includeSeparators:
                yield t[0]
            last = e
        yield instring[last:]

    def __add__(self, other):
        """
        Implementation of + operator - returns :class:`And`. Adding strings to a ParserElement
        converts them to :class:`Literal`s by default.

        Example::

            greet = Word(alphas) + "," + Word(alphas) + "!"
            hello = "Hello, World!"
            print (hello, "->", greet.parseString(hello))

        prints::

            Hello, World! -> ['Hello', ',', 'World', '!']

        ``...`` may be used as a parse expression as a short form of :class:`SkipTo`.

            Literal('start') + ... + Literal('end')

        is equivalent to:

            Literal('start') + SkipTo('end')("_skipped*") + Literal('end')

        Note that the skipped text is returned with '_skipped' as a results name,
        and to support having multiple skips in the same parser, the value returned is
        a list of all skipped text.
        """
        if other is Ellipsis:
            return _PendingSkip(self)

        return And([self, self.normalize(other)])

    def __radd__(self, other):
        """
        Implementation of + operator when left operand is not a :class:`ParserElement`
        """
        if other is Ellipsis:
            return SkipTo(self)("_skipped*") + self

        return self.normalize(other) + self

    def __sub__(self, other):
        """
        Implementation of - operator, returns :class:`And` with error stop
        """
        return self + And._ErrorStop() + self.normalize(other)

    def __rsub__(self, other):
        """
        Implementation of - operator when left operand is not a :class:`ParserElement`
        """
        return self.normalize(other) - self

    def __mul__(self, other):
        """
        Implementation of * operator, allows use of ``expr * 3`` in place of
        ``expr + expr + expr``.  Expressions may also me multiplied by a 2-integer
        tuple, similar to ``{min, max}`` multipliers in regular expressions.  Tuples
        may also include ``None`` as in:
         - ``expr*(n, None)`` or ``expr*(n, )`` is equivalent
              to ``expr*n + ZeroOrMore(expr)``
              (read as "at least n instances of ``expr``")
         - ``expr*(None, n)`` is equivalent to ``expr*(0, n)``
              (read as "0 to n instances of ``expr``")
         - ``expr*(None, None)`` is equivalent to ``ZeroOrMore(expr)``
         - ``expr*(1, None)`` is equivalent to ``OneOrMore(expr)``

        Note that ``expr*(None, n)`` does not raise an exception if
        more than n exprs exist in the input stream; that is,
        ``expr*(None, n)`` does not enforce a maximum number of expr
        occurrences.  If this behavior is desired, then write
        ``expr*(None, n) + ~expr``
        """
        if other is Ellipsis:
            other = (0, None)
        elif isinstance(other, tuple) and other[:1] == (Ellipsis,):
            other = ((0,) + other[1:] + (None,))[:2]

        if isinstance(other, int):
            minElements, optElements = other, 0
        elif isinstance(other, tuple):
            other = tuple(o if o is not Ellipsis else None for o in other)
            other = (other + (None, None))[:2]
            if other[0] is None:
                other = (0, other[1])
            if isinstance(other[0], int) and other[1] is None:
                if other[0] == 0:
                    return ZeroOrMore(self)
                if other[0] == 1:
                    return OneOrMore(self)
                else:
                    return self * other[0] + ZeroOrMore(self)
            elif isinstance(other[0], int) and isinstance(other[1], int):
                minElements, optElements = other
                optElements -= minElements
            else:
                raise TypeError(
                    "cannot multiply 'ParserElement' and ('%s', '%s') objects",
                    type(other[0]),
                    type(other[1]),
                )
        else:
            raise TypeError(
                "cannot multiply 'ParserElement' and '%s' objects", type(other)
            )

        if minElements < 0:
            raise ValueError("cannot multiply ParserElement by negative value")
        if optElements < 0:
            raise ValueError(
                "second tuple value must be greater or equal to first tuple value"
            )
        if minElements == optElements == 0:
            raise ValueError("cannot multiply ParserElement by 0 or (0, 0)")

        if optElements:

            def makeOptionalList(n):
                if n > 1:
                    return Optional(self + makeOptionalList(n - 1))
                else:
                    return Optional(self)

            if minElements:
                if minElements == 1:
                    ret = self + makeOptionalList(optElements)
                else:
                    ret = And([self] * minElements) + makeOptionalList(optElements)
            else:
                ret = makeOptionalList(optElements)
        else:
            if minElements == 1:
                ret = self
            else:
                ret = And([self] * minElements)
        return ret

    def __rmul__(self, other):
        return self.__mul__(other)

    def __or__(self, other):
        """
        Implementation of | operator - returns :class:`MatchFirst`
        """
        if other is Ellipsis:
            return _PendingSkip(self, must_skip=True)

        return MatchFirst([self, self.normalize(other)])

    def __ror__(self, other):
        """
        Implementation of | operator when left operand is not a :class:`ParserElement`
        """
        return self.normalize(other) | self

    def __xor__(self, other):
        """
        Implementation of ^ operator - returns :class:`Or`
        """
        return Or([self, self.normalize(other)])

    def __rxor__(self, other):
        """
        Implementation of ^ operator when left operand is not a :class:`ParserElement`
        """
        return self.normalize(other) ^ self

    def __and__(self, other):
        """
        Implementation of & operator - returns :class:`Each`
        """
        return Each([self, self.normalize(other)])

    def __rand__(self, other):
        """
        Implementation of & operator when left operand is not a :class:`ParserElement`
        """
        return self.normalize(other) & self

    def __invert__(self):
        """
        Implementation of ~ operator - returns :class:`NotAny`
        """
        return NotAny(self)

    def __iter__(self):
        # must implement __iter__ to override legacy use of sequential access to __getitem__ to
        # iterate over a sequence
        raise TypeError("%r object is not iterable" % self.__class__.__name__)

    def __getitem__(self, key):
        """
        use ``[]`` indexing notation as a short form for expression repetition:
         - ``expr[n]`` is equivalent to ``expr*n``
         - ``expr[m, n]`` is equivalent to ``expr*(m, n)``
         - ``expr[n, ...]`` or ``expr[n,]`` is equivalent
              to ``expr*n + ZeroOrMore(expr)``
              (read as "at least n instances of ``expr``")
         - ``expr[..., n]`` is equivalent to ``expr*(0, n)``
              (read as "0 to n instances of ``expr``")
         - ``expr[...]`` and ``expr[0, ...]`` are equivalent to ``ZeroOrMore(expr)``
         - ``expr[1, ...]`` is equivalent to ``OneOrMore(expr)``
         ``None`` may be used in place of ``...``.

        Note that ``expr[..., n]`` and ``expr[m, n]``do not raise an exception
        if more than ``n`` ``expr``s exist in the input stream.  If this behavior is
        desired, then write ``expr[..., n] + ~expr``.
       """

        # convert single arg keys to tuples
        try:
            if isinstance(key, str):
                key = (key,)
            iter(key)
        except TypeError:
            key = (key, key)

        if len(key) > 2:
            warnings.warn(
                "only 1 or 2 index arguments supported ({0}{1})".format(
                    key[:5], "... [{0}]".format(len(key)) if len(key) > 5 else ""
                )
            )

        # clip to 2 elements
        ret = self * tuple(key[:2])
        return ret

    def __call__(self, name=None):
        """
        Shortcut for :class:`setResultsName`, with ``listAllMatches=False``.

        If ``name`` is given with a trailing ``'*'`` character, then ``listAllMatches`` will be
        passed as ``True``.

        If ``name` is omitted, same as calling :class:`copy`.

        Example::

            # these are equivalent
            userdata = Word(alphas).setResultsName("name") + Word(nums + "-").setResultsName("socsecno")
            userdata = Word(alphas)("name") + Word(nums + "-")("socsecno")
        """
        if name is not None:
            return self._setResultsName(name)
        else:
            return self.copy()

    def suppress(self):
        """
        Suppresses the output of this :class:`ParserElement`; useful to keep punctuation from
        cluttering up returned output.
        """
        return Suppress(self)

    def leaveWhitespace(self):
        """
        Disables the skipping of whitespace before matching the characters in the
        :class:`ParserElement`'s defined pattern.  This is normally only used internally by
        the mo_parsing module, but may be needed in some whitespace-sensitive grammars.
        """
        output = self.copy()
        output.parser_config.skipWhitespace = False
        return output

    def setWhitespaceChars(self, chars):
        """
        Overrides the default whitespace chars
        """
        self.parser_config.skipWhitespace = True
        self.parser_config.copyDefaultWhiteChars = False
        self.parser_config.whiteChars = chars
        return self

    def parseWithTabs(self):
        """
        Overrides default behavior to expand ``<TAB>``s to spaces before parsing the input string.
        Must be called before ``parseString`` when the input grammar contains elements that
        match ``<TAB>`` characters.
        """
        self.parser_config.keepTabs = True
        return self

    def ignore(self, other):
        """
        Define expression to be ignored (e.g., comments) while doing pattern
        matching; may be called repeatedly, to define multiple comment or other
        ignorable patterns.

        Example::

            patt = OneOrMore(Word(alphas))
            patt.parseString('ablaj /* comment */ lskjd') # -> ['ablaj']

            patt.ignore(cStyleComment)
            patt.parseString('ablaj /* comment */ lskjd') # -> ['ablaj', 'lskjd']
        """
        if isinstance(other, basestring):
            other = Suppress(other)

        if isinstance(other, Suppress):
            if other not in self.ignoreExprs:
                self.ignoreExprs.append(other)
        else:
            self.ignoreExprs.append(Suppress(other.copy()))
        return self

    def setDebugActions(self, startAction, successAction, exceptionAction):
        """
        Enable display of debugging messages while doing pattern matching.
        """
        self.parser_config.debugActions = DebugActions(
            startAction or _defaultStartDebugAction,
            successAction or _defaultSuccessDebugAction,
            exceptionAction or _defaultExceptionDebugAction,
        )
        self.parser_config.debug = True
        return self

    def setDebug(self, flag=True):
        if flag:
            self.setDebugActions(
                _defaultStartDebugAction,
                _defaultSuccessDebugAction,
                _defaultExceptionDebugAction,
            )
        else:
            self.parser_config.debug = False
        return self

    def __str__(self):
        return self.name

    def __repr__(self):
        return text(self)

    def streamline(self):
        self.streamlined = True
        return self

    def checkRecursion(self, parseElementList):
        pass

    def validate(self, validateTrace=None):
        """
        Check defined expressions for valid structure, check for infinite recursive definitions.
        """
        self.checkRecursion([])

    def parseFile(self, file_or_filename, parseAll=False):
        """
        Execute the parse expression on the given file or filename.
        If a filename is specified (instead of a file object),
        the entire file is opened, read, and closed before parsing.
        """
        try:
            file_contents = file_or_filename.read()
        except AttributeError:
            with open(file_or_filename, "r") as f:
                file_contents = f.read()
        return self.parseString(file_contents, parseAll)

    def __eq__(self, other):
        if isinstance(other, ParserElement):
            if PY_3:
                self is other or super(ParserElement, self).__eq__(other)
            else:
                return self is other or vars(self) == vars(other)
        elif isinstance(other, basestring):
            return self.matches(other)
        else:
            return super(ParserElement, self) == other

    def __ne__(self, other):
        return not (self == other)

    def __hash__(self):
        return id(self)

    def __req__(self, other):
        return self == other

    def __rne__(self, other):
        return not (self == other)

    def matches(self, testString, parseAll=True):
        """
        Method for quick testing of a parser against a test string. Good for simple
        inline microtests of sub expressions while building up larger parser.

        Parameters:
         - testString - to test against this expression for a match
         - parseAll - (default= ``True``) - flag to pass to :class:`parseString` when running tests

        Example::

            expr = Word(nums)
            assert expr.matches("100")
        """
        try:
            self.parseString(text(testString), parseAll=parseAll)
            return True
        except ParseBaseException:
            return False


class _PendingSkip(ParserElement):
    # internal placeholder class to hold a place were '...' is added to a parser element,
    # once another ParserElement is added, this placeholder will be replaced with a SkipTo
    def __init__(self, expr, must_skip=False):
        super(_PendingSkip, self).__init__()
        self.strRepr = str(expr + Empty()).replace("Empty", "...")
        self.name = self.strRepr
        self.anchor = expr
        self.must_skip = must_skip

    def __add__(self, other):
        skipper = SkipTo(other).setName("...")("_skipped*")
        if self.must_skip:

            def must_skip(t):
                if not t._skipped or t._skipped == [""]:
                    del t[0]
                    t.pop("_skipped", None)

            def show_skip(t):
                if t._skipped[-1:] == [""]:
                    skipped = t.pop("_skipped")
                    t["_skipped"] = "missing <" + repr(self.anchor) + ">"

            return (
                self.anchor + skipper().addParseAction(must_skip)
                | skipper().addParseAction(show_skip)
            ) + other

        return self.anchor + skipper + other

    def __repr__(self):
        return self.strRepr

    def parseImpl(self, *args):
        raise Exception(
            "use of `...` expression without following SkipTo target expression"
        )


# export

from mo_parsing import results, cache

results.ParserElement = ParserElement
