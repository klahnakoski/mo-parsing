#
# test_examples.py
#
import unittest
from importlib import import_module

from mo_files import File

from mo_parsing.helpers import *

skip_list = [
    "TAP",
    "adventureEngine",
    "antlr_grammar",
    "booleansearchparser",
    "cLibHeader",
    "cpp_enum_parser",
    "datetimeParseActions",
    "decaf_parser",
    "delta_time",
    "dhcpd_leases_parser",
    "dictExample",
    "dictExample2",
    "ebnftest",
    "eval_arith",
    "gen_ctypes",
    "getNTPserversNew",
    "htmlTableParser",
    "htmlStripper",  # TAKES TOO LONG
    "invRegex",
    "jsonParser_test",
    "list1",
    "listAllMatches",
    "matchPreviousDemo",
    "mozillaCalendarParser",
    "oc",
    "parsePythonValue",
    "partial_gene_match",
    "pgn",
    "protobuf_parser",
    "pymicko",
    "pythonGrammarParser",
    "rangeCheck",
    "readJson",
    "removeLineBreaks",
    "rosettacode",
    "scanExamples",
    "searchParserAppDemo",
    "searchparser",
    "sexpParser",
    "simpleArith",
    "simpleSQL_test",
    "urlExtractor",
    "urlExtractorNew",
    "verilogParse",
    "verilogParse_test",
    "withAttribute",
    "wordsToNum",
    "LAparser_test",
]

modules = [f.name for f in File("examples").children]


class TestAllExamples(unittest.TestCase):
    pass


def _single_test(name):
    def output(self):
        with Engine():
            import_module("examples." + name)

    return output


for f in File("examples").children:
    if f.extension == "py":
        func = _single_test(f.name)
        if f.name in skip_list:
            func = unittest.skip("please fix " + f.name)(func)
        setattr(TestAllExamples, "test_" + f.name, func)
