# encoding: utf-8
import re

from mo_parsing import (
    Regex,
    Char,
    LookAhead,
    MatchFirst,
    Optional,
    OneOrMore,
    ZeroOrMore,
    Whitespace,
    whitespaces,
    CaselessKeyword,
)
from mo_parsing.tokens import SingleCharLiteral, Literal, Keyword, CharsNotIn
from mo_parsing.utils import alphas, regex_compile
from tests.test_simple_unit import PyparsingExpressionTestCase, SkipTo


class TestRegexParsing(PyparsingExpressionTestCase):
    def test_parsing_real_numbers_using_regex_instead_of_combine(self):
        self.run_test(
            desc="Parsing real numbers - using Regex instead of Combine",
            expr=(Regex(r"\d+\.\d+") / (lambda t: float(t[0])))[...],
            text="1.2 2.3 3.1416 98.6",
            expected_list=[
                1.2,
                2.3,
                3.1416,
                98.6,
            ],  # note, these are now floats, not strs
        )

    def testParseUsingRegex(self):

        signedInt = Regex(r"[-+][0-9]+")
        unsignedInt = Regex(r"[0-9]+")
        simple_string = Regex(r'("[^\"]*")|(\'[^\']*\')')
        namedGrouping = Regex(r'("(?P<content>[^\"]*)")').capture_groups()
        compiledRE = Regex(re.compile(r"[A-Z]+").pattern)

        def testMatch(expression, instring, shouldPass, expected_string=None):
            if shouldPass:
                result = expression.parse_string(instring)
                self.assertEqual(result, expected_string)
            else:
                with self.assertRaises(Exception):
                    expression.parse_string(instring)

            return True

        # These should fail
        self.assertTrue(
            testMatch(signedInt, "1234 foo", False), "Re: (1) passed, expected fail"
        )
        self.assertTrue(
            testMatch(signedInt, "    +foo", False), "Re: (2) passed, expected fail"
        )
        self.assertTrue(
            testMatch(unsignedInt, "abc", False), "Re: (3) passed, expected fail"
        )
        self.assertTrue(
            testMatch(unsignedInt, "+123 foo", False), "Re: (4) passed, expected fail"
        )
        self.assertTrue(
            testMatch(simple_string, "foo", False), "Re: (5) passed, expected fail"
        )
        self.assertTrue(
            testMatch(simple_string, "\"foo bar'", False),
            "Re: (6) passed, expected fail",
        )
        self.assertTrue(
            testMatch(simple_string, "'foo bar\"", False),
            "Re: (7) passed, expected fail",
        )

        # self.assertTrue(
        #     testMatch(signedInt, "   +123", True, "+123"),
        #     "Re: (8) failed, expected pass",
        # )
        self.assertTrue(
            testMatch(signedInt, "+123", True, "+123"), "Re: (9) failed, expected pass"
        )
        self.assertTrue(
            testMatch(signedInt, "+123 foo", True, "+123"),
            "Re: (10) failed, expected pass",
        )
        self.assertTrue(
            testMatch(signedInt, "-0 foo", True, "-0"), "Re: (11) failed, expected pass"
        )
        self.assertTrue(
            testMatch(unsignedInt, "123 foo", True, "123"),
            "Re: (12) failed, expected pass",
        )
        self.assertTrue(
            testMatch(unsignedInt, "0 foo", True, "0"), "Re: (13) failed, expected pass"
        )
        self.assertTrue(
            testMatch(simple_string, '"foo"', True, '"foo"'),
            "Re: (14) failed, expected pass",
        )
        self.assertTrue(
            testMatch(simple_string, "'foo bar' baz", True, "'foo bar'"),
            "Re: (15) failed, expected pass",
        )

        self.assertTrue(
            testMatch(compiledRE, "blah", False), "Re: (16) passed, expected fail"
        )
        self.assertTrue(
            testMatch(compiledRE, "BLAH", True, "BLAH"),
            "Re: (17) failed, expected pass",
        )

        self.assertTrue(
            testMatch(namedGrouping, '"foo bar" baz', True, '"foo bar"'),
            "Re: (16) failed, expected pass",
        )
        ret = namedGrouping.parse_string('"zork" blah')

        self.assertEqual(ret["content"], "zork", "named group lookup failed")
        self.assertEqual(
            ret[0],
            simple_string.parse_string('"zork" blah')[0],
            "Regex not properly returning ParseResults for named vs. unnamed groups",
        )

        with self.assertRaises(Exception):
            Regex("(\"[^\"]*\")|('[^']*'")

        with self.assertRaises():
            Regex("")

    def testRegexAsType(self):

        test_str = "sldkjfj 123 456 lsdfkj"

        expr = Regex(r"\w+ (\d+) (\d+) (\w+)").capture_groups()
        expected_group_list = test_str.split()[1:]
        result = expr.parse_string(test_str)

        self.assertParseResultsEquals(
            result,
            expected_list=expected_group_list,
            msg="incorrect group list returned by Regex)",
        )

        expr = (
            Regex(r"\w+ (?P<num1>\d+) (?P<num2>\d+) (?P<last_word>\w+)").capture_groups()
        )
        result = expr.parse_string(test_str)

        self.assertEqual(
            result,
            {"num1": "123", "num2": "456", "last_word": "lsdfkj"},
            "invalid group dict from Regex(asMatch=True)",
        )
        self.assertEqual(
            result[0],
            expected_group_list[0],
            "incorrect group list returned by Regex(asMatch)",
        )

    def testRegexSub(self):

        expr = Regex(r"<title>").sub("'Richard III'")
        result = expr.transform_string("This is the title: <title>")

        self.assertEqual(
            result,
            "This is the title: 'Richard III'",
            "incorrect Regex.sub result with simple string",
        )

        expr = Regex(r"([Hh]\d):\s*([^\n]*)").sub(r"<\1>\2</\1>")
        result = expr.transform_string(
            "h1: This is the main heading\nh2: This is the sub-heading"
        )

        self.assertEqual(
            result,
            "<h1>This is the main heading</h1>\n<h2>This is the sub-heading</h2>",
            "incorrect Regex.sub result with re string",
        )

        expr = Regex(r"([Hh]\d):\s*([^\n]*)").sub(r"<\1>\2</\1>")
        result = expr.transform_string(
            "h1: This is the main heading\nh2: This is the sub-heading"
        )

        self.assertEqual(
            result,
            "<h1>This is the main heading</h1>\n<h2>This is the sub-heading</h2>",
            "incorrect Regex.sub result with re string",
        )

        expr = Regex(r"<((?:(?!>).)*)>").sub(lambda m: m.group(1).upper())
        result = expr.transform_string("I want this in upcase: <what? what?>")

        self.assertEqual(
            result,
            "I want this in upcase: WHAT? WHAT?",
            "incorrect Regex.sub result with callable",
        )

    def test_escaped_square_bracket(self):
        parser = Regex("[^\\]]")
        self.assertIsInstance(parser.expr, Char)
        self.assertEqual(parser.expr.parser_config.exclude, "]")
        sql_server_name = Regex("\\[(\\]\\]|[^\\]])*\\]")
        self.assertIsInstance(sql_server_name.expr.exprs[0], SingleCharLiteral)
        self.assertEqual(sql_server_name.expr.exprs[0].parser_config.match, "[")
        self.assertIsInstance(sql_server_name.expr.exprs[2], SingleCharLiteral)
        self.assertEqual(sql_server_name.expr.exprs[2].parser_config.match, "]")

    def test_parsing_perl(self):
        # from https://flapenguin.me/xml-regex
        # Perl regex
        #                      -----    -------------------------------------    -------  --------------------------
        # xml = Regex(r"""\s*(?(?=<)<\s*(\w+)(?:\s+[^\s>]+=("|'|)[^\s"'>]+\2)*\s*(\/\s*)?>(?(3)|(?R)<\s*\/\s*\1\s*>)|[^<]*)*\s*""")
        pass

    def test_make_complex_ident(self):
        IDENT_CHAR = Regex("[@_$0-9A-Za-zÀ-ÖØ-öø-ƿ]").expr.parser_config.include
        FIRST_IDENT_CHAR = "".join(set(IDENT_CHAR) - set("0123456789"))
        digit = Char("0123456789")
        with whitespaces.NO_WHITESPACE:
            simple_ident = (
                Char(FIRST_IDENT_CHAR)
                + (
                    (Regex("(?<=[^0-9])") + "-" + LookAhead(~digit)) | Char(IDENT_CHAR)
                )[...]
            )

        regex = simple_ident.__regex__()[1]

        self.assertEqual(
            regex,
            "[\\$@-Z_a-zÀ-ÖØ-öø-ƿ](?:(?:(?<=[^0-9]))\\-(?=(?![0-9]))|[\\$0-9@-Z_a-zÀ-ÖØ-öø-ƿ])*",
        )

        faster = Regex(regex)
        self.assertEqual(
            faster.parse("this-is-a-test", parse_all=True), "this-is-a-test"
        )

        try:
            result = faster.parse("thi2-is-a-test", parse_all=True)
            raise Exception("expecting parse error")
        except Exception:
            pass

    def test_comment(self):
        with Whitespace() as white:
            white.add_ignore(Literal("/*") + SkipTo("*/", include=True))
            parser = Keyword("select") + Keyword("true")
            parser = parser.finalize()

        result = parser.parse_string("/* \nfoo\n\n */\nselect true")

        self.assertEqual(list(result), ["select", "true"])

    def test_keyword(self):
        k = CaselessKeyword("test", ident_chars=Regex("[a-z]"))
        self.assertEqual(
            k.parser_config.ident_chars,
            "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz",
        )

        k = Keyword("test", ident_chars=Regex("[a-z]"))
        self.assertEqual(k.parser_config.ident_chars, "abcdefghijklmnopqrstuvwxyz")

    def test_regex_or(self):
        parser = re.compile(r"(a)|(b)")

        self.assertEqual(parser.match("a").group(1), "a")
        self.assertEqual(parser.match("a").group(2), None)
        self.assertEqual(parser.match("b").group(1), None)
        self.assertEqual(parser.match("b").group(2), "b")
        self.assertEqual(parser.match("c"), None)

    def test_optional_prefix_does_not_hide_alternative(self):
        # A LEADING `-?` MUST NOT HIDE THE DIGITS THAT CAN ALSO START THE MATCH
        number = Regex(r"-?\d+(?:\.\d+)?")
        self.assertEqual("".join(sorted(number.expecting().keys())), "-0123456789")

        # ENOUGH ALTERNATIVES THAT MatchFirst BUILDS ITS LOOKUP
        grammar = MatchFirst([
            Literal("!"),
            Literal("$"),
            Regex(r"[A-Za-z]+"),
            number,
        ]).streamline()
        self.assertEqual(grammar.parse_string("42"), "42")
        self.assertEqual(grammar.parse_string("-42"), "-42")
        self.assertEqual(grammar.parse_string("3.14"), "3.14")

    def test_repetition_binds_last_character(self):
        # `abc*` IS `ab` FOLLOWED BY `c*`, NOT `abc` REPEATED
        self.assertEqual("".join(Regex(r"abc*").expecting().keys()), "ab")
        self.assertEqual(Regex(r"abc*").min_length(), 2)
        self.assertEqual("".join(Regex(r"ab?c").expecting().keys()), "a")
        self.assertEqual(Regex(r"ab?c").min_length(), 2)
        self.assertEqual("".join(Regex(r"colou?r").expecting().keys()), "colo")
        self.assertEqual(Regex(r"colou?r").min_length(), 5)
        for pattern, text in [(r"abc*", "ab"), (r"ab?c", "ac"), (r"colou?r", "color")]:
            self.assertEqual(Regex(pattern).parse_string(text), text)
        self.assertEqual(
            "".join(sorted(Regex(r"-?\d+").expecting().keys())), "-0123456789"
        )
        self.assertEqual(Regex(r"-?\d+").min_length(), 1)
        self.assertEqual("".join(Regex(r"ab?").expecting().keys()), "a")
        self.assertEqual(Regex(r"ab?").min_length(), 1)

    def test_leading_question_mark_still_parses(self):
        # A BARE `?` IN LEAD POSITION IS TOLERATED, AS IN THE UNMODELLED `(?P=name)`
        Regex(r"(?P<name>a)(?P=name)")

    def test_question_mark_builds_optional(self):
        self.assertIsInstance(Regex(r"ab?").expr.exprs[1], Optional)

    def test_non_greedy_is_not_greedy(self):
        # THE TREE FOR A NON-GREEDY REPETITION MUST NOT CONSUME LIKE ITS GREEDY FORM
        self.assertEqual(Regex(r"ab*?").expr.parse_string("abbb").end, 1)
        self.assertEqual(Regex(r"ab+?").expr.parse_string("abbb").end, 2)

    def test_zero_width_constructs_min_length(self):
        # `(?#note)` AND `\Z` MATCH NO CHARACTERS
        self.assertEqual(Regex(r"ab(?#note)cd").min_length(), 4)
        self.assertEqual(Regex(r"a\Zb").min_length(), 2)

    def test_word_edge_is_a_word_boundary(self):
        # `\b` IS A ZERO-WIDTH WORD/NON-WORD TRANSITION
        tree = Regex(r"\bcat\b").expr
        self.assertEqual(
            [(s, e) for _, s, e in tree.scan_string("a cat sat")], [(2, 5)]
        )
        self.assertEqual([(s, e) for _, s, e in tree.scan_string("concatenate")], [])
        self.assertEqual(Regex(r"\bcat\b").min_length(), 3)

    def test_overestimated_min_length_does_not_hide_match(self):
        # ENOUGH ALTERNATIVES THAT MatchFirst BUILDS ITS LOOKUP
        grammar = MatchFirst([
            Literal("!"),
            Literal("$"),
            Regex(r"[0-9]+"),
            Regex(r"ab(?#note)cd"),
        ]).streamline()
        self.assertEqual(grammar.parse_string("abcd"), "abcd")

    def test_string_start_is_zero_width(self):
        # `\A` ANCHORS THE START, IT IS NOT A LITERAL "A"
        anchored = Regex(r"\Aab")
        self.assertEqual(anchored.min_length(), 2)
        self.assertEqual(anchored.expr.parse_string("ab"), "ab")
        with self.assertRaisesParseException():
            anchored.expr.parse_string("Aab")

    def test_quantified_pattern_groups_before_repeating(self):
        # A PATTERN CARRYING ITS OWN QUANTIFIER IS NOT ATOMIC
        for expr in [
            Optional(CharsNotIn("\n")),
            Optional(OneOrMore(Char(alphas))),
            Optional(ZeroOrMore(Char(alphas))),
            OneOrMore(Char(alphas)[1:5]),
        ]:
            regex_compile(expr.__regex__()[1])

    def test_ignorable_may_be_more_than_one_token(self):
        with Whitespace() as white:
            white.add_ignore(Literal("#") + Optional(CharsNotIn("\n")))
            parser = (Keyword("select") + Keyword("true")).finalize()
        self.assertEqual(
            list(parser.parse_string("# note\nselect true")), ["select", "true"]
        )
