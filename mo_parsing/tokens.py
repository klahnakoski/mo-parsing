# encoding: utf-8
import re
import sre_constants
import warnings

from mo_future import text
from mo_logs import Log

from mo_parsing.engine import Engine
from mo_parsing.exceptions import ParseException
from mo_parsing.core import ParserElement
from mo_parsing.results import ParseResults
from mo_parsing.utils import (
    _MAX_INT,
    alphanums,
    basestring,
    col,
    printables,
    _bslash,
)


def _escapeRegexRangeChars(s):
    # ~  escape these chars: ^-]
    for c in r"\^-]":
        s = s.replace(c, _bslash + c)
    s = s.replace("\n", r"\n")
    s = s.replace("\t", r"\t")
    return text(s)


class Token(ParserElement):
    pass


class Empty(Token):
    """An empty token, will always match.
    """

    def __init__(self):
        super(Empty, self).__init__()
        self.parser_name = "Empty"
        self.parser_config.mayReturnEmpty = True
        self.parser_config.mayIndexError = False


class NoMatch(Token):
    """A token that will never match.
    """

    def __init__(self):
        super(NoMatch, self).__init__()
        self.parser_name = "NoMatch"
        self.parser_config.mayReturnEmpty = True
        self.parser_config.mayIndexError = False

    def parseImpl(self, instring, loc, doActions=True):
        raise ParseException(instring, loc, self)


class Literal(Token):
    """Token to exactly match a specified string.

    Example::

        Literal('blah').parseString('blah')  # -> ['blah']
        Literal('blah').parseString('blahfooblah')  # -> ['blah']
        Literal('blah').parseString('bla')  # -> Exception: Expected "blah"

    For case-insensitive matching, use :class:`CaselessLiteral`.

    For keyword matching (force word break before and after the matched string),
    use :class:`Keyword` or :class:`CaselessKeyword`.
    """

    def __init__(self, matchString):
        super(Literal, self).__init__()
        self.match = matchString
        self.matchLen = len(matchString)
        try:
            self.firstMatchChar = matchString[0]
        except IndexError:
            warnings.warn(
                "null string passed to Literal; use Empty() instead",
                SyntaxWarning,
                stacklevel=2,
            )
            self.__class__ = Empty
        self.parser_name = '"%s"' % text(self.match)
        self.parser_config.mayReturnEmpty = False
        self.parser_config.mayIndexError = False

        # Performance tuning: modify __class__ to select
        # a parseImpl optimized for single-character check
        if self.matchLen == 1 and type(self) is Literal:
            self.__class__ = _SingleCharLiteral

    def copy(self):
        output = ParserElement.copy(self)
        output.firstMatchChar = self.firstMatchChar
        output.match = self.match
        output.matchLen = self.matchLen
        return output

    def parseImpl(self, instring, loc, doActions=True):
        if instring[loc] == self.firstMatchChar and instring.startswith(
            self.match, loc
        ):
            return loc + self.matchLen, ParseResults(self, [self.match])
        raise ParseException(instring, loc, self)


class _SingleCharLiteral(Literal):
    def parseImpl(self, instring, loc, doActions=True):
        if instring[loc] == self.firstMatchChar:
            return loc + 1, ParseResults(self, [self.match])
        raise ParseException(instring, loc, self)


class Keyword(Token):
    """Token to exactly match a specified string as a keyword, that is,
    it must be immediately followed by a non-keyword character.  Compare
    with :class:`Literal`:

     - ``Literal("if")`` will match the leading ``'if'`` in
       ``'ifAndOnlyIf'``.
     - ``Keyword("if")`` will not; it will only match the leading
       ``'if'`` in ``'if x=1'``, or ``'if(y==2)'``

    Accepts two optional constructor arguments in addition to the
    keyword string:

     - ``identChars`` is a string of characters that would be valid
       identifier characters, defaulting to all alphanumerics + "_" and
       "$"
     - ``caseless`` allows case-insensitive matching, default is ``False``.

    Example::

        Keyword("start").parseString("start")  # -> ['start']
        Keyword("start").parseString("starting")  # -> Exception

    For case-insensitive matching, use :class:`CaselessKeyword`.
    """
    def __new__(cls, matchString, identChars=None, caseless=None):
        if len(matchString)==0:
            Log.error("Expecting more than one character in keyword")
        if caseless:
            return object.__new__(CaselessKeyword)
        else:
            return object.__new__(cls)

    def __init__(self, matchString, identChars=None, caseless=None):
        Token.__init__(self)
        if identChars is None:
            self.identChars = self.engine.keyword_chars
        else:
            self.identChars = "".join(sorted(set(identChars)))
        self.match = matchString
        self.matchLen = len(matchString)
        self.parser_name = '"%s"' % self.match
        self.parser_config.mayReturnEmpty = False
        self.parser_config.mayIndexError = False

    def copy(self):
        output = ParserElement.copy(self)
        output.match = self.match
        output.matchLen = self.matchLen
        output.identChars = self.identChars
        return output

    def parseImpl(self, instring, loc, doActions=True):
        if instring.startswith(self.match, loc):
            end = loc + self.matchLen
            try:
                if instring[end] not in self.identChars:
                    return end, ParseResults(self, [self.match])
            except IndexError:
                return end, ParseResults(self, [self.match])

        raise ParseException(instring, loc, self)


