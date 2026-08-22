# encoding: utf-8
import json
from contextlib import contextmanager

from mo_future import text, is_text, sort_using_cmp
from mo_imports import export, expect

from mo_parsing.utils import Log, enlist, quote, indent
from mo_parsing.utils import col, line, lineno

MatchFirst = expect("MatchFirst")

# collect and rank failure causes; Parser turns this on to re-parse after a failure
DIAGNOSTICS = False


@contextmanager
def diagnostics():
    global DIAGNOSTICS
    previous = DIAGNOSTICS
    DIAGNOSTICS = True
    try:
        yield
    finally:
        DIAGNOSTICS = previous


class ParseException(Exception):
    """base exception class for all parsing runtime exceptions"""

    # Performance tuning: we construct a *lot* of these, so keep this
    # constructor as small and fast as possible
    __slots__ = ["expr", "start", "string", "unsorted_cause", "_msg", "_causes", "_loc"]

    # marks a returned value as a failure; ParseResults.failed is False
    failed = True

    def __init__(self, expr, start, string, msg="", cause=None):
        if not isinstance(string, str):
            Log.error("expecting string")
        self.expr = expr
        self.start = start
        self.string = string
        self.unsorted_cause = cause if DIAGNOSTICS else None
        self._msg = msg
        self._causes = None
        self._loc = None

    @property
    def causes(self):
        if self._causes is None:
            if self.unsorted_cause is None:
                self._causes = []
            else:
                self._causes = sort_causes(enlist(self.unsorted_cause))
        return self._causes

    @property
    def __cause__(self):
        return None

    @property
    def best_cause(self):
        if not self.causes:
            return self

        best = [c.best_cause for c in self.causes if isinstance(c, ParseException)]
        if not best:
            return self

        best_0 = best[0]
        if (
            self.expr.parser_name
            and self.start >= best_0.start
            and not best_0.expr.parser_name
        ):
            return self
        elif len(best) == 1:
            return best_0
        else:
            return ParseException(
                MatchFirst([
                    b.expr for b in best if compare_causes(b, best_0) == 0
                ]).streamline(),
                best_0.start,
                best_0.string,
                msg=best_0._msg,
                cause=best,
            )

    @property
    def best_message(self):
        return self.best_cause.message

    @property
    def loc(self):
        if self._loc is None:
            causes = self.causes
            if causes and isinstance(causes[0], ParseException):
                self._loc = causes[0].loc
            else:
                self._loc = self.start
        return self._loc

    @property
    def message(self):
        if self._msg:
            expecting = f"{self._msg} ({self.expr})"
        else:
            expecting = f"Expecting {self.expr}"

        if self.loc >= len(self.string):
            found = ", found end of text"
        else:
            found = f", found {quote(self.string[self.loc: self.loc + 10])}"

        if self.causes and not isinstance(self.causes[0], ParseException):
            describe_cause = f", caused by {self.causes[0]}"
        else:
            describe_cause = ""

        location = f" (at char {self.loc}), (line:{self.lineno}, col:{self.column})"

        return "".join((expecting, found, describe_cause, location))

    @message.setter
    def msg(self, value):
        self._msg = value

    @property
    def line(self):
        return line(self.loc, self.string)

    @property
    def lineno(self):
        return lineno(self.loc, self.string)

    @property
    def col(self):
        return col(self.loc, self.string)

    @property
    def column(self):
        return col(self.loc, self.string)

    def __contains__(self, item):
        if is_text(item) and item in text(self):
            return True
        if (
            isinstance(item, type)
            and issubclass(item, Exception)
            and isinstance(self, item)
        ):
            return True
        for c in self.causes:
            if item in c:
                return True
        return False

    def __str__(self):
        return self.best_message

    def __repr__(self):
        if not self.causes:
            return f"{self.message}"

        causes = indent("".join("\n" + str(c) for c in self.causes))
        return f"{self.message}\n{causes}"

    def mark_inputline(self, marker_string=">!<"):
        """Extracts the exception line from the input string, and marks
        the location of the exception with a special symbol.
        """
        line_str = self.line
        line_column = self.column - 1
        if marker_string:
            line_str = "".join((
                line_str[:line_column],
                marker_string,
                line_str[line_column:],
            ))
        return line_str.strip()

    def __dir__(self):
        return "lineno col line".split() + dir(type(self))


class ParseSyntaxException(ParseException):
    """
    just like `ParseFatalException`, but thrown internally
    when an `ErrorStop<And.SyntaxErrorGuard>` ('-' operator) indicates
    that parsing is to stop immediately because an unbacktrackable
    syntax error has been found.
    """

    __slots__ = []


class RecursiveGrammarException(Exception):
    """exception thrown by `ParserElement.validate` if the
    grammar could be improperly recursive
    """

    __slots__ = []

    def __init__(self, cycle):
        self.parseElementTrace = cycle

    def __str__(self):
        return "RecursiveGrammarException: " + json.dumps([
            str(e) for e in self.parseElementTrace
        ])


# returned (never raised) when a parse fails and we are not diagnosing
FAIL = ParseException(None, 0, "")


def failure(expr, start, string, msg="", cause=None):
    """FAILURE VALUE FOR expr AT start"""
    return ParseException(expr, start, string, msg, cause) if DIAGNOSTICS else FAIL


def failure_at(cause, causes, type=ParseException):
    """FAILURE VALUE AT THE POSITION OF cause"""
    if not DIAGNOSTICS:
        return FAIL
    return type(cause.expr, cause.loc, cause.string, cause=causes)


def compare_causes(a, b):
    if isinstance(a, ParseException):
        if isinstance(b, ParseException):
            if a.loc < b.loc:
                return 1
            elif a.loc > b.loc:
                return -1
            elif b.expr.parser_name:
                if a.expr.parser_name:
                    return 0
                else:
                    return 1
            elif a.expr.parser_name:
                return -1
            elif b._msg:
                return 1
            elif a._msg:
                return -1
            else:
                return 0
        else:
            return 1
    elif isinstance(b, ParseException):
        return -1
    else:
        return 0


def sort_causes(causes):
    return list(sort_using_cmp(causes, cmp=compare_causes))


export("mo_parsing.utils", ParseException)
