# encoding: utf-8
import re
import sre_constants
import warnings

from mo_future import text
from mo_parsing.utils import Log, escapeRegexRange

from mo_parsing.engine import Engine, PLAIN_ENGINE
from mo_parsing.exceptions import ParseException
from mo_parsing.core import ParserElement
from mo_parsing.results import ParseResults
from mo_parsing.utils import (
    MAX_INT,
    col,
    printables,
)


def _escapeRegexRangeChars(s):
    # ~  escape these chars: ^-]
    for c in r"\^-]":
        s = s.replace(c, "\\" + c)
    s = s.replace("\n", r"\n")
    s = s.replace("\t", r"\t")
    return text(s)


class Token(ParserElement):
    pass


class Empty(Token):
    """An empty token, will always match."""

    def __init__(self, name="Empty"):
        Token.__init__(self)
        self.parser_name = name

    def consume_at_least_one_char(self):
        return False


class NoMatch(Token):
    """A token that will never match."""

    def __init__(self):
        super(NoMatch, self).__init__()
        self.parser_name = "NoMatch"

    def parseImpl(self, string, loc, doActions=True):
        raise ParseException(self, loc, string)

    def consume_at_least_one_char(self):
        return False


class Literal(Token):
    """Token to exactly match a specified string."""

    def __init__(self, matchString):
        Token.__init__(self)
        self.parser_config.match = matchString

        if len(matchString) == 0:
            Log.error("Literal must be at least one character")
        elif len(matchString) == 1:
            self.__class__ = _SingleCharLiteral

    def parseImpl(self, string, start, doActions=True):
        match = self.parser_config.match
        if string.startswith(match, start):
            end = start + len(match)
            return ParseResults(self, start, end, [match])
        raise ParseException(self, start, string)

    def __str__(self):
        return self.parser_config.match


class _SingleCharLiteral(Literal):
    def parseImpl(self, string, start, doActions=True):
        try:
            if string[start] == self.parser_config.match:
                return ParseResults(self, start, start + 1, [self.parser_config.match])
        except IndexError:
            pass

        raise ParseException(self, start, string)


class Keyword(Token):
    """Token to exactly match a specified string as a keyword, that is,
    it must be immediately followed by a non-keyword character.  Compare
    with `Literal`:

     - ``Literal("if")`` will match the leading ``'if'`` in
       ``'ifAndOnlyIf'``.
     - ``Keyword("if")`` will not; it will only match the leading
       ``'if'`` in ``'if x=1'``, or ``'if(y==2)'``

    Accepts two optional constructor arguments in addition to the
    keyword string:

     - ``ident_chars`` is a string of characters that would be valid
       identifier characters, defaulting to all alphanumerics + "_" and
       "$"
     - ``caseless`` allows case-insensitive matching, default is ``False``.

    For case-insensitive matching, use `CaselessKeyword`.
    """

    def __new__(cls, matchString, ident_chars=None, caseless=None):
        if len(matchString) == 0:
            Log.error("Expecting more than one character in keyword")
        if caseless:
            return object.__new__(CaselessKeyword)
        else:
            return object.__new__(cls)

    def __init__(self, matchString, ident_chars=None, caseless=None):
        Token.__init__(self)
        if ident_chars is None:
            self.parser_config.ident_chars = self.engine.keyword_chars
        else:
            self.parser_config.ident_chars = "".join(sorted(set(ident_chars)))
        self.parser_config.match = matchString
        self.parser_name = matchString

    def parseImpl(self, string, start, doActions=True):
        match = self.parser_config.match
        ident_chars = self.parser_config.ident_chars

        if string.startswith(match, start):
            end = start + len(match)
            if end == len(string) or string[end] not in ident_chars:
                return ParseResults(self, start, end, [match])

        raise ParseException(self, start, string)


class CaselessKeyword(Keyword):
    def __init__(self, matchString, ident_chars=None, caseless=True):
        Keyword.__init__(
            self,
            matchString,
            ident_chars or engine.CURRENT.keyword_chars,
            caseless=True,
        )
        self.parser_config.re = re.compile(re.escape(matchString), re.IGNORECASE)

    def parseImpl(self, string, start, doActions=True):
        if self.parser_config.re.match(string, start):
            end = start + len(self.parser_config.match)
            if end == len(string) or string[end] not in self.parser_config.ident_chars:
                return ParseResults(self, start, end, [self.parser_config.match])
        raise ParseException(self, start, string)


