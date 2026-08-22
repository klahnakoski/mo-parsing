# encoding: utf-8
from unittest import TestCase

from mo_testing.fuzzytestcase import add_error_reporting

from mo_parsing import (
    CaselessKeyword,
    CharsNotIn,
    Combine,
    Forward,
    Group,
    Keyword,
    LEFT_ASSOC,
    Literal,
    NotAny,
    OneOrMore,
    Optional,
    ParseException,
    Regex,
    Suppress,
    Whitespace,
    Word,
    ZeroOrMore,
    delimited_list,
    infix_notation,
    one_of,
)
from mo_parsing.core import Parser
from mo_parsing.enhancement import LookAhead
from mo_parsing.results import ParseResults
from mo_parsing.utils import alphanums, alphas, nums


def describe(result):
    """THE WHOLE RESULT TREE: TYPE, SPAN, AND TOKENS"""
    if not isinstance(result, ParseResults):
        return result
    return (
        result.__class__.__name__,
        id(result.type),
        result.start,
        result.end,
        [describe(t) for t in result.tokens],
    )


@add_error_reporting
class TestCompile(TestCase):
    """THE COMPILED FUNCTION MUST RETURN WHAT _parse RETURNS"""

    def setUp(self):
        self.whitespace = Whitespace().use()

    def tearDown(self):
        self.whitespace.release()

    def assertSameTree(self, expr, *strings):
        parser = Parser(expr)
        for string in strings:
            start = parser.whitespace.skip(string, 0)
            compiled = parser.compiled(string, start)
            interpreted = parser.element._parse(string, start)
            self.assertEqual(compiled.failed, interpreted.failed, string)
            if compiled.failed:
                continue
            self.assertEqual(describe(compiled), describe(interpreted), string)

    def test_leaves(self):
        self.assertSameTree(Literal("abc"), "abc", "abd", "")
        self.assertSameTree(Literal("x"), "x", "y", "")
        self.assertSameTree(Keyword("select"), "select a", "selecta", "")
        self.assertSameTree(CaselessKeyword("select"), "SeLeCt a", "selecta")
        self.assertSameTree(Word(alphas, alphanums), "ab12 ", "12")
        self.assertSameTree(CharsNotIn(",;"), "abc;", ";")
        self.assertSameTree(Regex(r"-?\d+"), "-42", "x")

    def test_and(self):
        expr = Word(alphas) + Literal("=") + Word(nums)
        self.assertSameTree(expr, "a = 1", "a = ", "1 = 1")

    def test_and_with_optional(self):
        expr = Word(alphas) + Optional(Literal("!")) + Literal(";")
        self.assertSameTree(expr, "a;", "a !;", "a ! ;", "a")

    def test_match_first(self):
        expr = Keyword("aa") | Keyword("bb") | Word(nums)
        self.assertSameTree(expr, "aa", "bb", "12", "cc")

    def test_named_alternative(self):
        expr = (Keyword("aa")("first") | Keyword("bb")) + Literal(".")
        self.assertSameTree(expr, "aa.", "bb.")

    def test_group_and_suppress(self):
        expr = Group(Suppress("(") + Word(alphas) + Suppress(")"))
        self.assertSameTree(expr, "(abc)", "()")

    def test_combine(self):
        expr = Combine(Word(alphas) + Literal(".") + Word(alphas))
        self.assertSameTree(expr, "a.b", "a . b")

    def test_repetition(self):
        self.assertSameTree(ZeroOrMore(Word(nums)), "1 2 3", "")
        self.assertSameTree(OneOrMore(Word(nums)), "1 2 3", "x")
        self.assertSameTree(delimited_list(Word(alphas)), "a, b, c", "a")

    def test_stop_on(self):
        expr = ZeroOrMore(Word(alphas), stop_on=Keyword("end")) + Keyword("end")
        self.assertSameTree(expr, "a b end", "end")

    def test_lookahead(self):
        self.assertSameTree(LookAhead(Keyword("a")) + Word(alphas), "abc", "a b")
        self.assertSameTree(NotAny(Keyword("a")) + Word(alphas), "b", "a")

    def test_parse_action(self):
        expr = (Word(alphas) / (lambda t: t.value().upper())) + Literal(";")
        self.assertSameTree(expr, "abc;", "abc")

    def test_forward(self):
        value = Forward()
        value << (Word(nums) | Group(Suppress("(") + ZeroOrMore(value) + Suppress(")")))
        self.assertSameTree(value, "(1 (2 3) 4)", "1", "(")

    def test_infix(self):
        expr = infix_notation(
            Word(alphas, alphanums) | Word(nums),
            [(one_of("* /"), 2, LEFT_ASSOC), (one_of("+ -"), 2, LEFT_ASSOC)],
        )
        self.assertSameTree(expr, "a + b * 2", "(a + b) * 2", "+")

    def test_json_grammar(self):
        value = Forward()
        string = Regex(r'"(?:[^"\\]|\\.)*"')
        number = Regex(r"-?\d+(?:\.\d+)?")
        member = Group(string("key") + Suppress(":") + value("value"))
        obj = Group(Suppress("{") + Optional(delimited_list(member)) + Suppress("}"))
        array = Group(Suppress("[") + Optional(delimited_list(value)) + Suppress("]"))
        value << (string | number | obj | array)
        self.assertSameTree(
            value, '{"a": [1, 2, {"b": "c"}], "d": {}}', "[]", "{", '"x"',
        )

    def test_forward_recompiles_after_shift(self):
        expr = Forward()
        expr << Word(nums)
        parser = expr.finalize()
        self.assertEqual(parser.parse("12"), "12")
        expr << Word(alphas)
        self.assertEqual(parser.parse("ab"), "ab")
        with self.assertRaises(ParseException):
            parser.parse("12")
