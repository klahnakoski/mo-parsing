# testing.py

from contextlib import contextmanager
from unittest import TestCase

from mo_parsing.core import (
    ParseException,
)
from mo_testing.fuzzytestcase import FuzzyTestCase


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

        # do this last, in case some specific test results can be reported instead
        self.assertTrue(
            run_test_success, msg=msg if msg is not None else "failed runTests"
        )

    @contextmanager
    def assertRaisesParseException(self, exc_type=ParseException, msg=None):
        with TestCase.assertRaises(self, exc_type, msg=msg):
            yield
