#
# simple_unit_tests.py
#
# While these unit tests *do* perform low-level unit testing of the classes in mo_parsing,
# this testing module should also serve an instructional purpose, to clearly show simple passing
# and failing parse cases of some basic mo_parsing expressions.
#
# Copyright (c) 2018  Paul T. McGuire
#
from __future__ import division

from contextlib import contextmanager
from unittest import TestCase

from mo_testing.fuzzytestcase import FuzzyTestCase

from mo_parsing import *
from mo_parsing.debug import Debugger
from mo_parsing.helpers import *
from mo_parsing.infix import oneOf
from mo_parsing.utils import *

TestSpecification = namedtuple(
    "PpTestSpec",
    "desc expr text parse_fn expected_list expected_dict expected_fail_locn",
)


class PyparsingExpressionTestCase(FuzzyTestCase):

    """
    A mixin class to add parse results assertion methods to normal unittest.TestCase classes.
    """

    def setUp(self):
        self.whitespace = Whitespace().use()

    def tearDown(self):
        self.whitespace.release()

    def assertParseResultsEquals(
        self, result, expected_list=None, expected_dict=None, msg=None
    ):
        """
        Unit test assertion to compare a ParseResults object with an optional expected_list,
        and compare any defined results names with an optional expected_dict.
        """
        self.assertEqual(result, expected_list, msg=msg)
        self.assertEqual(result, expected_dict, msg=msg)

    def assertRunTestResults(
        self, run_tests_report, expected_parse_results=None, msg=None
    ):
        """
        Unit test assertion to evaluate output of ParserElement.runTests(). If a list of
        list-dict tuples is given as the expected_parse_results argument, then these are zipped
        with the report tuples returned by runTests and evaluated using assertParseResultsEquals.
        Finally, asserts that the overall runTests() success value is True.

        :param run_tests_report: tuple(bool, [tuple(str, ParseResults or Exception)]) returned from runTests
        :param expected_parse_results (optional): [tuple(str, list, dict, Exception)]
        """
        run_test_success, run_test_results = run_tests_report

        if expected_parse_results is not None:
            merged = [
                (*rpt, expected)
                for rpt, expected in zip(run_test_results, expected_parse_results)
            ]
            for test_string, result, expected in merged:
                # expected should be a tuple containing a list and/or a dict or an exception,
                # and optional failure message string
                # an empty tuple will skip any result validation
                fail_msg = next((exp for exp in expected if isinstance(exp, str)), None)
                expected_exception = next(
                    (
                        exp
                        for exp in expected
                        if isinstance(exp, type) and issubclass(exp, Exception)
                    ),
                    None,
                )
                if expected_exception is not None:
                    with TestCase.assertRaises(
                        self, expected_exception=expected_exception, msg=fail_msg or msg
                    ):
                        if isinstance(result, Exception):
                            raise result
                else:
                    expected_list = next(
                        (exp for exp in expected if isinstance(exp, list)), None
                    )
                    expected_dict = next(
                        (exp for exp in expected if isinstance(exp, dict)), None
                    )
                    if (expected_list, expected_dict) != (None, None):
                        self.assertParseResultsEquals(
                            result,
                            expected_list=expected_list,
                            expected_dict=expected_dict,
                            msg=fail_msg or msg,
                        )

        # do this last, in case some specific test results can be reported instead
        self.assertTrue(
            run_test_success, msg=msg if msg is not None else "failed runTests"
        )

    @contextmanager
    def assertRaisesParseException(self, exc_type=ParseException, msg=None):
        with TestCase.assertRaises(self, exc_type, msg=msg):
            yield

    def runTest(
        self,
        desc="",
        expr=Empty(),
        text="",
        parse_fn="parseString",
        expected_list=None,
        expected_dict=None,
        expected_fail_locn=None,
    ):
        # for each spec in the class's tests list, create a subtest
        # that will either:
        #  - parse the string with expected success, display the
        #    results, and validate the returned ParseResults
        #  - or parse the string with expected failure, display the
        #    error message and mark the error location, and validate
        #    the location against an expected value
        expr = expr.streamline()

        parsefn = getattr(expr, parse_fn)
        if expected_fail_locn is None:
            # expect success
            result = parsefn(text)
            if parse_fn == "parseString":
                self.assertEqual(result, expected_list)
                self.assertEqual(result, expected_dict)
            elif parse_fn == "transformString":
                self.assertEqual([result], expected_list)
            elif parse_fn == "searchString":
                self.assertEqual([result], expected_list)
        else:
            # expect fail
            try:
                parsefn(text)
            except Exception as exc:
                self.assertEqual(exc.loc, expected_fail_locn)
            else:
                self.assertTrue(False, "failed to raise expected exception")


