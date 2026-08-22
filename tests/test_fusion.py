# encoding: utf-8
from unittest import TestCase

from mo_testing.fuzzytestcase import add_error_reporting

from mo_parsing import (
    CaselessKeyword,
    CharsNotIn,
    Combine,
    Group,
    Keyword,
    Literal,
    Optional,
    ParseException,
    Regex,
    Suppress,
    Whitespace,
    whitespaces,
    Word,
)
from mo_parsing.utils import alphas, nums


def fused_runs(expr):
    """THE FUSED ROWS OF expr, ONCE STREAMLINED"""
    element = expr.streamline()
    return [row[3] for row in element.plan if row[3] is not None]


@add_error_reporting
class TestFusion(TestCase):
    def setUp(self):
        self.whitespace = Whitespace().use()

    def tearDown(self):
        self.whitespace.release()

    def test_run_is_fused(self):
        expr = Word(alphas) + Literal("x")
        self.assertEqual(len(fused_runs(expr)), 1)

    def test_greedy_word_does_not_give_back(self):
        # PEG: Word eats the x, so the Literal has nothing left
        expr = Word(alphas) + Literal("x")
        self.assertEqual(len(fused_runs(expr)), 1)
        with self.assertRaises(ParseException):
            expr.parse("abcx", parse_all=True)
        self.assertEqual(list(expr.parse("abc x", parse_all=True)), ["abc", "x"])

    def test_greedy_chars_not_in_does_not_give_back(self):
        expr = CharsNotIn(",") + Literal(";")
        self.assertEqual(len(fused_runs(expr)), 1)
        with self.assertRaises(ParseException):
            expr.parse("abc;", parse_all=True)
        self.assertEqual(
            list((CharsNotIn(",;") + Literal(";")).parse("abc;")), ["abc", ";"]
        )

    def test_optional_breaks_the_run(self):
        expr = Literal("a") + Optional(Literal("b")) + Literal("c")
        self.assertEqual(fused_runs(expr), [])
        self.assertEqual(list(expr.parse("a b c", parse_all=True)), ["a", "b", "c"])
        self.assertEqual(list(expr.parse("a c", parse_all=True)), ["a", "c"])

    def test_optional_run_on_each_side(self):
        expr = (
            Word(alphas)
            + Word(nums)
            + Optional(Literal("!"))
            + Literal("(")
            + Literal(")")
        )
        self.assertEqual(len(fused_runs(expr)), 2)
        self.assertEqual(
            list(expr.parse("ab 12 ! ( )", parse_all=True)), ["ab", "12", "!", "(", ")"]
        )
        self.assertEqual(
            list(expr.parse("ab 12 ( )", parse_all=True)), ["ab", "12", "(", ")"]
        )

    def test_names_survive_fusion(self):
        expr = Word(alphas)("first") + Word(nums)("second")
        self.assertEqual(len(fused_runs(expr)), 1)
        result = expr.parse("abc 123", parse_all=True)
        self.assertEqual(list(result), ["abc", "123"])
        self.assertEqual(result["first"], "abc")
        self.assertEqual(result["second"], "123")

    def test_keyword_keeps_its_canonical_text(self):
        expr = CaselessKeyword("select") + CaselessKeyword("distinct")
        self.assertEqual(len(fused_runs(expr)), 1)
        self.assertEqual(
            list(expr.parse("SELECT   DiStInCt", parse_all=True)),
            ["select", "distinct"],
        )

    def test_keyword_boundary_is_kept(self):
        expr = Keyword("select") + Keyword("all")
        self.assertEqual(len(fused_runs(expr)), 1)
        with self.assertRaises(ParseException):
            expr.parse("select allow", parse_all=True)

    def test_suppressed_run_member_is_empty(self):
        expr = Word(alphas) + Suppress(",") + Word(alphas)
        self.assertEqual(len(fused_runs(expr)), 1)
        self.assertEqual(list(expr.parse("a , b", parse_all=True)), ["a", "b"])

    def test_suppress_marker_from_suppress_is_a_boundary(self):
        # `.suppress()` wraps the marker in a parse action, so this run does not fuse
        expr = Word(alphas) + Literal(",").suppress() + Word(alphas)
        self.assertEqual(fused_runs(expr), [])
        self.assertEqual(list(expr.parse("a , b", parse_all=True)), ["a", "b"])

    def test_suppress_alone_is_fused(self):
        expr = Suppress(Literal(",")).streamline()
        self.assertNotEqual(expr.regex, None)
        self.assertEqual(
            list((Word(alphas) + Group(expr + Word(alphas))).parse("a , b")),
            ["a", ["b"]],
        )

    def test_spans_are_unchanged(self):
        expr = Group(Word(alphas) + Word(nums))
        result = expr.parse("  abc   123  ")
        first, second = result.tokens[0].tokens
        self.assertEqual((first.start, first.end), (2, 5))
        self.assertEqual((second.start, second.end), (8, 11))

    def test_group_is_a_boundary(self):
        expr = Group(Word(alphas)) + Group(Word(nums))
        self.assertEqual(fused_runs(expr), [])
        self.assertEqual(
            expr.parse("abc 123", parse_all=True).as_list(), [["abc"], ["123"]]
        )

    def test_parse_action_is_a_boundary(self):
        expr = (Word(alphas) / (lambda t: t[0].upper())) + Word(nums)
        self.assertEqual(fused_runs(expr), [])
        self.assertEqual(list(expr.parse("abc 123", parse_all=True)), ["ABC", "123"])

    def test_comments_between_fused_children(self):
        with Whitespace() as white:
            white.add_ignore(Literal("--") + Regex(r"[^\n]*"))
            expr = Word(alphas) + Word(nums)
        self.assertEqual(len(fused_runs(expr)), 1)
        self.assertEqual(
            list(expr.parse("abc -- note\n 123", parse_all=True)), ["abc", "123"]
        )

    def test_no_whitespace_puts_nothing_between(self):
        with whitespaces.NO_WHITESPACE:
            inner = Word(alphas) + Word(nums)
            expr = Combine(inner)
        self.assertEqual(len(fused_runs(inner)), 1)
        self.assertEqual(list(expr.parse("abc123", parse_all=True)), ["abc123"])
        with self.assertRaises(ParseException):
            expr.parse("abc 123", parse_all=True)

    def test_combine_of_a_suppress_is_empty(self):
        # Combine calls parse_impl directly, so it used to miss the suppression
        self.assertEqual(list(Combine(Suppress(Word(alphas))).parse("abc")), [""])
        self.assertEqual(
            list(Combine(Word(alphas) + Suppress("-") + Word(alphas)).parse("ab-cd")),
            ["abcd"],
        )

    def test_regex_with_its_own_group(self):
        expr = Regex(r"(ab)+") + Literal(";")
        self.assertEqual(len(fused_runs(expr)), 1)
        self.assertEqual(list(expr.parse("ababab;", parse_all=True)), ["ababab", ";"])

    def test_regex_that_will_not_embed_is_left_alone(self):
        # the group name collides with the one fusion generates
        expr = Regex(r"(?P<f0>ab)") + Literal(";")
        self.assertEqual(fused_runs(expr), [])
        self.assertEqual(list(expr.parse("ab;", parse_all=True)), ["ab", ";"])

    def test_failure_message_is_the_same_fused_or_not(self):
        fused = Keyword("select") + Keyword("from")
        # a no-op parse action makes the first child un-fusable
        plain = (Keyword("select") / (lambda t: t)) + Keyword("from")
        self.assertEqual(len(fused_runs(fused)), 1)
        self.assertEqual(fused_runs(plain), [])

        def message(expr):
            try:
                expr.parse("select where", parse_all=True)
            except ParseException as cause:
                return str(cause)
            return None

        self.assertEqual(message(fused), message(plain))
        self.assertTrue("from" in message(fused))