class CaselessKeyword(Keyword):
    """
    Caseless version of :class:`Keyword`.

    Example::

        OneOrMore(CaselessKeyword("CMD")).parseString("cmd CMD Cmd10") # -> ['CMD', 'CMD']

    (Contrast with example for :class:`CaselessLiteral`.)
    """

    def __init__(self, matchString, identChars=None, caseless=True):
        Keyword.__init__(
            self,
            matchString.upper(),
            set(c.upper() for c in identChars or engine.CURRENT.keyword_chars),
            caseless=True
        )

    def parseImpl(self, instring, loc, doActions=True):
        end = loc + self.matchLen
        if instring[loc : end].upper() == self.match:
            try:
                if instring[end] not in self.identChars:
                    return end, ParseResults(self, [self.match])
            except IndexError:
                return end, ParseResults(self, [self.match])
        raise ParseException(instring, loc, self)



class CaselessLiteral(Literal):
    """Token to match a specified string, ignoring case of letters.
    Note: the matched results will always be in the case of the given
    match string, NOT the case of the input text.

    Example::

        OneOrMore(CaselessLiteral("CMD")).parseString("cmd CMD Cmd10") # -> ['CMD', 'CMD', 'CMD']

    (Contrast with example for :class:`CaselessKeyword`.)
    """

    def __init__(self, matchString):
        super(CaselessLiteral, self).__init__(matchString.upper())
        # Preserve the defining literal.
        self.returnString = matchString
        self.parser_name = "'%s'" % self.returnString

    def copy(self):
        output = Literal.copy(self)
        output.returnString = self.returnString
        return output

    def parseImpl(self, instring, loc, doActions=True):
        if instring[loc : loc + self.matchLen].upper() == self.match:
            return loc + self.matchLen, ParseResults(self, [self.returnString])
        raise ParseException(instring, loc, self)


class CloseMatch(Token):
    """A variation on :class:`Literal` which matches "close" matches,
    that is, strings with at most 'n' mismatching characters.
    :class:`CloseMatch` takes parameters:

     - ``match_string`` - string to be matched
     - ``maxMismatches`` - (``default=1``) maximum number of
       mismatches allowed to count as a match

    The results from a successful parse will contain the matched text
    from the input string and the following named results:

     - ``mismatches`` - a list of the positions within the
       match_string where mismatches were found
     - ``original`` - the original match_string used to compare
       against the input string

    If ``mismatches`` is an empty list, then the match was an exact
    match.

    Example::

        patt = CloseMatch("ATCATCGAATGGA")
        patt.parseString("ATCATCGAAXGGA") # -> (['ATCATCGAAXGGA'], {'mismatches': [[9]], 'original': ['ATCATCGAATGGA']})
        patt.parseString("ATCAXCGAAXGGA") # -> Exception: Expected 'ATCATCGAATGGA' (with up to 1 mismatches) (at char 0), (line:1, col:1)

        # exact match
        patt.parseString("ATCATCGAATGGA") # -> (['ATCATCGAATGGA'], {'mismatches': [[]], 'original': ['ATCATCGAATGGA']})

        # close match allowing up to 2 mismatches
        patt = CloseMatch("ATCATCGAATGGA", maxMismatches=2)
        patt.parseString("ATCAXCGAAXGGA") # -> (['ATCAXCGAAXGGA'], {'mismatches': [[4, 9]], 'original': ['ATCATCGAATGGA']})
    """

    def __init__(self, match_string, maxMismatches=1):
        super(CloseMatch, self).__init__()
        self.parser_name = match_string
        self.match_string = match_string
        self.maxMismatches = maxMismatches
        self.parser_config.mayIndexError = False
        self.parser_config.mayReturnEmpty = False

    def parseImpl(self, instring, loc, doActions=True):
        start = loc
        instrlen = len(instring)
        maxloc = start + len(self.match_string)

        if maxloc <= instrlen:
            match_string = self.match_string
            match_stringloc = 0
            mismatches = []
            maxMismatches = self.maxMismatches

            for match_stringloc, s_m in enumerate(
                zip(instring[loc:maxloc], match_string)
            ):
                src, mat = s_m
                if src != mat:
                    mismatches.append(match_stringloc)
                    if len(mismatches) > maxMismatches:
                        break
            else:
                loc = match_stringloc + 1
                results = ParseResults(self, [instring[start:loc]])
                results["original"] = match_string
                results["mismatches"] = mismatches
                return loc, results

        raise ParseException(instring, loc, self)