# =========== TEST DEFINITIONS START HERE ==============


class TestLiteral(PyparsingExpressionTestCase):
    def test_simple_match(self):
        self.runTest(
            desc="Simple match", expr=Literal("xyz"), text="xyz", expected_list=["xyz"],
        )

    def test_simple_match_after_skipping_whitespace(self):
        self.runTest(
            desc="Simple match after skipping whitespace",
            expr=Literal("xyz"),
            text="  xyz",
            expected_list=["xyz"],
        )

    def test_simple_fail_parse_an_empty_string(self):
        self.runTest(
            desc="Simple fail - parse an empty string",
            expr=Literal("xyz"),
            text="",
            expected_fail_locn=0,
        )

    def test_Simple_fail___parse_a_mismatching_string(self):
        self.runTest(
            desc="Simple fail - parse a mismatching string",
            expr=Literal("xyz"),
            text="xyu",
            expected_fail_locn=0,
        )

    def test_simple_fail_parse_a_partially_matching_string(self):
        self.runTest(
            desc="Simple fail - parse a partially matching string",
            expr=Literal("xyz"),
            text="xy",
            expected_fail_locn=0,
        )

    def test_fail_parse_a_partially_matching_string_by_matching_individual_letters(
        self,
    ):
        self.runTest(
            desc=(
                "Fail - parse a partially matching string by matching individual"
                " letters"
            ),
            expr=Literal("x") + Literal("y") + Literal("z"),
            text="xy",
            expected_fail_locn=2,
        )


class TestCaselessLiteral(PyparsingExpressionTestCase):
    def test_Match_colors_converting_to_consistent_case(self):
        self.runTest(
            desc="Match colors, converting to consistent case",
            expr=(
                CaselessLiteral("RED")
                | CaselessLiteral("GREEN")
                | CaselessLiteral("BLUE")
            )[...],
            text="red Green BluE blue GREEN green rEd",
            expected_list=["RED", "GREEN", "BLUE", "BLUE", "GREEN", "GREEN", "RED"],
        )


class TestWord(PyparsingExpressionTestCase):
    def test_Simple_Word_match(self):
        self.runTest(
            desc="Simple Word match",
            expr=Word("xy"),
            text="xxyxxyy",
            expected_list=["xxyxxyy"],
        )

    def test_Simple_Word_match_of_two_separate_Words(self):
        self.runTest(
            desc="Simple Word match of two separate Words",
            expr=Word("x") + Word("y"),
            text="xxxxxyy",
            expected_list=["xxxxx", "yy"],
        )

    def test_Simple_Word_match_of_two_separate_Words___implicitly_skips_whitespace(
        self,
    ):
        self.runTest(
            desc=(
                "Simple Word match of two separate Words - implicitly skips whitespace"
            ),
            expr=Word("x") + Word("y"),
            text="xxxxx yy",
            expected_list=["xxxxx", "yy"],
        )


class TestCombine(PyparsingExpressionTestCase):
    def test_1(self):
        self.runTest(
            desc="Parsing real numbers - fail, parsed numbers are in pieces",
            expr=(Word(nums) + "." + Word(nums))[...],
            text="1.2 2.3 3.1416 98.6",
            expected_list=[
                "1",
                ".",
                "2",
                "2",
                ".",
                "3",
                "3",
                ".",
                "1416",
                "98",
                ".",
                "6",
            ],
        )

    def test_2(self):
        self.runTest(
            desc=(
                "Parsing real numbers - better, use Combine to combine multiple tokens"
                " into one"
            ),
            expr=Combine(Word(nums) + "." + Word(nums))[...],
            text="1.2 2.3 3.1416 98.6",
            expected_list=["1.2", "2.3", "3.1416", "98.6"],
        )


