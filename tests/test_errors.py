# encoding: utf-8

from mo_testing.fuzzytestcase import FuzzyTestCase

from mo_parsing import Word, Group
from mo_parsing.infix import delimited_list


class TestErrors(FuzzyTestCase):
    def test_better_error(self):
        options = Group(Word("a") | Word("b")).set_parser_name("a or b")
        stream = delimited_list(options)
        content = "a, b, b, c"
        with self.assertRaises("Expecting a or b, found \"c\" (at char 9), (line:1, col:10)"):
            stream.parse(content, parse_all=True)