class Word(Token):
    """Token for matching words composed of allowed character sets.
    Defined with string containing all allowed initial characters, an
    optional string containing allowed body characters (if omitted,
    defaults to the initial character set), and an optional minimum,
    maximum, and/or exact length.  The default value for ``min`` is
    1 (a minimum value < 1 is not valid); the default values for
    ``max`` and ``exact`` are 0, meaning no maximum or exact
    length restriction. An optional ``excludeChars`` parameter can
    list characters that might be found in the input ``bodyChars``
    string; useful to define a word of all printables except for one or
    two characters, for instance.

    :class:`srange` is useful for defining custom character set strings
    for defining ``Word`` expressions, using range notation from
    regular expression character sets.

    A common mistake is to use :class:`Word` to match a specific literal
    string, as in ``Word("Address")``. Remember that :class:`Word`
    uses the string argument to define *sets* of matchable characters.
    This expression would match "Add", "AAA", "dAred", or any other word
    made up of the characters 'A', 'd', 'r', 'e', and 's'. To match an
    exact literal string, use :class:`Literal` or :class:`Keyword`.

    mo_parsing includes helper strings for building Words:

     - :class:`alphas`
     - :class:`nums`
     - :class:`alphanums`
     - :class:`hexnums`
     - :class:`alphas8bit` (alphabetic characters in ASCII range 128-255
       - accented, tilded, umlauted, etc.)
     - :class:`punc8bit` (non-alphabetic characters in ASCII range
       128-255 - currency, symbols, superscripts, diacriticals, etc.)
     - :class:`printables` (any non-whitespace character)

    Example::

        # a word composed of digits
        integer = Word(nums) # equivalent to Word("0123456789") or Word(srange("0-9"))

        # a word with a leading capital, and zero or more lowercase
        capital_word = Word(alphas.upper(), alphas.lower())

        # hostnames are alphanumeric, with leading alpha, and '-'
        hostname = Word(alphas, alphanums + '-')

        # roman numeral (not a strict parser, accepts invalid mix of characters)
        roman = Word("IVXLCDM")

        # any string of non-whitespace characters, except for ','
        csv_value = Word(printables, excludeChars=",")
    """

    def __init__(
        self,
        initChars,
        bodyChars=None,
        min=1,
        max=0,
        exact=0,
        asKeyword=False,
        excludeChars=None,
    ):
        super(Word, self).__init__()
        if excludeChars:
            excludeChars = set(excludeChars)
            initChars = "".join(c for c in initChars if c not in excludeChars)
            if bodyChars:
                bodyChars = "".join(c for c in bodyChars if c not in excludeChars)
        self.initCharsOrig = initChars
        self.initChars = set(initChars)
        if bodyChars:
            self.bodyCharsOrig = bodyChars
            self.bodyChars = set(bodyChars)
        else:
            self.bodyCharsOrig = initChars
            self.bodyChars = set(initChars)

        self.maxSpecified = max > 0

        if min < 1:
            raise ValueError(
                "cannot specify a minimum length < 1; use Optional(Word()) if zero-length word is permitted"
            )

        self.minLen = min

        if max > 0:
            self.maxLen = max
        else:
            self.maxLen = _MAX_INT

        if exact > 0:
            self.maxLen = exact
            self.minLen = exact

        self.parser_name = text(self)
        self.parser_config.mayIndexError = False
        self.asKeyword = asKeyword

        if " " not in self.initCharsOrig + self.bodyCharsOrig and (
            min == 1 and max == 0 and exact == 0
        ):
            if self.bodyCharsOrig == self.initCharsOrig:
                self.reString = "[%s]+" % _escapeRegexRangeChars(self.initCharsOrig)
            elif len(self.initCharsOrig) == 1:
                self.reString = "%s[%s]*" % (
                    re.escape(self.initCharsOrig),
                    _escapeRegexRangeChars(self.bodyCharsOrig),
                )
            else:
                self.reString = "[%s][%s]*" % (
                    _escapeRegexRangeChars(self.initCharsOrig),
                    _escapeRegexRangeChars(self.bodyCharsOrig),
                )
            if self.asKeyword:
                self.reString = r"\b" + self.reString + r"\b"

            try:
                self.re = re.compile(self.reString)
            except Exception:
                self.re = None
            else:
                self.re_match = self.re.match
                self.__class__ = _WordRegex

    def copy(self):
        output = ParserElement.copy(self)
        output.asKeyword = self.asKeyword
        output.bodyChars = self.bodyChars
        output.bodyCharsOrig = self.bodyCharsOrig
        output.initChars = self.initChars
        output.initCharsOrig = self.initCharsOrig
        output.maxLen = self.maxLen
        output.maxSpecified = self.maxSpecified
        output.minLen = self.minLen
        if "re" in dir(self):
            output.re = self.re
            output.re_match = self.re.match
            output.reString = self.reString
        return output

    def parseImpl(self, instring, loc, doActions=True):
        if instring[loc] not in self.initChars:
            raise ParseException(instring, loc, self)

        start = loc
        loc += 1
        instrlen = len(instring)
        bodychars = self.bodyChars
        maxloc = start + self.maxLen
        maxloc = min(maxloc, instrlen)
        while loc < maxloc and instring[loc] in bodychars:
            loc += 1

        throwException = False
        if loc - start < self.minLen:
            throwException = True
        elif self.maxSpecified and loc < instrlen and instring[loc] in bodychars:
            throwException = True
        elif self.asKeyword:
            if (
                start > 0
                and instring[start - 1] in bodychars
                or loc < instrlen
                and instring[loc] in bodychars
            ):
                throwException = True

        if throwException:
            raise ParseException(instring, loc, self)

        return loc, ParseResults(self, [instring[start:loc]])

    def __str__(self):
        try:
            return super(Word, self).__str__()
        except Exception:
            pass

        def charsAsStr(s):
            if len(s) > 4:
                return s[:4] + "..."
            else:
                return s

        if self.initCharsOrig != self.bodyCharsOrig:
            return "W:(%s, %s)" % (
                charsAsStr(self.initCharsOrig),
                charsAsStr(self.bodyCharsOrig),
            )
        else:
            return "W:(%s)" % charsAsStr(self.initCharsOrig)


