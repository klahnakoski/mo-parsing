# testing.py

from contextlib import contextmanager
from unittest import TestCase

from mo_testing.fuzzytestcase import FuzzyTestCase

from mo_parsing import core
from mo_parsing.core import (
    ParserElement,
    ParseException,
    __diag__,
    DEFAULT_WHITE_CHARS,
    CURRENT_WHITE_CHARS,
    default_literal,
)
from mo_parsing.tokens import Keyword
from mo_parsing.utils import __compat__


class reset_parsing_context:
    """
    Context manager to be used when writing unit tests that modify mo_parsing config values:
     - packrat parsing
     - default whitespace characters.
     - default keyword characters
     - literal string auto-conversion class
     - __diag__ settings

    Example:
        with reset_parsing_context():
            # test that literals used to construct a grammar are automatically suppressed
            default_literal(Suppress)

            term = Word(alphas) | Word(nums)
            group = Group('(' + term[...] + ')')

            # assert that the '()' characters are not included in the parsed tokens
            self.assertParseAndCheckList(group, "(abc 123 def)", ['abc', '123', 'def'])

        # after exiting context manager, literals are converted to Literal expressions again
    """

    def __init__(self):
        self._save_context = {}

    def save(self):
        self._save_context["default_whitespace"] = DEFAULT_WHITE_CHARS
        self._save_context["default_keyword_chars"] = Keyword.DEFAULT_KEYWORD_CHARS
        self._save_context["literal_string_class"] = core.CURRENT_LITERAL
        self._save_context["packrat_parse"] = ParserElement._parse
        self._save_context["__diag__"] = {
            name: getattr(__diag__, name) for name in __diag__._all_names
        }
        self._save_context["__compat__"] = {
            "collect_all_And_tokens": __compat__.collect_all_And_tokens
        }
        return self

    def restore(self):
        # reset mo_parsing global state
        if CURRENT_WHITE_CHARS != self._save_context["default_whitespace"]:
            ParserElement.setDefaultWhitespaceChars(
                self._save_context["default_whitespace"]
            )
        Keyword.DEFAULT_KEYWORD_CHARS = self._save_context["default_keyword_chars"]
        default_literal(self._save_context["literal_string_class"])
        for name, value in self._save_context["__diag__"].items():
            (__diag__.enable if value else __diag__.disable)(name)
        ParserElement._parse = self._save_context["packrat_parse"]
        __compat__.collect_all_And_tokens = self._save_context["__compat__"]

    def __enter__(self):
        return self.save()

    def __exit__(self, *args):
        return self.restore()


class TestParseResultsAsserts(FuzzyTestCase):
    """
    A mixin class to add parse results assertion methods to normal unittest.TestCase classes.
    """

    def assertParseResultsEquals(
        self, result, expected_list=None, expected_dict=None, msg=None
    ):
        """
        Unit test assertion to compare a ParseResults object with an optional expected_list,
        and compare any defined results names with an optional expected_dict.
        """
        self.assertEqual(result, expected_list, msg=msg)
        self.assertEqual(result, expected_dict, msg=msg)

    def assertParseAndCheckList(
        self, expr, test_string, expected_list, msg=None, verbose=True
    ):
        """
        Convenience wrapper assert to test a parser element and input string, and assert that
        the resulting ParseResults is equal to the expected_list.
        """
        result = expr.parseString(test_string, parseAll=True)
        if verbose:

        self.assertParseResultsEquals(result, expected_list=expected_list, msg=msg)

    def assertParseAndCheckDict(
        self, expr, test_string, expected_dict, msg=None, verbose=True
    ):
        """
        Convenience wrapper assert to test a parser element and input string, and assert that
        the resulting ParseResults is equal to the expected_dict.
        """
        result = expr.parseString(test_string, parseAll=True)
        if verbose:

        self.assertParseResultsEquals(result, expected_dict=expected_dict, msg=msg)

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
                    with TestCase.assertRaises(self,
                        expected_exception=expected_exception, msg=fail_msg or msg
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
                    else:
                        # warning here maybe?


        # do this last, in case some specific test results can be reported instead
        self.assertTrue(
            run_test_success, msg=msg if msg is not None else "failed runTests"
        )

    @contextmanager
    def assertRaisesParseException(self, exc_type=ParseException, msg=None):
        with TestCase.assertRaises(self, exc_type, msg=msg):
            yield