class TestRepetition(PyparsingExpressionTestCase):
    def test_Match_several_words(self):
        self.runTest(
            desc="Match several words",
            expr=(Word("x") | Word("y"))[...],
            text="xxyxxyyxxyxyxxxy",
            expected_list=["xx", "y", "xx", "yy", "xx", "y", "x", "y", "xxx", "y"],
        )

    def test_Match_several_words_skipping_whitespace(self):
        self.runTest(
            desc="Match several words, skipping whitespace",
            expr=(Word("x") | Word("y"))[...],
            text="x x  y xxy yxx y xyx  xxy",
            expected_list=[
                "x",
                "x",
                "y",
                "xx",
                "y",
                "y",
                "xx",
                "y",
                "x",
                "y",
                "x",
                "xx",
                "y",
            ],
        )

    def test_Match_several_words_skipping_whitespace_old_style(self):
        self.runTest(
            desc="Match several words, skipping whitespace (old style)",
            expr=OneOrMore(Word("x") | Word("y")),
            text="x x  y xxy yxx y xyx  xxy",
            expected_list=[
                "x",
                "x",
                "y",
                "xx",
                "y",
                "y",
                "xx",
                "y",
                "x",
                "y",
                "x",
                "xx",
                "y",
            ],
        )

    def test_many_with_stopper(self):
        expr = Many("x", stopOn="y").streamline()
        result = expr.parseString("xxxxy")
        expecting = "xxxx"
        self.assertEqual(result, expecting)

    def test_Match_words_and_numbers___show_use_of_results_names_to_collect_types_of_tokens(
        self,
    ):
        self.runTest(
            desc=(
                "Match words and numbers - show use of results names to collect types"
                " of tokens"
            ),
            expr=(Word(alphas)("alpha") | integer("int"))[...],
            text="sdlfj23084ksdfs08234kjsdlfkjd0934",
            expected_list=["sdlfj", 23084, "ksdfs", 8234, "kjsdlfkjd", 934],
            expected_dict={
                "alpha": ["sdlfj", "ksdfs", "kjsdlfkjd"],
                "int": [23084, 8234, 934],
            },
        )

    def test_Using_delimitedList_comma_is_the_default_delimiter(self):
        self.runTest(
            desc="Using delimitedList (comma is the default delimiter)",
            expr=delimitedList(Word(alphas)),
            text="xxyx,xy,y,xxyx,yxx, xy",
            expected_list=["xxyx", "xy", "y", "xxyx", "yxx", "xy"],
        )

    def test_Using_delimitedList_with_colon_delimiter(self):
        self.runTest(
            desc="Using delimitedList, with ':' delimiter",
            expr=delimitedList(Word(hexnums, exact=2), separator=":", combine=True),
            text="0A:4B:73:21:FE:76",
            expected_list=["0A:4B:73:21:FE:76"],
        )


class TestResultsName(PyparsingExpressionTestCase):
    def test_Match_with_results_name(self):
        self.runTest(
            desc="Match with results name",
            expr=Group(Literal("xyz").set_token_name("value")),
            text="xyz",
            expected_dict={"value": "xyz"},
            expected_list=["xyz"],
        )

    def test_Match_with_results_name___using_naming_short_cut(self):
        self.runTest(
            desc="Match with results name - using naming short-cut",
            expr=Group(Literal("xyz")("value")),
            text="xyz",
            expected_dict={"value": "xyz"},
            expected_list=["xyz"],
        )

    def test_Define_multiple_results_names(self):
        self.runTest(
            desc="Define multiple results names",
            expr=Group(Word(alphas, alphanums)("key") + "=" + integer("value")),
            text="range=5280",
            expected_dict={"key": "range", "value": 5280},
            expected_list=["range", "=", 5280],
        )


class TestGroups(PyparsingExpressionTestCase):
    EQ = Suppress("=")

    def test_Define_multiple_results_names_in_groups(self):
        self.runTest(
            desc="Define multiple results names in groups",
            expr=Group(Word(alphas)("key") + self.EQ + number("value"))[...],
            text="range=5280 long=-138.52 lat=46.91",
            expected_list=[["range", 5280], ["long", -138.52], ["lat", 46.91]],
        )

    def test_Define_multiple_results_names_in_groups___use_Dict_to_define_results_names_using_parsed_keys(
        self,
    ):
        self.runTest(
            desc=(
                "Define multiple results names in groups - use Dict to define results"
                " names using parsed keys"
            ),
            expr=Dict(Group(Word(alphas) + self.EQ + number)[...]),
            text="range=5280 long=-138.52 lat=46.91",
            expected_list=[["range", 5280], ["long", -138.52], ["lat", 46.91]],
            expected_dict={"lat": 46.91, "long": -138.52, "range": 5280},
        )

    def test_define_multiple_value_types(self):
        expr = Dict(Group(
            Word(alphas) + self.EQ + (number | oneOf("True False") | QuotedString("'"))
        )[...])
        text = "long=-122.47 lat=37.82 public=True name='Golden Gate Bridge'"
        self.runTest(
            desc="Define multiple value types",
            expr=expr,
            text=text,
            expected_list=[
                ["long", -122.47],
                ["lat", 37.82],
                ["public", "True"],
                ["name", "Golden Gate Bridge"],
            ],
            expected_dict={
                "long": -122.47,
                "lat": 37.82,
                "public": "True",
                "name": "Golden Gate Bridge",
            },
        )