class _WordRegex(Word):
    def parseImpl(self, instring, loc, doActions=True):
        result = self.re_match(instring, loc)
        if not result:
            raise ParseException(instring, loc, self)

        loc = result.end()
        return loc, ParseResults(self, [result.group()])


class Char(_WordRegex):
    """A short-cut class for defining ``Word(characters, exact=1)``,
    when defining a match of any single character in a string of
    characters.
    """

    def __init__(self, charset, asKeyword=False, excludeChars=None):
        super(Char, self).__init__(
            charset, exact=1, asKeyword=asKeyword, excludeChars=excludeChars
        )
        self.reString = "[%s]" % _escapeRegexRangeChars("".join(self.initChars))
        if asKeyword:
            self.reString = r"\b%s\b" % self.reString
        self.re = re.compile(self.reString)
        self.re_match = self.re.match


class Regex(Token):
    r"""Token for matching strings that match a given regular
    expression. Defined with string specifying the regular expression in
    a form recognized by the stdlib Python  `re module <https://docs.python.org/3/library/re.html>`_.
    If the given regex contains named groups (defined using ``(?P<name>...)``),
    these will be preserved as named parse results.

    Example::

        realnum = Regex(r"[+-]?\d+\.\d*")
        date = Regex(r'(?P<year>\d{4})-(?P<month>\d\d?)-(?P<day>\d\d?)')
        # ref: https://stackoverflow.com/questions/267399/how-do-you-match-only-valid-roman-numerals-with-a-regular-expression
        roman = Regex(r"M{0,4}(CM|CD|D?{0,3})(XC|XL|L?X{0,3})(IX|IV|V?I{0,3})")
    """
    compiledREtype = type(re.compile("[A-Z]"))

    def __init__(self, pattern, flags=0, asGroupList=False, asMatch=False):
        """The parameters ``pattern`` and ``flags`` are passed
        to the ``re.compile()`` function as-is. See the Python
        `re module <https://docs.python.org/3/library/re.html>`_ module for an
        explanation of the acceptable patterns and flags.
        """
        super(Regex, self).__init__()

        if isinstance(pattern, basestring):
            if not pattern:
                warnings.warn(
                    "null string passed to Regex; use Empty() instead",
                    SyntaxWarning,
                    stacklevel=2,
                )

            self.pattern = pattern
            self.flags = flags

            try:
                self.re = re.compile(self.pattern, self.flags)
                self.reString = self.pattern
            except sre_constants.error:
                warnings.warn(
                    "invalid pattern (%s) passed to Regex" % pattern,
                    SyntaxWarning,
                    stacklevel=2,
                )
                raise

        elif isinstance(pattern, Regex.compiledREtype):
            self.re = pattern
            self.pattern = self.reString = str(pattern)
            self.flags = flags

        else:
            raise ValueError(
                "Regex may only be constructed with a string or a compiled RE object"
            )

        self.re_match = self.re.match

        self.parser_name = text(self)
        self.parser_config.mayIndexError = False
        self.parser_config.mayReturnEmpty = True
        self.asGroupList = asGroupList
        self.asMatch = asMatch
        if self.asGroupList:
            self.parseImpl = self.parseImplAsGroupList
        if self.asMatch:
            self.parseImpl = self.parseImplAsMatch

    def copy(self):
        output = ParserElement.copy(self)

        output.asGroupList = self.asGroupList
        output.asMatch = self.asMatch
        output.flags = self.flags
        output.pattern = self.pattern
        output.re = self.re
        output.reString = self.reString
        output.re_match = self.re_match
        return output

    def parseImpl(self, instring, loc, doActions=True):
        result = self.re_match(instring, loc)
        if not result:
            raise ParseException(instring, loc, self)

        loc = result.end()
        ret = ParseResults(self, [result.group()])
        d = result.groupdict()
        if d:
            for k, v in d.items():
                ret[k] = v
        return loc, ret

    def parseImplAsGroupList(self, instring, loc, doActions=True):
        result = self.re_match(instring, loc)
        if not result:
            raise ParseException(instring, loc, self)

        loc = result.end()
        ret = ParseResults(self, [result.groups()])
        return loc, ret

    def parseImplAsMatch(self, instring, loc, doActions=True):
        result = self.re_match(instring, loc)
        if not result:
            raise ParseException(instring, loc, self)

        loc = result.end()
        ret = ParseResults(self, [result])
        return loc, ret

    def __str__(self):
        try:
            return super(Regex, self).__str__()
        except Exception:
            pass

        return "Re:(%s)" % repr(self.pattern)

    def sub(self, repl):
        r"""
        Return Regex with an attached parse action to transform the parsed
        result as if called using `re.sub(expr, repl, string) <https://docs.python.org/3/library/re.html#re.sub>`_.

        Example::

            make_html = Regex(r"(\w+):(.*?):").sub(r"<\1>\2</\1>")
            print(make_html.transformString("h1:main title:"))
            # prints "<h1>main title</h1>"
        """
        if self.asGroupList:
            warnings.warn(
                "cannot use sub() with Regex(asGroupList=True)",
                SyntaxWarning,
                stacklevel=2,
            )
            raise SyntaxError()

        if self.asMatch and callable(repl):
            warnings.warn(
                "cannot use sub() with a callable with Regex(asMatch=True)",
                SyntaxWarning,
                stacklevel=2,
            )
            raise SyntaxError()

        if self.asMatch:

            def pa(tokens):
                return tokens[0].expand(repl)

        else:

            def pa(tokens):
                return self.re.sub(repl, tokens[0])

        return self.addParseAction(pa)


