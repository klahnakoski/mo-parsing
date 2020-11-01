# encoding: utf-8
from mo_future import text
from mo_parsing.utils import Log

from mo_parsing.core import replaceWith, ParserElement
from mo_parsing.exceptions import ParseException
from mo_parsing.results import ParseResults
from mo_parsing.tokens import Literal


def runTests(
    self,
    tests,
    parseAll=True,
    comment="#",
    fullDump=True,
    printResults=True,
    failureTests=False,
    postParse=None,
    file=None,
):
    """
    Execute the parse expression on a series of test strings, showing each
    test, the parsed results or where the parse failed. Quick and easy way to
    run a parse expression against a list of sample strings.

    Parameters:
     - tests - a list of separate test strings, or a multiline string of test strings
     - parseAll - (default= ``True``) - flag to pass to `parseString` when running tests
     - comment - (default= ``'#'``) - expression for indicating embedded comments in the test
          string; pass None to disable comment filtering
     - fullDump - (default= ``True``) - dump results as list followed by results names in nested outline;
          if False, only dump nested list
     - printResults - (default= ``True``) prints test output to stdout
     - failureTests - (default= ``False``) indicates if these tests are expected to fail parsing
     - postParse - (default= ``None``) optional callback for successful parse results; called as
          `fn(test_string, parse_results)` and returns a string to be added to the test output
     - file - (default=``None``) optional file-like object to which test output will be written;
          if None, will default to ``sys.stdout``

    Returns: a (success, results) tuple, where success indicates that all tests succeeded
    (or failed if ``failureTests`` is True), and the results contain a list of lines of each
    test's output

    Example::

        number_expr = number.copy()

        result = test.runTests(number_expr, '''
            # unsigned integer
            100
            # negative integer
            -100
            # float with scientific notation
            6.02e23
            # integer with scientific notation
            1e-12
            ''')


        result = test.runTests(number_expr, '''
            # stray character
            100Z
            # missing leading digit before '.'
            -.100
            # too many '.'
            3.14.159
            ''', failureTests=True)


    prints::

        # unsigned integer
        100
        [100]

        # negative integer
        -100
        [-100]

        # float with scientific notation
        6.02e23
        [6.02e+23]

        # integer with scientific notation
        1e-12
        [1e-12]

        Success

        # stray character
        100Z
           ^
        FAIL: Expected end of text (at char 3), (line:1, col:4)

        # missing leading digit before '.'
        -.100
        ^
        FAIL: Expected {real number with scientific notation | real number | signed integer} (at char 0), (line:1, col:1)

        # too many '.'
        3.14.159
            ^
        FAIL: Expected end of text (at char 4), (line:1, col:5)

        Success

    Each test string must be on a single line. If you want to test a string that spans multiple
    lines, create a test like this::

        expr.runTest(r"this is a test\\n of strings that spans \\n 3 lines")

    (Note that this is a raw string literal, you must include the leading 'r'.)
    """
    error = Log.error
    if isinstance(tests, text):
        tests = [tt for t in tests.rstrip().splitlines() for tt in [t.strip()] if tt]
    if isinstance(comment, text):
        comment = Literal(comment)

    allResults = []
    NL = Literal(r"\n").addParseAction(replaceWith("\n"))
    BOM = u"\ufeff"
    for i, (t, failureTest) in enumerate(zip(tests, [failureTests]*len(tests) if not isinstance(failureTests, list) else failureTests)):
        if comment is not None and comment.matches(t, False):
            Log.note(t)
            continue
        if not t:
            continue
        try:
            # convert newline marks to actual newlines, and strip leading BOM if present
            t = NL.transformString(t.lstrip(BOM))
            result = self.parseString(t, parseAll=parseAll)
        except ParseException as pe:
            if not failureTest:
                error("FAIL", cause=pe)

            result = pe
        except Exception as exc:
            if not failureTest:
                error("FAIL-EXCEPTION", cause=exc)
            result = exc
        else:
            if failureTest:
                error("EXPECTING FAIL")

            if postParse:
                try:
                    pp_value = postParse(t, result)
                    if pp_value is not None:
                        if isinstance(pp_value, ParseResults):
                            Log.note(pp_value)
                        else:
                            Log.note(str(pp_value))
                    else:
                        Log.note("{{result}}", result=result)
                except Exception as cause:
                    Log.warning("postParse {{name}} failed", name=postParse.__name__, cause=cause)
            else:
                Log.note("{{result}}", result=result)

        allResults.append((t, result))

    return True, allResults


ParserElement.runTests = runTests
