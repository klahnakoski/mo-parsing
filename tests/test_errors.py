# encoding: utf-8

from mo_testing.fuzzytestcase import FuzzyTestCase

from mo_parsing import Word, Group, ParseException, Char, Log
from mo_parsing.infix import delimited_list, Regex


class TestErrors(FuzzyTestCase):
    def test_better_error(self):
        options = Group(Word("a") | Word("b")).set_parser_name("a or b")
        stream = delimited_list(options)
        content = "a, b, b, c"
        with self.assertRaises("Expecting a or b, found \"c\" (at char 9), (line:1, col:10)"):
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