class CaselessLiteral(Literal):
    """Token to match a specified string, ignoring case of letters.
    Note: the matched results will always be in the case of the given
    match string, NOT the case of the input text.
    """

    def __init__(self, match):
        Literal.__init__(self, match.upper())
        # Preserve the defining literal.
        self.parser_config.match = match
        self.parser_config.pattern = re.compile(re.escape(match), re.I)
        self.parser_name = repr(self.parser_config.pattern)

    def parseImpl(self, string, start, doActions=True):
        if self.parser_config.pattern.match(string, start):
            return ParseResults(
                self,
                start,
                start + len(self.parser_config.match),
                [self.parser_config.match],
            )
        raise ParseException(self, start, string)


class CloseMatch(Token):
    """A variation on `Literal` which matches "close" matches,
    that is, strings with at most 'n' mismatching characters.
    `CloseMatch` takes parameters:

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
        self.parser_config.match = match_string
        self.parser_config.maxMismatches = maxMismatches

    def parseImpl(self, string, start, doActions=True):
        end = start
        instrlen = len(string)
        maxloc = start + len(self.parser_config.match)

        if maxloc <= instrlen:
            match = self.parser_config.match
            match_stringloc = 0
            mismatches = []
            maxMismatches = self.parser_config.maxMismatches

            for match_stringloc, (src, mat) in enumerate(zip(
                string[end:maxloc], match
            )):
                if src != mat:
                    mismatches.append(match_stringloc)
                    if len(mismatches) > maxMismatches:
                        break
            else:
                end = match_stringloc + 1
                results = ParseResults(self, start, end, [string[start:end]])
                results["original"] = match
                results["mismatches"] = mismatches
                return results

        raise ParseException(self, start, string)


class Word(Token):
    """Token for matching words composed of allowed character sets.
    Defined with string containing all allowed initial characters, an
    optional string containing allowed body characters (if omitted,
    defaults to the initial character set), and an optional minimum,
    maximum, and/or exact length.  The default value for ``min`` is
    1 (a minimum value < 1 is not valid); the default values for
    ``max`` and ``exact`` are 0, meaning no maximum or exact
    length restriction. An optional ``excludeChars`` parameter can
    list characters that might be found in the input ``body_chars``
    string; useful to define a word of all printables except for one or
    two characters, for instance.

    `srange` is useful for defining custom character set strings
    for defining ``Word`` expressions, using range notation from
    regular expression character sets.

    A common mistake is to use `Word` to match a specific literal
    string, as in ``Word("Address")``. Remember that `Word`
    uses the string argument to define *sets* of matchable characters.
    This expression would match "Add", "AAA", "dAred", or any other word
    made up of the characters 'A', 'd', 'r', 'e', and 's'. To match an
    exact literal string, use `Literal` or `Keyword`.

    mo_parsing includes helper strings for building Words:

     - `alphas`
     - `nums`
     - `alphanums`
     - `hexnums`
     - `alphas8bit` (alphabetic characters in ASCII range 128-255
       - accented, tilded, umlauted, etc.)
     - `punc8bit` (non-alphabetic characters in ASCII range
       128-255 - currency, symbols, superscripts, diacriticals, etc.)
     - `printables` (any non-whitespace character)

    """

    def __init__(
        self,
        init_chars,
        body_chars=None,
        min=1,
        max=0,
        exact=0,
        asKeyword=False,
        excludeChars=None,
    ):
        super(Word, self).__init__()
        if body_chars is None:
            body_chars = init_chars

        if excludeChars:
            init_chars = set(init_chars) - set(excludeChars)
            body_chars = set(body_chars) - set(excludeChars)
        init_chars = self.parser_config.init_chars = "".join(sorted(set(init_chars)))
        body_chars = self.parser_config.body_chars = "".join(sorted(set(body_chars)))

        if min < 1:
            raise ValueError(
                "cannot specify a minimum length < 1; use Optional(Word()) if"
                " zero-length word is permitted"
            )

        self.parser_config.min_len = min
        self.parser_config.max_len = max if max > 0 else MAX_INT
        self.parser_config.max_specified = max > 0
        if exact > 0:
            self.parser_config.min_len = exact
            self.parser_config.max_len = max = exact
        self.parser_config.as_keyword = asKeyword

        if " " not in init_chars + body_chars and (
            min == 1 and max == 0 and exact == 0
        ):
            if body_chars == init_chars:
                regexp = "[%s]+" % _escapeRegexRangeChars(init_chars)
            elif len(init_chars) == 1:
                regexp = "%s[%s]*" % (
                    re.escape(init_chars),
                    _escapeRegexRangeChars(body_chars),
                )
            else:
                regexp = "[%s][%s]*" % (
                    _escapeRegexRangeChars(init_chars),
                    _escapeRegexRangeChars(body_chars),
                )
            if self.parser_config.as_keyword:
                regexp = r"\b" + regexp + r"\b"

            try:
                self.parser_config.pattern = re.compile(regexp)
                self.__class__ = _WordRegex
            except Exception:
                pass

    def parseImpl(self, string, start, doActions=True):
        try:
            first = string[start]
        except IndexError:
            raise ParseException(self, start, string)

        if first not in self.parser_config.init_chars:
            raise ParseException(self, start, string)

        end = start + 1
        instrlen = len(string)
        bodychars = self.parser_config.body_chars
        maxloc = start + self.parser_config.max_len
        maxloc = min(maxloc, instrlen)
        while end < maxloc and string[end] in bodychars:
            end += 1

        throwException = False
        if end - start < self.parser_config.min_len:
            throwException = True
        elif (
            self.parser_config.max_specified
            and end < instrlen
            and string[end] in bodychars
        ):
            throwException = True
        elif self.parser_config.as_keyword:
            if (
                start > 0
                and string[start - 1] in bodychars
                or end < instrlen
                and string[end] in bodychars
            ):
                throwException = True

        if throwException:
            raise ParseException(self, end, string)

        return ParseResults(self, start, end, [string[start:end]])

    def __str__(self):
        if self.parser_name:
            return self.parser_name
        return "W:(%s)" % str(self.parser_config.pattern)


class _WordRegex(Word):
    def parseImpl(self, string, start, doActions=True):
        result = self.parser_config.pattern.match(string, start)
        if not result:
            raise ParseException(self, start, string)

        return ParseResults(self, start, result.end(), [result.group()])


class Char(_WordRegex):
    """A short-cut class for defining ``Word(characters, exact=1)``,
    when defining a match of any single character in a string of
    characters.
    """

    def __init__(self, charset, asKeyword=False, excludeChars=None):
        super(Char, self).__init__(
            charset, exact=1, asKeyword=asKeyword, excludeChars=excludeChars
        )
        regex = escapeRegexRange("".join(self.parser_config.init_chars))
        if asKeyword:
            regex = r"\b%s\b" % self
        self.parser_config.pattern = re.compile(regex)


class Regex(Token):
    r"""Token for matching strings that match a given regular
    expression. Defined with string specifying the regular expression in
    a form recognized by the stdlib Python  `re module <https://docs.python.org/3/library/re.html>`_.
    If the given regex contains named groups (defined using ``(?P<name>...)``),
    these will be preserved as named parse results.
    """
    compiledREtype = type(re.compile("[A-Z]"))

    def __new__(cls, pattern, flags=0, asGroupList=False, asMatch=False):
        if asGroupList:
            return object.__new__(_RegExAsGroup)
        elif asMatch:
            return object.__new__(_RegExAsMatch)
        else:
            return object.__new__(cls)

    def __init__(self, pattern, flags=0, asGroupList=False, asMatch=False):
        """The parameters ``pattern`` and ``flags`` are passed
        to the ``re.compile()`` function as-is. See the Python
        `re module <https://docs.python.org/3/library/re.html>`_ module for an
        explanation of the acceptable patterns and flags.
        """
        super(Regex, self).__init__()
        self.parser_config.flags = flags

        if isinstance(pattern, text):
            if not pattern:
                warnings.warn(
                    "null string passed to Regex; use Empty() instead",
                    SyntaxWarning,
                    stacklevel=2,
                )

            try:
                self.parser_config.pattern = re.compile(
                    pattern, self.parser_config.flags
                )
            except sre_constants.error as cause:
                Log.error(
                    "invalid pattern {{pattern}} passed to Regex",
                    pattern=pattern,
                    cause=cause,
                )
        elif isinstance(pattern, Regex.compiledREtype):
            self.parser_config.pattern = pattern
        else:
            Log.error(
                "Regex may only be constructed with a string or a compiled RE object"
            )

        self.parser_name = text(self)

    def parseImpl(self, string, start, doActions=True):
        result = self.parser_config.pattern.match(string, start)
        if not result:
            raise ParseException(self, start, string)

        ret = ParseResults(self, start, result.end(), [result.group()])
        d = result.groupdict()
        if d:
            for k, v in d.items():
                ret[k] = v
        return ret

    def __str__(self):
        return repr(self.parser_config.pattern)

    def sub(self, repl):
        r"""
        Return Regex with an attached parse action to transform the parsed
        result as if called using `re.sub(expr, repl, string) <https://docs.python.org/3/library/re.html#re.sub>`_.

        Example::

            make_html = Regex(r"(\w+):(.*?):").sub(r"<\1>\2</\1>")
            print(make_html.transformString("h1:main title:"))
            # prints "<h1>main title</h1>"
        """

        def pa(tokens):
            return self.parser_config.pattern.sub(repl, tokens[0])

        return self.addParseAction(pa)


class _RegExAsGroup(Regex):
    def parseImpl(self, string, start, doActions=True):
        result = self.parser_config.pattern.match(string, start)
        if not result:
            raise ParseException(self, start, string)

        return ParseResults(self, start, result.end(), [result.groups()])

    def sub(self, repl):
        raise SyntaxError("cannot use sub() with Regex(asGroupList=True)")


class _RegExAsMatch(Regex):
    def parseImpl(self, string, start, doActions=True):
        result = self.parser_config.pattern.match(string, start)
        if not result:
            raise ParseException(self, start, string)

        return ParseResults(self, start, result.end(), [result])

    def sub(self, repl):
        if callable(repl):
            raise SyntaxError(
                "cannot use sub() with a callable with Regex(asMatch=True)"
            )

        def pa(tokens):
            return tokens[0].expand(repl)

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
        self.endQuoteChar = endQuoteChar
        self.escChar = escChar
        self.escQuote = escQuote
        self.unquoteResults = unquoteResults
        self.convertWhitespaceEscapes = convertWhitespaceEscapes

        if multiline:
            self.parser_config.flags = re.MULTILINE | re.DOTALL
            self.pattern = r"%s(?:[^%s%s]" % (
                re.escape(self.quoteChar),
                _escapeRegexRangeChars(self.endQuoteChar[0]),
                (escChar is not None and _escapeRegexRangeChars(escChar) or ""),
            )
        else:
            self.parser_config.flags = 0
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
            self.parser_config.pattern = re.compile(
                self.pattern, self.parser_config.flags
            )
            self.reString = self.pattern
        except sre_constants.error:
            warnings.warn(
                "invalid pattern (%s) passed to Regex" % self.pattern,
                SyntaxWarning,
                stacklevel=2,
            )
            raise

        self.parser_name = text(self)

    def parseImpl(self, string, start, doActions=True):
        result = self.parser_config.pattern.match(string, start)
        if not result:
            raise ParseException(self, start, string)

        end = result.end()
        ret = result.group()

        if self.unquoteResults:

            # strip off quotes
            ret = ret[len(self.quoteChar) : -len(self.endQuoteChar)]

            if isinstance(ret, text):
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

        return ParseResults(self, start, end, [ret])

    def copy(self):
        output = Token.copy(self)

        output.quoteChar = self.quoteChar
        output.endQuoteChar = self.endQuoteChar
        output.escChar = self.escChar
        output.escQuote = self.escQuote
        output.unquoteResults = self.unquoteResults
        output.convertWhitespaceEscapes = self.convertWhitespaceEscapes
        output.flags = self.parser_config.flags
        output.pattern = self.pattern
        output.regex = self.reString
        return output

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
        self.parser_config.not_chars = "".join(sorted(set(notChars)))

        if min < 1:
            raise ValueError(
                "cannot specify a minimum length < 1; use "
                "Optional(CharsNotIn()) if zero-length char group is permitted"
            )

        self.parser_config.min_len = min
        self.parser_config.max_len = max if max > 0 else MAX_INT
        if exact > 0:
            self.parser_config.max_len = exact
            self.parser_config.min_len = exact
        self.parser_name = text(self)

    def parseImpl(self, string, start, doActions=True):
        if string[start] in self.parser_config.not_chars:
            raise ParseException(self, start, string)

        end = start
        end += 1
        notchars = self.parser_config.not_chars
        maxlen = min(start + self.parser_config.max_len, len(string))
        while end < maxlen and string[end] not in notchars:
            end += 1

        if end - start < self.parser_config.min_len:
            raise ParseException(self, end, string)

        return ParseResults(self, start, end, [string[start:end]])

    def __str__(self):
        try:
            return super(CharsNotIn, self).__str__()
        except Exception:
            pass

        if len(self.parser_config.not_chars) > 4:
            return "!W:(%s...)" % self.parser_config.not_chars[:4]
        else:
            return "!W:(%s)" % self.parser_config.not_chars


class White(Token):
    """Special matching class for matching whitespace.  Normally,
    whitespace is ignored by mo_parsing grammars.  This class is included
    when some whitespace structures are significant.  Define with
    a string containing the whitespace characters to be matched; default
    is ``" \\t\\r\\n"``.  Also takes optional ``min``,
    ``max``, and ``exact`` arguments, as defined for the
    `Word` class.
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
        with Engine(white="".join(
            c for c in self.engine.white_chars if c not in ws
        )) as e:
            super(White, self).__init__()
            self.parser_config.lock_engine = e
        self.parser_config.white_chars = "".join(sorted(set(ws)))
        self.parser_name = "|".join(
            White.whiteStrs[c] for c in self.parser_config.white_chars
        )

        self.parser_config.min_len = min
        self.parser_config.max_len = max if max > 0 else MAX_INT
        if exact > 0:
            self.parser_config.max_len = exact
            self.parser_config.min_len = exact

    def parseImpl(self, string, start, doActions=True):
        if string[start] not in self.parser_config.white_chars:
            raise ParseException(self, start, string)
        end = start
        end += 1
        maxloc = start + self.parser_config.max_len
        maxloc = min(maxloc, len(string))
        while end < maxloc and string[end] in self.parser_config.white_chars:
            end += 1

        if end - start < self.parser_config.min_len:
            raise ParseException(self, end, string)

        return ParseResults(self, start, end, string[start:end])


