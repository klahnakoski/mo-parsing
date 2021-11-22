# encoding: utf-8
import re

from mo_parsing import Regex, Char, LookAhead
from mo_parsing.tokens import SingleCharLiteral, LookBehind
from tests.test_simple_unit import PyparsingExpressionTestCase


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
        digit = Char('0123456789')
        simple_ident = Char(FIRST_IDENT_CHAR) + ((Regex("(?<=[^0-9])") + "-" + LookAhead(~digit)) | Char(IDENT_CHAR))[...]

        regex = simple_ident.__regex__()[1]

        self.assertEqual(regex, '[\\$@-Z_a-zÀ-ÖØ-öø-ƿ](?:(?:(?<=[^0-9]))\\-(?=(?![0-9]))|[\\$0-9@-Z_a-zÀ-ÖØ-öø-ƿ])*')

        faster = Regex(regex)
        self.assertEqual(
            faster.parse("this-is-a-test", parse_all=True),
            "this-is-a-test"
        )

        try:
            result = faster.parse("thi2-is-a-test", parse_all=True)
            raise Exception("expecting parse error")
        except Exception:
            pass
