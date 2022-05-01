# encoding: utf-8
import ast
import sys

from mo_dots import literal_field
from mo_testing.fuzzytestcase import FuzzyTestCase

from mo_parsing import *
from mo_parsing.helpers import quoted_string


class TestErrors(FuzzyTestCase):
    def test_better_error(self):
        options = Group(Word("a") | Word("b")).set_parser_name("a or b")
        stream = delimited_list(options)
        content = "a, b, b, c"
        with self.assertRaises(
            'Expecting a or b, found "c" (at char 9), (line:1, col:10)'
        ):
            stream.parse(content, parse_all=True)

    def test_message_is_priority(self):
        def no_dashes(tokens, start, string):
            if "-" in tokens[0]:
                index = tokens[0].find("-")
                raise ParseException(
                    tokens.type,
                    start + index,
                    string,
                    """Ambiguity: Use backticks (``) around identifiers with dashes, or add space around subtraction operator.""",
                )

        IDENT_CHAR = Regex("[@_$0-9A-Za-zÀ-ÖØ-öø-ƿ]").expr.parser_config.include
        FIRST_IDENT_CHAR = "".join(set(IDENT_CHAR) - set("0123456789"))
        simple_ident = (
            Char(FIRST_IDENT_CHAR)
            + (Regex("(?<=[^ 0-9])\\-(?=[^ 0-9])") | Char(IDENT_CHAR))[...]
        )
        simple_ident = Regex(simple_ident.__regex__()[1]) / no_dashes

        try:
            simple_ident.parse("coverage-summary.source.file.covered")
            self.assertTrue(False)
        except Exception as cause:
            self.assertIn("Use backticks (``) around identifiers", cause.message)

    def test_report_after_as(self):
        ansi_ident = (Word(Regex("[a-z]")) | "123").set_parser_name("identifier")
        columns = delimited_list(quoted_string + Optional("AS" + ansi_ident))
        simple = "SELECT" + columns
        with self.assertRaises("Expecting identifier, found \"'T'"):
            simple.parse("SELECT 'b' AS b, 'a' AS 'T'", parse_all=True)

    def test_combine_error(self):
        ansi_ident = Combine(Word(Regex("[a-z]")) | "123").set_parser_name("combine")
        columns = delimited_list(quoted_string + Optional("AS" + ansi_ident))
        with self.assertRaises("Expecting combine, found \"'T'"):
            columns.parse("'b' AS b, 'a' AS 'T'", parse_all=True)


def double_column(tokens):
    global emit_warning_for_double_quotes
    if emit_warning_for_double_quotes:
        emit_warning_for_double_quotes = False
        sys.stderr.write(
            """Double quotes are used to quote column names, not literal strings.  To hide this message: mo_sql_parsing.utils.emit_warning_for_double_quotes = False"""
        )

    val = tokens[0]
    val = '"' + val[1:-1].replace('""', '\\"') + '"'
    un = literal_field(ast.literal_eval(val))
    return un