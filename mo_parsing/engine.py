# encoding: utf-8
import sys
from collections import namedtuple

from mo_dots import Null
from mo_future import is_text, text
from mo_logs import Log, strings

from mo_parsing.exceptions import ParseException
from mo_parsing.utils import lineno, col, alphanums

ParserElement, Literal, Token = [None] * 3

CURRENT = None


class Engine:
    def __init__(self, white=" \n\r\t"):
        self.literal = Literal
        self.keyword_chars = alphanums + "_$"
        self.ignore_list = []
        self.debugActions = DebugActions(noop, noop, noop)
        self.all_exceptions = {}
        self.content = None
        self.skips = {}
        self.set_whitespace(white)
        self.previous = None  # WE MAINTAIN A STACK OF ENGINES

    def __enter__(self):
        global CURRENT
        self.previous = CURRENT  # WE MAINTAIN A STACK OF ENGINES
        CURRENT = self
        return self

    use = __enter__

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        ENSURE self IS NOT CURRENT
        :return:
        """
        global CURRENT
        if not self.previous:
            Log.error("expecting engine to be released just once")

        CURRENT = self.previous
        self.previous = None

    def release(self):
        self.__exit__(None, None, None)

    def normalize(self, expr):
        if expr == None:
            return Null
        if is_text(expr):
            if issubclass(self.literal, Token):
                return self.literal(expr)
            else:
                return self.literal(Literal(expr))
        if not isinstance(expr, ParserElement):
            Log.error("expecting string, or ParserElemenet")

        # curr_engine = expr.engine
        # if curr_engine != self and not expr.parser_config.lock_engine:
        #     # UPDATE ENGINE IF NOT LOCKED
        #     expr = expr.copy()
        return expr

    def record_exception(self, instring, loc, expr, exc):
        es = self.all_exceptions.setdefault(loc, [])
        es.append(exc)

    def set_debug_actions(
        self, startAction=None, successAction=None, exceptionAction=None
    ):
        """
        Enable display of debugging messages while doing pattern matching.
        """
        self.debugActions = DebugActions(
            startAction or _defaultStartDebugAction,
            successAction or _defaultSuccessDebugAction,
            exceptionAction or _defaultExceptionDebugAction,
        )
        return self

    def set_recursion_limit(self, limit):
        sys.setrecursionlimit(limit)

    def set_literal(self, literal):
        self.literal = literal

    def set_keyword_chars(self, chars):
        self.keyword_chars = "".join(sorted(set(chars)))

    def set_whitespace(self, chars):
        self.white_chars = "".join(sorted(set(chars)))

    def add_ignore(self, ignore_expr):
        """
        ADD TO THE LIST OF IGNORED EXPRESSIONS
        :param ignore_expr:
        """
        ignore_expr = ignore_expr.suppress()
        self.ignore_list.append(ignore_expr)
        return self

    def skip(self, instring, start):
        if instring is self.content:
            end = self.skips.get(start)
            if end is not None:
                return end
        else:
            self.skips = {}
            self.content = instring
        end = self.skips[start] = start  # TO AVOID RECURSIVE LOOP
        wt = self.white_chars
        instrlen = len(instring)

        more = True  # ENSURE ALTERNATING WHITESPACE AND IGNORABLES ARE SKIPPED
        while more:
            more = False
            while end < instrlen and instring[end] in wt:
                more = True
                end += 1

            for i in self.ignore_list:
                try:
                    next_end, _ = i.parseImpl(instring, end)
                    if next_end > end:
                        more = True
                        end = next_end
                except ParseException as e:
                    pass

        self.skips[start] = end  # THE REAL VALUE
        return end

    def __str__(self):
        output = ["{"]
        for k, v in self.__dict__.items():
            value = str(v)
            output.append(strings.indent(strings.quote(k) + ":" + value))
        output.append("}")
        return "\n".join(output)


def _defaultStartDebugAction(instring, loc, expr):
    print(
        "Match "
        + text(expr)
        + " at loc "
        + text(loc)
        + "(%d,%d)" % (lineno(loc, instring), col(loc, instring))
    )


def _defaultSuccessDebugAction(instring, startloc, endloc, expr, toks):
    print("Matched " + text(expr) + " -> " + str(toks))


def _defaultExceptionDebugAction(instring, loc, expr, exc):
    print("Exception raised:" + text(exc))


def noop(*args):
    return


DebugActions = namedtuple("DebugActions", ["TRY", "MATCH", "FAIL"])

PLAIN_ENGINE = Engine("").use()
Engine().use()