class QuotedString(Token):
    r"""
    Token for matching strings that are delimited by quoting characters.

    Defined with the following parameters:

        - quoteChar - string of one or more characters defining the
          quote delimiting string
        - escChar - character to escape quotes, typically backslash
          (default= ``None``)
        - escQuote - special quote sequence to escape an embedded quote
          string (such as SQL's ``""`` to escape an embedded ``"``)
          (default= ``None``)
        - multiline - boolean indicating whether quotes can span
          multiple lines (default= ``False``)
        - unquoteResults - boolean indicating whether the matched text
          should be unquoted (default= ``True``)
        - endQuoteChar - string of one or more characters defining the
          end of the quote delimited string (default= ``None``  => same as
          quoteChar)
        - convertWhitespaceEscapes - convert escaped whitespace
          (``'\t'``, ``'\n'``, etc.) to actual whitespace
          (default= ``True``)

    Example::

        qs = QuotedString('"')
        print(qs.searchString('lsjdf "This is the quote" sldjf'))
        complex_qs = QuotedString('{{', endQuoteChar='}}')
        print(complex_qs.searchString('lsjdf {{This is the "quote"}} sldjf'))
        sql_qs = QuotedString('"', escQuote='""')
        print(sql_qs.searchString('lsjdf "This is the quote with ""embedded"" quotes" sldjf'))

    prints::

        [['This is the quote']]
        [['This is the "quote"']]
        [['This is the quote with "embedded" quotes']]
    """

    def __init__(
        self,
        quoteChar,
        escChar=None,
        escQuote=None,
        multiline=False,
        unquoteResults=True,
        endQuoteChar=None,
        convertWhitespaceEscapes=True,
    ):
        super(QuotedString, self).__init__()

        # remove white space from quote chars - wont work anyway
        quoteChar = quoteChar.strip()
        if not quoteChar:
            warnings.warn(
                "quoteChar cannot be the empty string", SyntaxWarning, stacklevel=2
            )
            raise SyntaxError()

        if endQuoteChar is None:
            endQuoteChar = quoteChar
        else:
            endQuoteChar = endQuoteChar.strip()
            if not endQuoteChar:
                warnings.warn(
                    "endQuoteChar cannot be the empty string",
                    SyntaxWarning,
                    stacklevel=2,
                )
                raise SyntaxError()

        self.quoteChar = quoteChar
        self.quoteCharLen = len(quoteChar)
        self.firstQuoteChar = quoteChar[0]
        self.endQuoteChar = endQuoteChar
        self.endQuoteCharLen = len(endQuoteChar)
        self.escChar = escChar
        self.escQuote = escQuote
        self.unquoteResults = unquoteResults
        self.convertWhitespaceEscapes = convertWhitespaceEscapes

        if multiline:
            self.flags = re.MULTILINE | re.DOTALL
            self.pattern = r"%s(?:[^%s%s]" % (
                re.escape(self.quoteChar),
                _escapeRegexRangeChars(self.endQuoteChar[0]),
                (escChar is not None and _escapeRegexRangeChars(escChar) or ""),
            )
        else:
            self.flags = 0
            self.pattern = r"%s(?:[^%s\n\r%s]" % (
                re.escape(self.quoteChar),
                _escapeRegexRangeChars(self.endQuoteChar[0]),
                (escChar is not None and _escapeRegexRangeChars(escChar) or ""),
            )
        if len(self.endQuoteChar) > 1:
            self.pattern += (
                "|(?:"
                + ")|(?:".join(
                    "%s[^%s]"
                    % (
                        re.escape(self.endQuoteChar[:i]),
                        _escapeRegexRangeChars(self.endQuoteChar[i]),
                    )
                    for i in range(len(self.endQuoteChar) - 1, 0, -1)
                )
                + ")"
            )

        if escQuote:
            self.pattern += r"|(?:%s)" % re.escape(escQuote)
        if escChar:
            self.pattern += r"|(?:%s.)" % re.escape(escChar)
            self.escCharReplacePattern = re.escape(self.escChar) + "(.)"
        self.pattern += r")*%s" % re.escape(self.endQuoteChar)

        try:
            self.re = re.compile(self.pattern, self.flags)
            self.reString = self.pattern
            self.re_match = self.re.match
        except sre_constants.error:
            warnings.warn(
                "invalid pattern (%s) passed to Regex" % self.pattern,
                SyntaxWarning,
                stacklevel=2,
            )
            raise

        self.parser_name = text(self)
        self.parser_config.mayIndexError = False
        self.parser_config.mayReturnEmpty = True

    def parseImpl(self, instring, loc, doActions=True):
        result = (
            instring[loc] == self.firstQuoteChar
            and self.re_match(instring, loc)
            or None
        )
        if not result:
            raise ParseException(instring, loc, self)

        loc = result.end()
        ret = result.group()

        if self.unquoteResults:

            # strip off quotes
            ret = ret[self.quoteCharLen : -self.endQuoteCharLen]

            if isinstance(ret, basestring):
                # replace escaped whitespace
                if "\\" in ret and self.convertWhitespaceEscapes:
                    ws_map = {
                        r"\t": "\t",
                        r"\n": "\n",
                        r"\f": "\f",
                        r"\r": "\r",
                    }
                    for wslit, wschar in ws_map.items():
                        ret = ret.replace(wslit, wschar)

                # replace escaped characters
                if self.escChar:
                    ret = re.sub(self.escCharReplacePattern, r"\g<1>", ret)

                # replace escaped quotes
                if self.escQuote:
                    ret = ret.replace(self.escQuote, self.endQuoteChar)

        return loc, ParseResults(self, [ret])

    def __str__(self):
        try:
            return super(QuotedString, self).__str__()
        except Exception:
            pass

        return "quoted string, starting with %s ending with %s" % (
            self.quoteChar,
            self.endQuoteChar,
        )