class TestParseAction(PyparsingExpressionTestCase):
    def test_(self):
        self.runTest(
            desc=(
                "Parsing real numbers - use parse action to convert to float at parse"
                " time"
            ),
            expr=Combine(
                Word(nums) + "." + Word(nums)
            ).addParseAction(lambda t: float(t[0]))[...],
            text="1.2 2.3 3.1416 98.6",
            expected_list=[
                1.2,
                2.3,
                3.1416,
                98.6,
            ],  # note, these are now floats, not strs
        )

    def test_Match_with_numeric_string_converted_to_int(self):
        self.runTest(
            desc="Match with numeric string converted to int",
            expr=Word("0123456789").addParseAction(lambda t: int(t[0])),
            text="12345",
            expected_list=[12345],  # note - result is type int, not str
        )

    def test_Use_two_parse_actions_to_convert_numeric_string_then_convert_to_datetime(
        self,
    ):
        self.runTest(
            desc=(
                "Use two parse actions to convert numeric string, then convert to"
                " datetime"
            ),
            expr=Word(nums).addParseAction(
                lambda t: int(t[0]), lambda t: datetime.utcfromtimestamp(t[0])
            ),
            text="1537415628",
            expected_list=[datetime(2018, 9, 20, 3, 53, 48)],
        )

    def test_Use_tokenMap_for_parse_actions_that_operate_on_a_single_length_token(self):
        self.runTest(
            desc="Use tokenMap for parse actions that operate on a single-length token",
            expr=Word(nums).addParseAction(
                tokenMap(int), tokenMap(datetime.utcfromtimestamp)
            ),
            text="1537415628",
            expected_list=[datetime(2018, 9, 20, 3, 53, 48)],
        )

    def test_Using_a_built_in_function_that_takes_a_sequence_of_strs_as_a_parse_action1(
        self,
    ):
        self.runTest(
            desc=(
                "Using a built-in function that takes a sequence of strs as a parse"
                " action"
            ),
            expr=Word(hexnums, exact=2)[...].addParseAction(":".join),
            text="0A4B7321FE76",
            expected_list=["0A:4B:73:21:FE:76"],
        )

    def test_Using_a_built_in_function_that_takes_a_sequence_of_strs_as_a_parse_action2(
        self,
    ):
        self.runTest(
            desc=(
                "Using a built-in function that takes a sequence of strs as a parse"
                " action"
            ),
            expr=Word(hexnums, exact=2)[...].addParseAction(sorted),
            text="0A4B7321FE76",
            expected_list=["0A", "21", "4B", "73", "76", "FE"],
        )


class TestResultsModifyingParseAction(PyparsingExpressionTestCase):
    @staticmethod
    def compute_stats_parse_action(t):
        # by the time this parse action is called, parsed numeric words
        # have been converted to ints by a previous parse action, so
        # they can be treated as ints
        t["sum"] = sum(t)
        t["ave"] = sum(t) / t.length()
        t["min"] = min(t)
        t["max"] = max(t)
        return t

    def test_A_parse_action_that_adds_new_key_values(self):
        self.runTest(
            desc="A parse action that adds new key-values",
            expr=integer[...].addParseAction(self.compute_stats_parse_action),
            text="27 1 14 22 89",
            expected_list=[27, 1, 14, 22, 89],
            expected_dict={"ave": 30.6, "max": 89, "min": 1, "sum": 153},
        )


class TestParseCondition(PyparsingExpressionTestCase):
    def test_Define_a_condition_to_only_match_numeric_values_that_are_multiples_of_7(
        self,
    ):
        self.runTest(
            desc=(
                "Define a condition to only match numeric values that are multiples"
                " of 7"
            ),
            expr=Word(nums).addCondition(
                lambda t: int(t[0]) % 7 == 0, message="expecting divisible by 7"
            )[...],
            text="14 35 77 12 28",
            expected_list=["14", "35", "77"],
        )

    def test_Separate_conversion_to_int_and_condition_into_separate_parse_action_conditions(
        self,
    ):
        self.runTest(
            desc=(
                "Separate conversion to int and condition into separate parse"
                " action/conditions"
            ),
            expr=Word(nums)
            .addParseAction(lambda t: int(t[0]))
            .addCondition(lambda t: t[0] % 7 == 0)[...],
            text="14 35 77 12 28",
            expected_list=[14, 35, 77],
        )


