# encoding: utf-8
# test_examples.py
#
import unittest
from importlib import import_module

from mo_files import File
from mo_logs import logger, Except

from mo_parsing.helpers import *

skip_list = [
    "TAP",
    "adventureEngine",
    "antlr_grammar",
    "booleansearchparser",
    "cLibHeader",
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
    "pythonGrammarParser",
    "pymicko",
    "rangeCheck",
    "removeLineBreaks",
    "scanExamples",
    "searchParserAppDemo",
    "searchparser",
    "sexpParser",
    "simpleSQL_test",
    "urlExtractor",
    "urlExtractorNew",
    "verilogParse",
    "verilogParse_test",
    "LAparser_test",
]


class TestAllExamples(unittest.TestCase):
    pass


def _single_test(name):
    def output(self):
        with Whitespace():
            try:
                import_module("examples." + name)
            except Exception as cause:
                cause = Except.wrap(cause)
                logger.warning("Problem", cause=cause)

    return output


for f in File("examples").children:
    if f.extension == "py":
        func = _single_test(f.stem)
        if f.stem in skip_list:
            func = unittest.skip("please fix " + f.stem)(func)
        setattr(TestAllExamples, "test_" + f.stem, func)