class _PositionToken(Token):
    def __init__(self):
        super(_PositionToken, self).__init__()
        self.parser_name = self.__class__.__name__


class GoToColumn(_PositionToken):
    """Token to advance to a specific column of input text; useful for
    tabular report scraping.
    """

    def __init__(self, colno):
        super(GoToColumn, self).__init__()
        self.col = colno

    def preParse(self, string, loc):
        if col(loc, string) != self.col:
            instrlen = len(string)
            loc = self._skipIgnorables(string, loc)
            while (
                loc < instrlen
                and string[loc].isspace()
                and col(loc, string) != self.col
            ):
                loc += 1
        return loc

    def parseImpl(self, string, start, doActions=True):
        thiscol = col(start, string)
        if thiscol > self.col:
            raise ParseException(self, start, string, "Text not in expected column")
        newloc = start + self.col - thiscol
        ret = string[start:newloc]
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

    def parseImpl(self, string, start, doActions=True):
        if col(start, string) == 1:
            return ParseResults(self, start, start, [])
        raise ParseException(self, start, string)


class LineEnd(_PositionToken):
    """Matches if current position is at the end of a line within the
    parse string
    """

    def __init__(self):
        with Engine(" \t") as e:
            super(LineEnd, self).__init__()
            self.parser_config.lock_engine = e

    def parseImpl(self, string, start, doActions=True):
        if start < len(string):
            if string[start] == "\n":
                return ParseResults(self, start, start + 1, ["\n"])
            else:
                raise ParseException(self, start, string)
        elif start == len(string):
            return ParseResults(self, start, start, [])
        else:
            raise ParseException(self, start, string)


