#
# test_examples.py
#
import unittest
from importlib import import_module

from mo_files import File
from mo_times import Timer

from mo_parsing.engine import Engine

skip_list = [
    "SimpleCalc",
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
    "dictExample2",
    "ebnftest",
    "eval_arith",
    "excelExpr",
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
    "wordsToNum"
]

modules = [f.name for f in File("examples").children]


class TestAllExamples(unittest.TestCase):
    pass


def _single_test(name):
    def output(self):
        with Engine():
            import_module("examples." + name)

    return output

with Timer("bigquery view parsing"):
    for f in File("examples").children:
        if f.extension == "py":
            func = _single_test(f.name)
            if f.name in skip_list:
                func = unittest.skip("requires fix")(func)
            setattr(TestAllExamples, "test_" + f.name, func)