class CharsNotIn(Token):
    """Token for matching words composed of characters *not* in a given
    set (will include whitespace in matched characters if not listed in
    the provided exclusion set - see example). Defined with string
    containing all disallowed characters, and an optional minimum,
    maximum, and/or exact length.  The default value for ``min`` is
    1 (a minimum value < 1 is not valid); the default values for
    ``max`` and ``exact`` are 0, meaning no maximum or exact
    length restriction.

    Example::

        # define a comma-separated-value as anything that is not a ','
        csv_value = CharsNotIn(',')
        print(delimitedList(csv_value).parseString("dkls,lsdkjf,s12 34,@!#,213"))

    prints::

        ['dkls', 'lsdkjf', 's12 34', '@!#', '213']
    """

    def __init__(self, notChars, min=1, max=0, exact=0):
        super(CharsNotIn, self).__init__()
        self.parser_config.skipWhitespace = False
        self.notChars = "".join(notChars)

        if min < 1:
            raise ValueError(
                "cannot specify a minimum length < 1; use "
                "Optional(CharsNotIn()) if zero-length char group is permitted"
            )

        self.minLen = min

        if max > 0:
            self.maxLen = max
        else:
            self.maxLen = _MAX_INT

        if exact > 0:
            self.maxLen = exact
            self.minLen = exact

        self.parser_name = text(self)
        self.parser_config.mayReturnEmpty = self.minLen == 0
        self.parser_config.mayIndexError = False

    def copy(self):
        output = ParserElement.copy(self)
        output.notChars = self.notChars
        output.minLen = self.minLen
        output.maxLen = self.maxLen
        return output

    def parseImpl(self, instring, loc, doActions=True):
        if instring[loc] in self.notChars:
            raise ParseException(instring, loc, self)

        start = loc
        loc += 1
        notchars = self.notChars
        maxlen = min(start + self.maxLen, len(instring))
        while loc < maxlen and instring[loc] not in notchars:
            loc += 1

        if loc - start < self.minLen:
            raise ParseException(instring, loc, self)

        return loc, ParseResults(self, [instring[start:loc]])

    def __str__(self):
        try:
            return super(CharsNotIn, self).__str__()
        except Exception:
            pass

        if len(self.notChars) > 4:
            return "!W:(%s...)" % self.notChars[:4]
        else:
            return "!W:(%s)" % self.notChars