class TestTransformStringUsingParseActions(PyparsingExpressionTestCase):
    markup_convert_map = {"*": "B", "_": "U", "/": "I"}

    def markup_convert(self, t):
        htmltag = self.markup_convert_map[t["markup_symbol"]]
        return "<{0}>{1}</{2}>".format(htmltag, t["body"], htmltag)

    def test_Use_transformString_to_convert_simple_markup_to_HTML(self):
        self.runTest(
            desc="Use transformString to convert simple markup to HTML",
            expr=(
                oneOf(self.markup_convert_map)("markup_symbol")
                + "("
                + CharsNotIn(")")("body")
                + ")"
            ).addParseAction(self.markup_convert),
            text="Show in *(bold), _(underscore), or /(italic) type",
            expected_list=[
                "Show in <B>bold</B>, <U>underscore</U>, or <I>italic</I> type"
            ],
            parse_fn="transformString",
        )


class TestCommonHelperExpressions(PyparsingExpressionTestCase):
    def test_A_comma_delimited_list_of_words(self):
        self.runTest(
            desc="A comma-delimited list of words",
            expr=delimitedList(Word(alphas)),
            text="this, that, blah,foo,   bar",
            expected_list=["this", "that", "blah", "foo", "bar"],
        )

    def test_A_counted_array_of_words(self):
        self.runTest(
            desc="A counted array of words",
            expr=countedArray(Word("ab"))[...],
            text="2 aaa bbb 0 3 abab bbaa abbab",
            expected_list=[["aaa", "bbb"], [], ["abab", "bbaa", "abbab"]],
        )

    def test_skipping_comments_with_ignore(self):
        whitespaces.CURRENT.add_ignore(cppStyleComment)
        self.runTest(
            desc="skipping comments with ignore",
            expr=identifier("lhs") + "=" + fnumber("rhs"),
            text="abc_100 = /* value to be tested */ 3.1416",
            expected_list=["abc_100", "=", 3.1416],
            expected_dict={"lhs": "abc_100", "rhs": 3.1416},
        )

    def test_some_pre_defined_expressions_in_parsing_common_and_building_a_dotted_identifier_with_delimted_list(
        self,
    ):
        self.runTest(
            desc=(
                "some pre-defined expressions in parsing_common, and building a dotted"
                " identifier with delimted_list"
            ),
            expr=(
                number("id_num")
                + delimitedList(identifier, ".", combine=True)("name")
                + ipv4_address("ip_address")
            ),
            #     0123456789012345678901234567890123456789
            text="1001 www.google.com 192.168.10.199",
            expected_list=[1001, "www.google.com", "192.168.10.199"],
            expected_dict={
                "id_num": 1001,
                "name": "www.google.com",
                "ip_address": "192.168.10.199",
            },
        )

    def test_using_oneOf_shortcut_for_a_b_c(self):
        self.runTest(
            desc=(
                "using oneOf (shortcut for Literal('a') | Literal('b') | Literal('c'))"
            ),
            expr=oneOf("a b c")[...],
            text="a b a b b a c c a b b",
            expected_list=["a", "b", "a", "b", "b", "a", "c", "c", "a", "b", "b"],
        )

    def test_parsing_nested_parentheses(self):
        self.runTest(
            desc="parsing nested parentheses",
            expr=nestedExpr(),
            text="(a b (c) d (e f g ()))",
            expected_list=["a", "b", ["c"], "d", ["e", "f", "g", []]],
        )

    def test_parsing_nested_braces(self):
        self.runTest(
            desc="parsing nested braces",
            expr=Keyword("if")
            + nestedExpr()("condition")
            + nestedExpr("{", "}")("body"),
            text='if ((x == y) || !z) {printf("{}");}',
            expected_list=[
                "if",
                [["x", "==", "y"], "||", "!z"],
                ["printf(", '"{}"', ");"],
            ],
            expected_dict={
                "condition": [["x", "==", "y"], "||", "!z"],
                "body": ["printf(", '"{}"', ");"],
            },
        )


def _get_decl_line_no(cls):
    import inspect

    return inspect.getsourcelines(cls)[1]