class StringStart(_PositionToken):
    """Matches if current position is at the beginning of the parse
    string
    """

    def __init__(self):
        super(StringStart, self).__init__()

    def parseImpl(self, string, loc, doActions=True):
        if loc != 0:
            # see if entire string up to here is just whitespace and ignoreables
            if loc != self.engine.skip(string, 0):
                raise ParseException(self, loc, string)
        return []


class StringEnd(_PositionToken):
    """
    Matches if current position is at the end of the parse string
    """

    def __init__(self):
        with Engine() as e:
            super(StringEnd, self).__init__()
            self.parser_config.lock_engine = e

    def parseImpl(self, string, start, doActions=True):
        end = len(string)
        if start >= end:
            return ParseResults(self, end, end, [])

        raise ParseException(self, start, string)


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
        self.parser_config.word_chars = "".join(sorted(set(wordChars)))

    def parseImpl(self, string, start, doActions=True):
        if start:
            if start >= len(string):
                raise ParseException(self, start, string)
            if (
                string[start - 1] in self.parser_config.word_chars
                or string[start] not in self.parser_config.word_chars
            ):
                raise ParseException(self, start, string)
        return ParseResults(self, start, start, [])


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
        self.engine = PLAIN_ENGINE
        self.parser_config.word_chars = "".join(sorted(set(wordChars)))

    def copy(self):
        output = _PositionToken.copy(self)
        output.engine = PLAIN_ENGINE
        return output

    def parseImpl(self, string, start, doActions=True):
        word_chars = self.parser_config.word_chars
        instrlen = len(string)
        if instrlen > 0 and start < instrlen:
            if string[start] in word_chars or string[start - 1] not in word_chars:
                raise ParseException(self, start, string)
        return ParseResults(self, start, start, [])


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
enhancement.Empty = Empty

results.Token = Token
results.Empty = Empty