class White(Token):
    """Special matching class for matching whitespace.  Normally,
    whitespace is ignored by mo_parsing grammars.  This class is included
    when some whitespace structures are significant.  Define with
    a string containing the whitespace characters to be matched; default
    is ``" \\t\\r\\n"``.  Also takes optional ``min``,
    ``max``, and ``exact`` arguments, as defined for the
    :class:`Word` class.
    """

    whiteStrs = {
        " ": "<SP>",
        "\t": "<TAB>",
        "\n": "<LF>",
        "\r": "<CR>",
        "\f": "<FF>",
        "u\00A0": "<NBSP>",
        "u\1680": "<OGHAM_SPACE_MARK>",
        "u\180E": "<MONGOLIAN_VOWEL_SEPARATOR>",
        "u\2000": "<EN_QUAD>",
        "u\2001": "<EM_QUAD>",
        "u\2002": "<EN_SPACE>",
        "u\2003": "<EM_SPACE>",
        "u\2004": "<THREE-PER-EM_SPACE>",
        "u\2005": "<FOUR-PER-EM_SPACE>",
        "u\2006": "<SIX-PER-EM_SPACE>",
        "u\2007": "<FIGURE_SPACE>",
        "u\2008": "<PUNCTUATION_SPACE>",
        "u\2009": "<THIN_SPACE>",
        "u\200A": "<HAIR_SPACE>",
        "u\200B": "<ZERO_WIDTH_SPACE>",
        "u\202F": "<NNBSP>",
        "u\205F": "<MMSP>",
        "u\3000": "<IDEOGRAPHIC_SPACE>",
    }

    def __init__(self, ws=" \t\r\n", min=1, max=0, exact=0):
        super(White, self).__init__()
        self.matchWhite = ws
        e = engine.CURRENT
        self.engine = Engine(
            white="".join(
                c for c in self.engine.white_chars if c not in self.matchWhite
            )
        )
        engine.CURRENT = e
        self.parser_name = "".join(White.whiteStrs[c] for c in self.matchWhite)
        self.parser_config.mayReturnEmpty = True

        self.minLen = min

        if max > 0:
            self.maxLen = max
        else:
            self.maxLen = _MAX_INT

        if exact > 0:
            self.maxLen = exact
            self.minLen = exact

    def parseImpl(self, instring, loc, doActions=True):
        if instring[loc] not in self.matchWhite:
            raise ParseException(instring, loc, self)
        start = loc
        loc += 1
        maxloc = start + self.maxLen
        maxloc = min(maxloc, len(instring))
        while loc < maxloc and instring[loc] in self.matchWhite:
            loc += 1

        if loc - start < self.minLen:
            raise ParseException(instring, loc, self)

        return loc, ParseResults(self, [instring[start:loc]])


class _PositionToken(Token):
    def __init__(self):
        super(_PositionToken, self).__init__()
        self.parser_name = self.__class__.__name__
        self.parser_config.mayReturnEmpty = True
        self.parser_config.mayIndexError = False


class GoToColumn(_PositionToken):
    """Token to advance to a specific column of input text; useful for
    tabular report scraping.
    """

    def __init__(self, colno):
        super(GoToColumn, self).__init__()
        self.col = colno

    def preParse(self, instring, loc):
        if col(loc, instring) != self.col:
            instrlen = len(instring)
            loc = self._skipIgnorables(instring, loc)
            while (
                loc < instrlen
                and instring[loc].isspace()
                and col(loc, instring) != self.col
            ):
                loc += 1
        return loc

    def parseImpl(self, instring, loc, doActions=True):
        thiscol = col(loc, instring)
        if thiscol > self.col:
            raise ParseException(instring, loc, "Text not in expected column", self)
        newloc = loc + self.col - thiscol
        ret = instring[loc:newloc]
        return newloc, ret


class LineStart(_PositionToken):
    r"""Matches if current position is at the beginning of a line within
    the parse string

    Example::

        test = '''\
        AAA this line
        AAA and this line
          AAA but not this one
        B AAA and definitely not this one
        '''

        for t in (LineStart() + 'AAA' + restOfLine).searchString(test):
            print(t)

    prints::

        ['AAA', ' this line']
        ['AAA', ' and this line']

    """

    def __init__(self):
        super(LineStart, self).__init__()

    def parseImpl(self, instring, loc, doActions=True):
        if col(loc, instring) == 1:
            return loc, ParseResults(self, [])
        raise ParseException(instring, loc, self)


class LineEnd(_PositionToken):
    """Matches if current position is at the end of a line within the
    parse string
    """

    def __init__(self):
        super(LineEnd, self).__init__()

    def parseImpl(self, instring, loc, doActions=True):
        if loc < len(instring):
            if instring[loc] == "\n":
                return loc + 1, ParseResults(self, ["\n"])
            else:
                raise ParseException(instring, loc, self)
        elif loc == len(instring):
            return loc + 1, ParseResults(self, [])
        else:
            raise ParseException(instring, loc, self)


class StringStart(_PositionToken):
    """Matches if current position is at the beginning of the parse
    string
    """

    def __init__(self):
        super(StringStart, self).__init__()

    def parseImpl(self, instring, loc, doActions=True):
        if loc != 0:
            # see if entire string up to here is just whitespace and ignoreables
            if loc != self.engine.skip(instring, 0):
                raise ParseException(instring, loc, self)
        return loc, []


class StringEnd(_PositionToken):
    """Matches if current position is at the end of the parse string
    """

    def __init__(self):
        super(StringEnd, self).__init__()

    def parseImpl(self, instring, loc, doActions=True):
        if loc < len(instring):
            raise ParseException(instring, loc, self)
        elif loc == len(instring):
            return loc + 1, ParseResults(self, [])
        elif loc > len(instring):
            return loc, ParseResults(self, [])
        else:
            raise ParseException(instring, loc, self)


class WordStart(_PositionToken):
    """Matches if the current position is at the beginning of a Word,
    and is not preceded by any character in a given set of
    ``wordChars`` (default= ``printables``). To emulate the
    ``\b`` behavior of regular expressions, use
    ``WordStart(alphanums)``. ``WordStart`` will also match at
    the beginning of the string being parsed, or at the beginning of
    a line.
    """

    def __init__(self, wordChars=printables):
        super(WordStart, self).__init__()
        self.wordChars = set(wordChars)

    def parseImpl(self, instring, loc, doActions=True):
        if loc != 0:
            if (
                instring[loc - 1] in self.wordChars
                or instring[loc] not in self.wordChars
            ):
                raise ParseException(instring, loc, self)
        return loc, ParseResults(self, [])


class WordEnd(_PositionToken):
    """Matches if the current position is at the end of a Word, and is
    not followed by any character in a given set of ``wordChars``
    (default= ``printables``). To emulate the ``\b`` behavior of
    regular expressions, use ``WordEnd(alphanums)``. ``WordEnd``
    will also match at the end of the string being parsed, or at the end
    of a line.
    """

    def __init__(self, wordChars=printables):
        super(WordEnd, self).__init__()
        self.wordChars = set(wordChars)
        self.parser_config.skipWhitespace = False

    def parseImpl(self, instring, loc, doActions=True):
        instrlen = len(instring)
        if instrlen > 0 and loc < instrlen:
            if (
                instring[loc] in self.wordChars
                or instring[loc - 1] not in self.wordChars
            ):
                raise ParseException(instring, loc, self)
        return loc, ParseResults(self, [])


# export
from mo_parsing import core, enhancement, engine, results

core.Empty = Empty
core.StringEnd = StringEnd
core.Literal = Literal
core.Token = Token

engine.Token = Token
engine.Literal = Literal
engine.CURRENT.literal = Literal

enhancement.Token = Token
enhancement.Literal = Literal
enhancement.Keyword = Keyword
enhancement.Word = Word
enhancement.CharsNotIn = CharsNotIn
enhancement._PositionToken = _PositionToken
enhancement.StringEnd = StringEnd

results.Token = Token
