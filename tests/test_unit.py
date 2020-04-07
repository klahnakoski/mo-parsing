#
# test_unit.py
#
# Unit tests for mo_parsing module
#
# Copyright 2002-2019, Paul McGuire
#
#
import ast
import datetime
import json
import math
import operator
import re
import sys
import textwrap
import traceback
from io import StringIO
from itertools import product
from textwrap import dedent
from unittest import TestCase, skip

from mo_dots import coalesce
from mo_logs import Log
from mo_times import Timer

from examples import fourFn, configParse, idlParse, ebnf
from examples.jsonParser import jsonObject
from examples.simpleSQL import simpleSQL
from mo_parsing import *
from mo_parsing import (
    ParseException,
    Word,
    alphas,
    nums,
    Combine,
    CharsNotIn,
    Keyword,
    Literal,
    QuotedString,
    alphanums,
    Dict,
    ParseBaseException,
    Forward,
    Regex,
    ParseFatalException,
    WordStart,
    CaselessKeyword,
    WordEnd,
    helpers,
    CaselessLiteral,
    RecursiveGrammarException,
    engine,
)
from mo_parsing.core import (
    quotedString,
    Suppress,
    StringEnd,
    Group,
    OneOrMore,
    Optional,
    SkipTo,
    And,
    replaceWith,
    ZeroOrMore,
    Empty,
)
from mo_parsing.engine import Engine
from mo_parsing.helpers import (
    real,
    sci_real,
    number,
    integer,
    identifier,
    comma_separated_list,
    upcaseTokens,
    downcaseTokens,
    sglQuotedString,
    dblQuotedString,
    oneOf,
    delimitedList,
    removeQuotes,
    cStyleComment,
    infixNotation,
    opAssoc,
    countedArray,
    lineEnd,
    stringEnd,
    originalTextFor,
    makeHTMLTags,
    empty,
    withAttribute,
    nestedExpr,
    restOfLine,
    cppStyleComment,
    withClass,
    iso8601_date,
    locatedExpr,
    anyOpenTag,
    anyCloseTag,
    commonHTMLEntity,
    replaceHTMLEntity,
    mac_address,
    ipv4_address,
    fnumber,
    convertToDate,
    iso8601_datetime,
    uuid,
    fraction,
    mixed_integer,
    tokenMap,
    pythonStyleComment,
    ipv6_address,
    convertToDatetime,
    stripHTMLTags,
    indentedBlock,
)
from mo_parsing.utils import parsing_unicode, printables, traceParseAction, hexnums
from tests.json_parser_tests import test1, test2, test3, test4, test5

# see which Python implementation we are running
from tests.utils import TestParseResultsAsserts

CPYTHON_ENV = sys.platform == "win32"
IRON_PYTHON_ENV = sys.platform == "cli"
JYTHON_ENV = sys.platform.startswith("java")

VERBOSE = True


def flatten(tok):
    # simple utility for flattening parse results
    return list(_flatten(tok))


def _flatten(tok):

    if isinstance(tok, ParseResults):
        for t in tok:
            for tt in _flatten(t):
                yield tt
    else:
        yield tok


class resetting:
    def __init__(self, *args):
        ob = args[0]
        attrnames = args[1:]
        self.ob = ob
        self.save_attrs = attrnames
        self.save_values = [getattr(ob, attrname) for attrname in attrnames]

    def __enter__(self):
        pass

    def __exit__(self, *args):
        for attr, value in zip(self.save_attrs, self.save_values):
            setattr(self.ob, attr, value)


class TestParsing(TestParseResultsAsserts, TestCase):
    def setUp(self):
        engine.Engine()

    def testParseFourFn(self):
        def test(s, ans):
            fourFn.exprStack[:] = []
            results = fourFn.bnf.parseString(s)
            try:
                resultValue = fourFn.evaluate_stack(fourFn.exprStack)
            except Exception:
                self.assertIsNone(ans, "exception raised for expression {!r}".format(s))
            else:
                self.assertEqual(resultValue, ans, "failed to evaluate")

        test("9", 9)
        test("-9", -9)
        test("--9", 9)
        test("-E", -math.e)
        test("9 + 3 + 6", 9 + 3 + 6)
        test("9 + 3 / 11", 9 + 3.0 / 11)
        test("(9 + 3)", (9 + 3))
        test("(9+3) / 11", (9 + 3.0) / 11)
        test("9 - 12 - 6", 9 - 12 - 6)
        test("9 - (12 - 6)", 9 - (12 - 6))
        test("2*3.14159", 2 * 3.14159)
        test("3.1415926535*3.1415926535 / 10", 3.1415926535 * 3.1415926535 / 10)
        test("PI * PI / 10", math.pi * math.pi / 10)
        test("PI*PI/10", math.pi * math.pi / 10)
        test("PI^2", math.pi ** 2)
        test("round(PI^2)", round(math.pi ** 2))
        test("6.02E23 * 8.048", 6.02e23 * 8.048)
        test("e / 3", math.e / 3)
        test("sin(PI/2)", math.sin(math.pi / 2))
        test("10+sin(PI/4)^2", 10 + math.sin(math.pi / 4) ** 2)
        test("trunc(E)", int(math.e))
        test("trunc(-E)", int(-math.e))
        test("round(E)", round(math.e))
        test("round(-E)", round(-math.e))
        test("E^PI", math.e ** math.pi)
        test("exp(0)", 1)
        test("exp(1)", math.e)
        test("2^3^2", 2 ** 3 ** 2)
        test("(2^3)^2", (2 ** 3) ** 2)
        test("2^3+2", 2 ** 3 + 2)
        test("2^3+5", 2 ** 3 + 5)
        test("2^9", 2 ** 9)
        test("sgn(-2)", -1)
        test("sgn(0)", 0)
        test("sgn(0.1)", 1)
        test("foo(0.1)", None)
        test("round(E, 3)", round(math.e, 3))
        test("round(PI^2, 3)", round(math.pi ** 2, 3))
        test("sgn(cos(PI/4))", 1)
        test("sgn(cos(PI/2))", 0)
        test("sgn(cos(PI*3/4))", -1)
        test("+(sgn(cos(PI/4)))", 1)
        test("-(sgn(cos(PI/4)))", -1)

    def testParseSQL(self):
        def test(s, numToks, errloc=-1):
            try:
                sqlToks = flatten(simpleSQL.parseString(s))

                self.assertEqual(
                    len(sqlToks),
                    numToks,
                    "invalid parsed tokens, expected {}, found {} ({})".format(
                        numToks, len(sqlToks), sqlToks
                    ),
                )
            except ParseException as e:
                if errloc >= 0:
                    self.assertEqual(
                        e.loc,
                        errloc,
                        "expected error at {}, found at {}".format(errloc, e.loc),
                    )

        test("SELECT * from XYZZY, ABC", 6)
        test("select * from SYS.XYZZY", 5)
        test("Select A from Sys.dual", 5)
        test("Select A,B,C from Sys.dual", 7)
        test("Select A, B, C from Sys.dual", 7)
        test("Select A, B, C from Sys.dual, Table2   ", 8)
        test("Xelect A, B, C from Sys.dual", 0, 0)
        test("Select A, B, C frox Sys.dual", 0, 15)
        test("Select", 0, 6)
        test("Select &&& frox Sys.dual", 0, 7)
        test("Select A from Sys.dual where a in ('RED','GREEN','BLUE')", 12)
        test(
            "Select A from Sys.dual where a in ('RED','GREEN','BLUE') and b in (10,20,30)",
            20,
        )
        test(
            "Select A,b from table1,table2 where table1.id eq table2.id -- test out comparison operators",
            10,
        )

    def testParseConfigFile(self):
        def test(fnam, numToks, resCheckList):

            with open(fnam) as infile:
                iniFileLines = "\n".join(infile.read().splitlines())
            iniData = configParse.inifile_BNF().parseString(iniFileLines)

            self.assertEqual(
                len(flatten(iniData)), numToks, "file %s not parsed correctly" % fnam,
            )
            for chk in resCheckList:
                var = iniData
                for attr in chk[0].split("."):
                    var = getattr(var, attr)

                self.assertEqual(
                    var,
                    chk[1],
                    "ParseConfigFileTest: failed to parse ini {!r} as expected {}, found {}".format(
                        chk[0], chk[1], var
                    ),
                )

        test(
            "tests/resources/karthik.ini",
            23,
            [("users.K", "8"), ("users.mod_scheme", "'QPSK'"), ("users.Na", "K+2")],
        )
        test(
            "tests/resources/Setup.ini",
            125,
            [
                ("Startup.audioinf", "M3i"),
                ("Languages.key1", "0x0003"),
                ("test.foo", "bar"),
            ],
        )

    def testParseJSONDataSimple(self):
        jsons = json.dumps({"glossary": {"title": "example glossary"}})
        expected = [["glossary", [[["title", "example glossary"]]]]]
        result = jsonObject.parseString(jsons)
        self.assertEqual(result, expected, "failed test {}".format(jsons))

    def testParseJSONData(self):
        expected = [
            [
                [
                    "glossary",
                    [
                        ["title", "example glossary"],
                        [
                            "GlossDiv",
                            [
                                ["title", "S"],
                                [
                                    "GlossList",
                                    [
                                        [
                                            ["ID", "SGML"],
                                            ["SortAs", "SGML"],
                                            [
                                                "GlossTerm",
                                                "Standard Generalized Markup Language",
                                            ],
                                            ["Acronym", "SGML"],
                                            ["LargestPrimeLessThan100", 97],
                                            ["AvogadroNumber", 6.02e23],
                                            ["EvenPrimesGreaterThan2", None],
                                            ["PrimesLessThan10", [2, 3, 5, 7]],
                                            ["WMDsFound", False],
                                            ["IraqAlQaedaConnections", None],
                                            ["Abbrev", "ISO 8879:1986"],
                                            [
                                                "GlossDef",
                                                "A meta-markup language, used to create markup languages such as "
                                                "DocBook.",
                                            ],
                                            ["GlossSeeAlso", ["GML", "XML", "markup"]],
                                            ["EmptyDict", []],
                                            ["EmptyList", [[]]],
                                        ]
                                    ],
                                ],
                            ],
                        ],
                    ],
                ]
            ],
            [
                [
                    "menu",
                    [
                        ["id", "file"],
                        ["value", "File:"],
                        [
                            "popup",
                            [
                                [
                                    "menuitem",
                                    [
                                        [
                                            ["value", "New"],
                                            ["onclick", "CreateNewDoc()"],
                                        ],
                                        [["value", "Open"], ["onclick", "OpenDoc()"]],
                                        [["value", "Close"], ["onclick", "CloseDoc()"]],
                                    ],
                                ]
                            ],
                        ],
                    ],
                ]
            ],
            [
                [
                    "widget",
                    [
                        ["debug", "on"],
                        [
                            "window",
                            [
                                ["title", "Sample Konfabulator Widget"],
                                ["name", "main_window"],
                                ["width", 500],
                                ["height", 500],
                            ],
                        ],
                        [
                            "image",
                            [
                                ["src", "Images/Sun.png"],
                                ["name", "sun1"],
                                ["hOffset", 250],
                                ["vOffset", 250],
                                ["alignment", "center"],
                            ],
                        ],
                        [
                            "text",
                            [
                                ["data", "Click Here"],
                                ["size", 36],
                                ["style", "bold"],
                                ["name", "text1"],
                                ["hOffset", 250],
                                ["vOffset", 100],
                                ["alignment", "center"],
                                [
                                    "onMouseUp",
                                    "sun1.opacity = (sun1.opacity / 100) * 90;",
                                ],
                            ],
                        ],
                    ],
                ]
            ],
            [
                [
                    "web-app",
                    [
                        [
                            "servlet",
                            [
                                [
                                    ["servlet-name", "cofaxCDS"],
                                    ["servlet-class", "org.cofax.cds.CDSServlet"],
                                    [
                                        "init-param",
                                        [
                                            [
                                                "configGlossary:installationAt",
                                                "Philadelphia, PA",
                                            ],
                                            [
                                                "configGlossary:adminEmail",
                                                "ksm@pobox.com",
                                            ],
                                            ["configGlossary:poweredBy", "Cofax"],
                                            [
                                                "configGlossary:poweredByIcon",
                                                "/images/cofax.gif",
                                            ],
                                            [
                                                "configGlossary:staticPath",
                                                "/content/static",
                                            ],
                                            [
                                                "templateProcessorClass",
                                                "org.cofax.WysiwygTemplate",
                                            ],
                                            [
                                                "templateLoaderClass",
                                                "org.cofax.FilesTemplateLoader",
                                            ],
                                            ["templatePath", "templates"],
                                            ["templateOverridePath", ""],
                                            ["defaultListTemplate", "listTemplate.htm"],
                                            [
                                                "defaultFileTemplate",
                                                "articleTemplate.htm",
                                            ],
                                            ["useJSP", False],
                                            ["jspListTemplate", "listTemplate.jsp"],
                                            ["jspFileTemplate", "articleTemplate.jsp"],
                                            ["cachePackageTagsTrack", 200],
                                            ["cachePackageTagsStore", 200],
                                            ["cachePackageTagsRefresh", 60],
                                            ["cacheTemplatesTrack", 100],
                                            ["cacheTemplatesStore", 50],
                                            ["cacheTemplatesRefresh", 15],
                                            ["cachePagesTrack", 200],
                                            ["cachePagesStore", 100],
                                            ["cachePagesRefresh", 10],
                                            ["cachePagesDirtyRead", 10],
                                            [
                                                "searchEngineListTemplate",
                                                "forSearchEnginesList.htm",
                                            ],
                                            [
                                                "searchEngineFileTemplate",
                                                "forSearchEngines.htm",
                                            ],
                                            [
                                                "searchEngineRobotsDb",
                                                "WEB-INF/robots.db",
                                            ],
                                            ["useDataStore", True],
                                            [
                                                "dataStoreClass",
                                                "org.cofax.SqlDataStore",
                                            ],
                                            [
                                                "redirectionClass",
                                                "org.cofax.SqlRedirection",
                                            ],
                                            ["dataStoreName", "cofax"],
                                            [
                                                "dataStoreDriver",
                                                "com.microsoft.jdbc.sqlserver.SQLServerDriver",
                                            ],
                                            [
                                                "dataStoreUrl",
                                                "jdbc:microsoft:sqlserver://LOCALHOST:1433;DatabaseName=goon",
                                            ],
                                            ["dataStoreUser", "sa"],
                                            ["dataStorePassword", "dataStoreTestQuery"],
                                            [
                                                "dataStoreTestQuery",
                                                "SET NOCOUNT ON;select test='test';",
                                            ],
                                            [
                                                "dataStoreLogFile",
                                                "/usr/local/tomcat/logs/datastore.log",
                                            ],
                                            ["dataStoreInitConns", 10],
                                            ["dataStoreMaxConns", 100],
                                            ["dataStoreConnUsageLimit", 100],
                                            ["dataStoreLogLevel", "debug"],
                                            ["maxUrlLength", 500],
                                        ],
                                    ],
                                ],
                                [
                                    ["servlet-name", "cofaxEmail"],
                                    ["servlet-class", "org.cofax.cds.EmailServlet"],
                                    [
                                        "init-param",
                                        [
                                            ["mailHost", "mail1"],
                                            ["mailHostOverride", "mail2"],
                                        ],
                                    ],
                                ],
                                [
                                    ["servlet-name", "cofaxAdmin"],
                                    ["servlet-class", "org.cofax.cds.AdminServlet"],
                                ],
                                [
                                    ["servlet-name", "fileServlet"],
                                    ["servlet-class", "org.cofax.cds.FileServlet"],
                                ],
                                [
                                    ["servlet-name", "cofaxTools"],
                                    [
                                        "servlet-class",
                                        "org.cofax.cms.CofaxToolsServlet",
                                    ],
                                    [
                                        "init-param",
                                        [
                                            ["templatePath", "toolstemplates/"],
                                            ["log", 1],
                                            [
                                                "logLocation",
                                                "/usr/local/tomcat/logs/CofaxTools.log",
                                            ],
                                            ["logMaxSize", ""],
                                            ["dataLog", 1],
                                            [
                                                "dataLogLocation",
                                                "/usr/local/tomcat/logs/dataLog.log",
                                            ],
                                            ["dataLogMaxSize", ""],
                                            [
                                                "removePageCache",
                                                "/content/admin/remove?cache=pages&id=",
                                            ],
                                            [
                                                "removeTemplateCache",
                                                "/content/admin/remove?cache=templates&id=",
                                            ],
                                            [
                                                "fileTransferFolder",
                                                "/usr/local/tomcat/webapps/content/fileTransferFolder",
                                            ],
                                            ["lookInContext", 1],
                                            ["adminGroupID", 4],
                                            ["betaServer", True],
                                        ],
                                    ],
                                ],
                            ],
                        ],
                        [
                            "servlet-mapping",
                            [
                                ["cofaxCDS", "/"],
                                ["cofaxEmail", "/cofaxutil/aemail/*"],
                                ["cofaxAdmin", "/admin/*"],
                                ["fileServlet", "/static/*"],
                                ["cofaxTools", "/tools/*"],
                            ],
                        ],
                        [
                            "taglib",
                            [
                                ["taglib-uri", "cofax.tld"],
                                ["taglib-location", "/WEB-INF/tlds/cofax.tld"],
                            ],
                        ],
                    ],
                ]
            ],
            [
                [
                    "menu",
                    [
                        ["header", "SVG Viewer"],
                        [
                            "items",
                            [
                                [["id", "Open"]],
                                [["id", "OpenNew"], ["label", "Open New"]],
                                None,
                                [["id", "ZoomIn"], ["label", "Zoom In"]],
                                [["id", "ZoomOut"], ["label", "Zoom Out"]],
                                [["id", "OriginalView"], ["label", "Original View"]],
                                None,
                                [["id", "Quality"]],
                                [["id", "Pause"]],
                                [["id", "Mute"]],
                                None,
                                [["id", "Find"], ["label", "Find..."]],
                                [["id", "FindAgain"], ["label", "Find Again"]],
                                [["id", "Copy"]],
                                [["id", "CopyAgain"], ["label", "Copy Again"]],
                                [["id", "CopySVG"], ["label", "Copy SVG"]],
                                [["id", "ViewSVG"], ["label", "View SVG"]],
                                [["id", "ViewSource"], ["label", "View Source"]],
                                [["id", "SaveAs"], ["label", "Save As"]],
                                None,
                                [["id", "Help"]],
                                [
                                    ["id", "About"],
                                    ["label", "About Adobe CVG Viewer..."],
                                ],
                            ],
                        ],
                    ],
                ]
            ],
        ]

        for t, exp in zip((test1, test2, test3, test4, test5), expected):
            result = jsonObject.parseString(t)

            self.assertEqual(result, exp, "failed test {}".format(t))

    def testParseCommaSeparatedValues(self):
        testData = [
            "m  ",
            "a,b,c,100.2,,3",
            "d, e, j k , m  ",
            "'Hello, World', f, g , , 5.1,x",
            "John Doe, 123 Main St., Cleveland, Ohio",
            "Jane Doe, 456 St. James St., Los Angeles , California   ",
            "",
        ]
        testVals = [
            [(0, "m")],
            [(3, "100.2"), (4, ""), (5, "3")],
            [(2, "j k"), (3, "m")],
            [(0, "'Hello, World'"), (2, "g"), (3, "")],
            [(0, "John Doe"), (1, "123 Main St."), (2, "Cleveland"), (3, "Ohio")],
            [
                (0, "Jane Doe"),
                (1, "456 St. James St."),
                (2, "Los Angeles"),
                (3, "California"),
            ],
        ]
        for line, tests in zip(testData, testVals):
            results = comma_separated_list.parseString(line)
            for t in tests:
                self.assertTrue(
                    len(results) > t[0] and results[t[0]] == t[1],
                    "failed on %s, item %d s/b '%s', got '%s'"
                    % (line, t[0], t[1], str(results)),
                )

    def testParseEBNF(self):

        grammar = """
        syntax = (syntax_rule), {(syntax_rule)};
        syntax_rule = meta_identifier, '=', definitions_list, ';';
        definitions_list = single_definition, {'|', single_definition};
        single_definition = syntactic_term, {',', syntactic_term};
        syntactic_term = syntactic_factor,['-', syntactic_factor];
        syntactic_factor = [integer, '*'], syntactic_primary;
        syntactic_primary = optional_sequence | repeated_sequence |
          grouped_sequence | meta_identifier | terminal_string;
        optional_sequence = '[', definitions_list, ']';
        repeated_sequence = '{', definitions_list, '}';
        grouped_sequence = '(', definitions_list, ')';
        (*
        terminal_string = "'", character - "'", {character - "'"}, "'" |
          '"', character - '"', {character - '"'}, '"';
         meta_identifier = letter, {letter | digit};
        integer = digit, {digit};
        *)
        """

        table = {}
        table["terminal_string"] = quotedString
        table["meta_identifier"] = Word(alphas + "_", alphas + "_" + nums)
        table["integer"] = Word(nums)

        parsers = ebnf.parse(grammar, table)
        ebnf_parser = parsers["syntax"]

        self.assertEqual(
            len(list(parsers.keys())), 13, "failed to construct syntax grammar"
        )

        parsed_chars = ebnf_parser.parseString(grammar)
        parsed_char_len = len(parsed_chars)

        self.assertEqual(
            len(flatten(parsed_chars)), 98, "failed to tokenize grammar correctly",
        )

    def testParseIDL(self):
        def test(strng, numToks, errloc=0):

            try:
                bnf = idlParse.CORBA_IDL_BNF()
                tokens = bnf.parseString(strng)

                tokens = flatten(tokens)

                self.assertEqual(
                    len(tokens),
                    numToks,
                    "error matching IDL string, {} -> {}".format(strng, str(tokens)),
                )
            except ParseException as err:

                self.assertEqual(
                    numToks,
                    0,
                    "unexpected ParseException while parsing {}, {}".format(
                        strng, str(err)
                    ),
                )
                self.assertEqual(
                    err.loc,
                    errloc,
                    "expected ParseException at %d, found exception at %d"
                    % (errloc, err.loc),
                )

        test(
            """
            /*
             * a block comment *
             */
            typedef string[10] tenStrings;
            typedef sequence<string> stringSeq;
            typedef sequence< sequence<string> > stringSeqSeq;

            interface QoSAdmin {
                stringSeq method1(in string arg1, inout long arg2);
                stringSeqSeq method2(in string arg1, inout long arg2, inout long arg3);
                string method3();
              };
            """,
            59,
        )
        test(
            """
            /*
             * a block comment *
             */
            typedef string[10] tenStrings;
            typedef
                /** ** *** **** *
                 * a block comment *
                 */
                sequence<string> /*comment inside an And */ stringSeq;
            /* */  /**/ /***/ /****/
            typedef sequence< sequence<string> > stringSeqSeq;

            interface QoSAdmin {
                stringSeq method1(in string arg1, inout long arg2);
                stringSeqSeq method2(in string arg1, inout long arg2, inout long arg3);
                string method3();
              };
            """,
            59,
        )
        test(
            r"""
              const string test="Test String\n";
              const long  a = 0;
              const long  b = -100;
              const float c = 3.14159;
              const long  d = 0x007f7f7f;
              exception TestException
                {
                string msg;
                sequence<string> dataStrings;
                };

              interface TestInterface
                {
                void method1(in string arg1, inout long arg2);
                };
            """,
            60,
        )
        test(
            """
            module Test1
              {
              exception TestException
                {
                string msg;
                ];

              interface TestInterface
                {
                void method1(in string arg1, inout long arg2)
                  raises (TestException);
                };
              };
            """,
            0,
            56,
        )
        test(
            """
            module Test1
              {
              exception TestException
                {
                string msg;
                };

              };
            """,
            13,
        )

    def testParseVerilog(self):
        pass

    def testScanString(self):

        testdata = """
            <table border="0" cellpadding="3" cellspacing="3" frame="" width="90%">
                <tr align="left" valign="top">
                        <td><b>Name</b></td>
                        <td><b>IP Address</b></td>
                        <td><b>Location</b></td>
                </tr>
                <tr align="left" valign="top" bgcolor="#c7efce">
                        <td>time-a.nist.gov</td>
                        <td>129.6.15.28</td>
                        <td>NIST, Gaithersburg, Maryland</td>
                </tr>
                <tr align="left" valign="top">
                        <td>time-b.nist.gov</td>
                        <td>129.6.15.29</td>
                        <td>NIST, Gaithersburg, Maryland</td>
                </tr>
                <tr align="left" valign="top" bgcolor="#c7efce">
                        <td>time-a.timefreq.bldrdoc.gov</td>
                        <td>132.163.4.101</td>
                        <td>NIST, Boulder, Colorado</td>
                </tr>
                <tr align="left" valign="top">
                        <td>time-b.timefreq.bldrdoc.gov</td>
                        <td>132.163.4.102</td>
                        <td>NIST, Boulder, Colorado</td>
                </tr>
                <tr align="left" valign="top" bgcolor="#c7efce">
                        <td>time-c.timefreq.bldrdoc.gov</td>
                        <td>132.163.4.103</td>
                        <td>NIST, Boulder, Colorado</td>
                </tr>
            </table>
            """
        integer = Word(nums)
        ipAddress = Combine(integer + "." + integer + "." + integer + "." + integer)
        tdStart = Suppress("<td>")
        tdEnd = Suppress("</td>")
        timeServerPattern = (
            tdStart
            + ipAddress("ipAddr")
            + tdEnd
            + tdStart
            + CharsNotIn("<")("loc")
            + tdEnd
        )
        servers = [
            srvr["ipAddr"]
            for srvr, startloc, endloc in timeServerPattern.scanString(testdata)
        ]

        self.assertEqual(
            servers,
            [
                "129.6.15.28",
                "129.6.15.29",
                "132.163.4.101",
                "132.163.4.102",
                "132.163.4.103",
            ],
            "failed scanString()",
        )

        # test for stringEnd detection in scanString
        foundStringEnds = [r for r in StringEnd().scanString("xyzzy")]

        self.assertTrue(foundStringEnds, "Failed to find StringEnd in scanString")

    def testQuotedStrings(self):

        testData = """
                'a valid single quoted string'
                'an invalid single quoted string
                 because it spans lines'
                "a valid double quoted string"
                "an invalid double quoted string
                 because it spans lines"
            """

        sglStrings = [
            (t[0], b, e) for (t, b, e) in sglQuotedString.scanString(testData)
        ]

        self.assertTrue(
            len(sglStrings) == 1
            and (sglStrings[0][1] == 17 and sglStrings[0][2] == 47),
            "single quoted string failure",
        )

        dblStrings = [
            (t[0], b, e) for (t, b, e) in dblQuotedString.scanString(testData)
        ]

        self.assertTrue(
            len(dblStrings) == 1
            and (dblStrings[0][1] == 154 and dblStrings[0][2] == 184),
            "double quoted string failure",
        )

        allStrings = [(t[0], b, e) for (t, b, e) in quotedString.scanString(testData)]

        self.assertTrue(
            len(allStrings) == 2
            and (allStrings[0][1] == 17 and allStrings[0][2] == 47)
            and (allStrings[1][1] == 154 and allStrings[1][2] == 184),
            "quoted string failure",
        )

        escapedQuoteTest = r"""
                'This string has an escaped (\') quote character'
                "This string has an escaped (\") quote character"
            """

        sglStrings = [
            (t[0], b, e) for (t, b, e) in sglQuotedString.scanString(escapedQuoteTest)
        ]

        self.assertTrue(
            len(sglStrings) == 1
            and (sglStrings[0][1] == 17 and sglStrings[0][2] == 66),
            "single quoted string escaped quote failure (%s)" % str(sglStrings[0]),
        )

        dblStrings = [
            (t[0], b, e) for (t, b, e) in dblQuotedString.scanString(escapedQuoteTest)
        ]

        self.assertTrue(
            len(dblStrings) == 1
            and (dblStrings[0][1] == 83 and dblStrings[0][2] == 132),
            "double quoted string escaped quote failure (%s)" % str(dblStrings[0]),
        )

        allStrings = [
            (t[0], b, e) for (t, b, e) in quotedString.scanString(escapedQuoteTest)
        ]

        self.assertTrue(
            len(allStrings) == 2
            and (
                allStrings[0][1] == 17
                and allStrings[0][2] == 66
                and allStrings[1][1] == 83
                and allStrings[1][2] == 132
            ),
            "quoted string escaped quote failure (%s)"
            % ([str(s[0]) for s in allStrings]),
        )

        dblQuoteTest = r"""
                'This string has an doubled ('') quote character'
                "This string has an doubled ("") quote character"
            """
        sglStrings = [
            (t[0], b, e) for (t, b, e) in sglQuotedString.scanString(dblQuoteTest)
        ]

        self.assertTrue(
            len(sglStrings) == 1
            and (sglStrings[0][1] == 17 and sglStrings[0][2] == 66),
            "single quoted string escaped quote failure (%s)" % str(sglStrings[0]),
        )
        dblStrings = [
            (t[0], b, e) for (t, b, e) in dblQuotedString.scanString(dblQuoteTest)
        ]

        self.assertTrue(
            len(dblStrings) == 1
            and (dblStrings[0][1] == 83 and dblStrings[0][2] == 132),
            "double quoted string escaped quote failure (%s)" % str(dblStrings[0]),
        )
        allStrings = [
            (t[0], b, e) for (t, b, e) in quotedString.scanString(dblQuoteTest)
        ]

        self.assertTrue(
            len(allStrings) == 2
            and (
                allStrings[0][1] == 17
                and allStrings[0][2] == 66
                and allStrings[1][1] == 83
                and allStrings[1][2] == 132
            ),
            "quoted string escaped quote failure (%s)"
            % ([str(s[0]) for s in allStrings]),
        )

        print(
            "testing catastrophic RE backtracking in implementation of dblQuotedString"
        )
        for expr, test_string in [
            (dblQuotedString, '"' + "\\xff" * 500),
            (sglQuotedString, "'" + "\\xff" * 500),
            (quotedString, '"' + "\\xff" * 500),
            (quotedString, "'" + "\\xff" * 500),
            (QuotedString('"'), '"' + "\\xff" * 500),
            (QuotedString("'"), "'" + "\\xff" * 500),
        ]:
            expr.parseString(test_string + test_string[0])
            try:
                expr.parseString(test_string)
            except Exception:
                continue

    def testCaselessOneOf(self):

        caseless1 = oneOf("d a b c aA B A C", caseless=True)
        caseless1str = str(caseless1)

        caseless2 = oneOf("d a b c Aa B A C", caseless=True)
        caseless2str = str(caseless2)

        self.assertEqual(
            caseless1str.upper(),
            caseless2str.upper(),
            "oneOf not handling caseless option properly",
        )
        self.assertNotEqual(
            caseless1str, caseless2str, "Caseless option properly sorted"
        )

        res = caseless1[...].parseString("AAaaAaaA")

        self.assertEqual(len(res), 4, "caseless1 oneOf failed")
        self.assertEqual(
            "".join(res), "aA" * 4, "caseless1 CaselessLiteral return failed"
        )

        res = caseless2[...].parseString("AAaaAaaA")

        self.assertEqual(len(res), 4, "caseless2 oneOf failed")
        self.assertEqual(
            "".join(res), "Aa" * 4, "caseless1 CaselessLiteral return failed"
        )

    def testCommentParser(self):

        testdata = """
        /* */
        /** **/
        /**/
        /***/
        /****/
        /* /*/
        /** /*/
        /*** /*/
        /*
         ablsjdflj
         */
        """
        foundLines = [
            lineno(s, testdata) for t, s, e in cStyleComment.scanString(testdata)
        ]
        self.assertEqual(
            foundLines,
            list(range(11))[2:],
            "only found C comments on lines " + str(foundLines),
        )
        testdata = """
        <!-- -->
        <!--- --->
        <!---->
        <!----->
        <!------>
        <!-- /-->
        <!--- /-->
        <!---- /-->
        <!---- /- ->
        <!---- / -- >
        <!--
         ablsjdflj
         -->
        """
        foundLines = [
            lineno(s, testdata) for t, s, e in htmlComment.scanString(testdata)
        ]
        self.assertEqual(
            foundLines,
            list(range(11))[2:],
            "only found HTML comments on lines " + str(foundLines),
        )

        # test C++ single line comments that have line terminated with '\' (should continue comment to following line)
        testSource = r"""
            // comment1
            // comment2 \
            still comment 2
            // comment 3
            """
        self.assertEqual(
            len(cppStyleComment.searchString(testSource)[1][0]),
            41,
            r"failed to match single-line comment with '\' at EOL",
        )

    def testParseExpressionResults(self):

        a = Word("a", alphas).set_parser_name("A")
        b = Word("b", alphas).set_parser_name("B")
        c = Word("c", alphas).set_parser_name("C")
        ab = (a + b).set_parser_name("AB")
        abc = (ab + c).set_parser_name("ABC")
        word = Word(alphas).set_parser_name("word")

        words = Group(OneOrMore(~a + word)).set_parser_name("words")

        phrase = (
            words("Head") + Group(a + Optional(b + Optional(c)))("ABC") + words("Tail")
        )

        results = phrase.parseString("xavier yeti alpha beta charlie will beaver")

        for key, ln in [("Head", 2), ("ABC", 3), ("Tail", 2)]:
            self.assertEqual(
                len(results[key]),
                ln,
                "expected %d elements in %s, found %s" % (ln, key, str(results[key])),
            )

    def testParseKeyword(self):

        kw = Keyword("if")
        lit = Literal("if")

        def test(s, litShouldPass, kwShouldPass):
            try:
                lit.parseString(s)
            except Exception:
                if litShouldPass:
                    self.assertTrue(
                        False, "Literal failed to match %s, should have" % s
                    )
            else:
                if not litShouldPass:
                    self.assertTrue(False, "Literal matched %s, should not have" % s)

            try:
                kw.parseString(s)
            except Exception:

                if kwShouldPass:
                    self.assertTrue(
                        False, "Keyword failed to match %s, should have" % s
                    )
            else:
                if not kwShouldPass:
                    self.assertTrue(False, "Keyword matched %s, should not have" % s)

        test("ifOnlyIfOnly", True, False)
        test("if(OnlyIfOnly)", True, True)
        test("if (OnlyIf Only)", True, True)

        kw = Keyword("if", caseless=True)

        test("IFOnlyIfOnly", False, False)
        test("If(OnlyIfOnly)", False, True)
        test("iF (OnlyIf Only)", False, True)

    def testParseExpressionResultsAccumulate(self):

        num = Word(nums).set_parser_name("num")("base10*")
        hexnum = Combine("0x" + Word(nums)).set_parser_name("hexnum")("hex*")
        name = Word(alphas).set_parser_name("word")("word*")
        list_of_num = delimitedList(hexnum | num | name, ",")

        tokens = list_of_num.parseString("1, 0x2, 3, 0x4, aaa")
        # print(tokens)
        # self.assertParseResultsEquals(
        #     tokens,
        #     expected_list=["1", "0x2", "3", "0x4", "aaa"],
        #     expected_dict={
        #         "base10": ["1", "3"],
        #         "hex": ["0x2", "0x4"],
        #         "word": ["aaa"],
        #     },
        # )

        lbrack = Literal("(").suppress()
        rbrack = Literal(")").suppress()
        integer = Word(nums).set_parser_name("int")
        variable = Word(alphas, max=1).set_parser_name("variable")
        relation_body_item = (
            variable | integer | quotedString.copy().setParseAction(removeQuotes)
        )
        relation_name = Word(alphas + "_", alphanums + "_")
        relation_body = lbrack + Group(delimitedList(relation_body_item)) + rbrack
        Goal = Dict(Group(relation_name + relation_body))
        Comparison_Predicate = Group(variable + oneOf("< >") + integer)("pred*")
        Query = Goal("head") + ":-" + delimitedList(Goal | Comparison_Predicate)

        test = """Q(x,y,z):-Bloo(x,"Mitsis",y),Foo(y,z,1243),y>28,x<12,x>3"""

        queryRes = Query.parseString(test)

        self.assertParseResultsEquals(
            queryRes.pred,
            expected_list=[["y", ">", "28"], ["x", "<", "12"], ["x", ">", "3"]],
            msg="Incorrect list for attribute pred, %s" % str(queryRes.pred),
        )

    def testReStringRange(self):
        testCases = (
            (r"[A-Z]"),
            (r"[A-A]"),
            (r"[A-Za-z]"),
            (r"[A-z]"),
            (r"[\ -\~]"),
            (r"[\0x20-0]"),
            (r"[\0x21-\0x7E]"),
            (r"[\0xa1-\0xfe]"),
            (r"[\040-0]"),
            (r"[A-Za-z0-9]"),
            (r"[A-Za-z0-9_]"),
            (r"[A-Za-z0-9_$]"),
            (r"[A-Za-z0-9_$\-]"),
            (r"[^0-9\\]"),
            (r"[a-zA-Z]"),
            (r"[/\^~]"),
            (r"[=\+\-!]"),
            (r"[A-]"),
            (r"[-A]"),
            (r"[\x21]"),
            (r"[а-яА-ЯёЁA-Z$_\041α-ω]"),
        )
        expectedResults = (
            "ABCDEFGHIJKLMNOPQRSTUVWXYZ",
            "A",
            "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz",
            "ABCDEFGHIJKLMNOPQRSTUVWXYZ[\\]^_`abcdefghijklmnopqrstuvwxyz",
            " !\"#$%&'()*+,-./0123456789:;<=>?@ABCDEFGHIJKLMNOPQRSTUVWXYZ[\\]^_`abcdefghijklmnopqrstuvwxyz{|}~",
            " !\"#$%&'()*+,-./0",
            "!\"#$%&'()*+,-./0123456789:;<=>?@ABCDEFGHIJKLMNOPQRSTUVWXYZ[\\]^_`abcdefghijklmnopqrstuvwxyz{|}~",
            "¡¢£¤¥¦§¨©ª«¬­®¯°±²³´µ¶·¸¹º»¼½¾¿ÀÁÂÃÄÅÆÇÈÉÊËÌÍÎÏÐÑÒÓÔÕÖ×ØÙÚÛÜÝÞßàáâãäåæçèéêëìíîïðñòóôõö÷øùúûüýþ",
            " !\"#$%&'()*+,-./0",
            "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789",
            "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_",
            "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_$",
            "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_$-",
            "0123456789\\",
            "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ",
            "/^~",
            "=+-!",
            "A-",
            "-A",
            "!",
            "абвгдежзийклмнопрстуфхцчшщъыьэюяАБВГДЕЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯёЁABCDEFGHIJKLMNOPQRSTUVWXYZ$_!αβγδεζηθικλμνξοπρςστυφχψω",
        )
        for test in zip(testCases, expectedResults):
            t, exp = test
            res = srange(t)
            # print(t, "->", res)
            self.assertEqual(
                res,
                exp,
                "srange error, srange({!r})->'{!r}', expected '{!r}'".format(
                    t, res, exp
                ),
            )

    def testSkipToParserTests(self):

        thingToFind = Literal("working")
        testExpr = (
            SkipTo(Literal(";"), include=True, ignore=cStyleComment) + thingToFind
        )

        def tryToParse(someText, fail_expected=False):
            try:
                testExpr.parseString(someText)
                self.assertFalse(
                    fail_expected, "expected failure but no exception raised"
                )
            except Exception as e:

                self.assertTrue(
                    fail_expected and isinstance(e, ParseBaseException),
                    "Exception {} while parsing string {}".format(e, repr(someText)),
                )

        # This first test works, as the SkipTo expression is immediately following the ignore expression (cStyleComment)
        tryToParse("some text /* comment with ; in */; working")
        # This second test previously failed, as there is text following the ignore expression, and before the SkipTo expression.
        tryToParse("some text /* comment with ; in */some other stuff; working")

        # tests for optional failOn argument
        testExpr = (
            SkipTo(Literal(";"), include=True, ignore=cStyleComment, failOn="other")
            + thingToFind
        )
        tryToParse("some text /* comment with ; in */; working")
        tryToParse(
            "some text /* comment with ; in */some other stuff; working",
            fail_expected=True,
        )

        # test that we correctly create named results
        text = "prefixDATAsuffix"
        data = Literal("DATA")
        suffix = Literal("suffix")
        expr = SkipTo(data + suffix)("prefix") + data + suffix
        result = expr.parseString(text)
        self.assertTrue(
            isinstance(result.prefix, str),
            "SkipTo created with wrong saveAsList attribute",
        )

        alpha_word = (~Literal("end") + Word(alphas, asKeyword=True)).set_parser_name(
            "alpha"
        )
        num_word = Word(nums, asKeyword=True).set_parser_name("int")

        def test(expr, test_string, expected_list, expected_dict):
            if (expected_list, expected_dict) == (None, None):
                with TestCase.assertRaises(
                    self,
                    Exception,
                    msg="{} failed to parse {!r}".format(expr, test_string),
                ):
                    expr.parseString(test_string)
            else:
                result = expr.parseString(test_string)
                self.assertParseResultsEquals(
                    result, expected_list=expected_list, expected_dict=expected_dict
                )

        # ellipses for SkipTo
        e = ... + Literal("end")
        test(e, "start 123 end", ["start 123 ", "end"], {"_skipped": ["start 123 "]})

        e = Literal("start") + ... + Literal("end")
        test(e, "start 123 end", ["start", "123 ", "end"], {"_skipped": ["123 "]})

        e = Literal("start") + ...
        test(e, "start 123 end", None, None)

        e = And(["start", ..., "end"])
        test(e, "start 123 end", ["start", "123 ", "end"], {"_skipped": ["123 "]})

        e = And([..., "end"])
        test(e, "start 123 end", ["start 123 ", "end"], {"_skipped": ["start 123 "]})

        e = "start" + (num_word | ...) + "end"
        test(e, "start 456 end", ["start", "456", "end"], {})
        test(
            e,
            "start 123 456 end",
            ["start", "123", "456 ", "end"],
            {"_skipped": ["456 "]},
        )
        test(e, "start end", ["start", "end"], {"_skipped": ""})

        e = "start" + (alpha_word[...] & num_word[...] | ...) + "end"
        test(e, "start 456 red end", ["start", "456", "red", "end"], {})
        test(e, "start red 456 end", ["start", "red", "456", "end"], {})
        test(
            e,
            "start 456 red + end",
            ["start", "456", "red", "+ ", "end"],
            {"_skipped": ["+ "]},
        )
        test(e, "start red end", ["start", "red", "end"], {})
        test(e, "start 456 end", ["start", "456", "end"], {})
        test(e, "start end", ["start", "end"], {})
        test(e, "start 456 + end", ["start", "456", "+ ", "end"], {"_skipped": ["+ "]})

        e = "start" + (alpha_word[1, ...] & num_word[1, ...] | ...) + "end"
        test(e, "start 456 red end", ["start", "456", "red", "end"], {})
        test(e, "start red 456 end", ["start", "red", "456", "end"], {})
        test(
            e,
            "start 456 red + end",
            ["start", "456", "red", "+ ", "end"],
            {"_skipped": ["+ "]},
        )
        test(e, "start red end", ["start", "red ", "end"], {"_skipped": ["red "]})
        test(e, "start 456 end", ["start", "456 ", "end"], {"_skipped": ["456 "]})
        test(
            e, "start end", ["start", "end"], {"_skipped": ""},
        )
        test(e, "start 456 + end", ["start", "456 + ", "end"], {"_skipped": ["456 + "]})

        e = "start" + (alpha_word | ...) + (num_word | ...) + "end"
        test(e, "start red 456 end", ["start", "red", "456", "end"], {})
        test(
            e, "start red end", ["start", "red", "end"], {"_skipped": ""},
        )
        test(
            e, "start end", ["start", "end"], {"_skipped": ""},
        )

        e = Literal("start") + ... + "+" + ... + "end"
        test(
            e,
            "start red + 456 end",
            ["start", "red ", "+", "456 ", "end"],
            {"_skipped": ["red ", "456 "]},
        )

    def testEllipsisRepetion(self):

        word = Word(alphas).set_parser_name("word")
        num = Word(nums).set_parser_name("num")

        exprs = [
            word[...] + num,
            word[0, ...] + num,
            word[1, ...] + num,
            word[2, ...] + num,
            word[..., 3] + num,
            word[2] + num,
        ]

        expected_res = [
            r"([abcd]+ )*\d+",
            r"([abcd]+ )*\d+",
            r"([abcd]+ )+\d+",
            r"([abcd]+ ){2,}\d+",
            r"([abcd]+ ){0,3}\d+",
            r"([abcd]+ ){2}\d+",
        ]

        tests = [
            "aa bb cc dd 123",
            "bb cc dd 123",
            "cc dd 123",
            "dd 123",
            "123",
        ]

        all_success = True
        for expr, expected_re in zip(exprs, expected_res):
            successful_tests = [t for t in tests if re.match(expected_re, t)]
            failure_tests = [t for t in tests if not re.match(expected_re, t)]
            success1, _ = expr.runTests(successful_tests)
            success2, _ = expr.runTests(failure_tests, failureTests=True)
            all_success = all_success and success1 and success2
            if not all_success:

                break

        self.assertTrue(all_success, "failed getItem_ellipsis test")

    def testEllipsisRepetionWithResultsNames(self):

        label = Word(alphas)
        val = integer()
        parser = label("label") + ZeroOrMore(val)("values")

        _, results = parser.runTests(
            """
            a 1
            b 1 2 3
            c
            """
        )
        expected = [
            (["a", 1], {"label": "a", "values": [1]}),
            (["b", 1, 2, 3], {"label": "b", "values": [1, 2, 3]}),
            (["c"], {"label": "c", "values": []}),
        ]
        for obs, exp in zip(results, expected):
            test, result = obs
            exp_list, exp_dict = exp
            self.assertParseResultsEquals(
                result, expected_list=exp_list, expected_dict=exp_dict
            )

        parser = label("label") + val[...]("values")

        _, results = parser.runTests(
            """
            a 1
            b 1 2 3
            c
            """
        )
        expected = [
            (["a", 1], {"label": "a", "values": [1]}),
            (["b", 1, 2, 3], {"label": "b", "values": [1, 2, 3]}),
            (["c"], {"label": "c", "values": []}),
        ]
        for obs, exp in zip(results, expected):
            test, result = obs
            exp_list, exp_dict = exp
            self.assertParseResultsEquals(
                result, expected_list=exp_list, expected_dict=exp_dict
            )

        pt = Group(val("x") + Suppress(",") + val("y"))
        parser = label("label") + pt[...]("points")
        _, results = parser.runTests(
            """
            a 1,1
            b 1,1 2,2 3,3
            c
            """
        )
        expected = [
            (["a", [1, 1]], {"label": "a", "points": {"x": 1, "y": 1}}),
            (
                ["b", [1, 1], [2, 2], [3, 3]],
                {
                    "label": "b",
                    "points": [{"x": 1, "y": 1}, {"x": 2, "y": 2}, {"x": 3, "y": 3}],
                },
            ),
            (["c"], {"label": "c", "points": []}),
        ]
        for obs, exp in zip(results, expected):
            test, result = obs
            exp_list, exp_dict = exp
            self.assertParseResultsEquals(
                result, expected_list=exp_list, expected_dict=exp_dict
            )

    def testCustomQuotes(self):

        testString = r"""
            sdlfjs :sdf\:jls::djf: sl:kfsjf
            sdlfjs -sdf\:jls::--djf: sl-kfsjf
            sdlfjs -sdf\:::jls::--djf: sl:::-kfsjf
            sdlfjs ^sdf\:jls^^--djf^ sl-kfsjf
            sdlfjs ^^^==sdf\:j=lz::--djf: sl=^^=kfsjf
            sdlfjs ==sdf\:j=ls::--djf: sl==kfsjf^^^
        """
        colonQuotes = QuotedString(":", "\\", "::")
        dashQuotes = QuotedString("-", "\\", "--")
        hatQuotes = QuotedString("^", "\\")
        hatQuotes1 = QuotedString("^", "\\", "^^")
        dblEqQuotes = QuotedString("==", "\\")

        def test(quoteExpr, expected):

            self.assertEqual(
                quoteExpr.searchString(testString)[0][0],
                expected,
                "failed to match {}, expected '{}', got '{}'".format(
                    quoteExpr, expected, quoteExpr.searchString(testString)[0]
                ),
            )

        test(colonQuotes, r"sdf:jls:djf")
        test(dashQuotes, r"sdf:jls::-djf: sl")
        test(hatQuotes, r"sdf:jls")
        test(hatQuotes1, r"sdf:jls^--djf")
        test(dblEqQuotes, r"sdf:j=ls::--djf: sl")
        test(QuotedString(":::"), "jls::--djf: sl")
        test(QuotedString("==", endQuoteChar="--"), r"sdf\:j=lz::")
        test(
            QuotedString("^^^", multiline=True),
            r"""==sdf\:j=lz::--djf: sl=^^=kfsjf
            sdlfjs ==sdf\:j=ls::--djf: sl==kfsjf""",
        )
        with TestCase.assertRaises(self, SyntaxError):
            QuotedString("", "\\")

    def testRecursiveCombine(self):

        testInput = "myc(114)r(11)dd"
        Stream = Forward()
        Stream << Optional(Word(alphas)) + Optional("(" + Word(nums) + ")" + Stream)
        expected = ["".join(Stream.parseString(testInput))]

        Stream = Forward()
        Stream << Combine(
            Optional(Word(alphas)) + Optional("(" + Word(nums) + ")" + Stream)
        )
        testVal = Stream.parseString(testInput)

        self.assertParseResultsEquals(testVal, expected_list=expected)

    def testInfixNotationGrammarTest1(self):

        integer = Word(nums).setParseAction(lambda t: int(t[0]))
        variable = Word(alphas, exact=1)
        operand = integer | variable

        expop = Literal("^")
        signop = oneOf("+ -")
        multop = oneOf("* /")
        plusop = oneOf("+ -")
        factop = Literal("!")

        expr = infixNotation(
            operand,
            [
                (factop, 1, opAssoc.LEFT),
                (expop, 2, opAssoc.RIGHT),
                (signop, 1, opAssoc.RIGHT),
                (multop, 2, opAssoc.LEFT),
                (plusop, 2, opAssoc.LEFT),
            ],
        )

        test = [
            "9 + 2 + 3",
            "9 + 2 * 3",
            "(9 + 2) * 3",
            "(9 + -2) * 3",
            "(9 + --2) * 3",
            "(9 + -2) * 3^2^2",
            "(9! + -2) * 3^2^2",
            "M*X + B",
            "M*(X + B)",
            "1+2*-3^4*5+-+-6",
            "3!!",
        ]
        expected = [
            [[9, "+", 2], "+", 3],
            [9, "+", [2, "*", 3]],
            [[9, "+", 2], "*", 3],
            [[9, "+", ["-", 2]], "*", 3],
            [[9, "+", ["-", ["-", 2]]], "*", 3],
            [[9, "+", ["-", 2]], "*", [3, "^", [2, "^", 2]]],
            [[[9, "!"], "+", ["-", 2]], "*", [3, "^", [2, "^", 2]]],
            [["M", "*", "X"], "+", "B"],
            ["M", "*", ["X", "+", "B"]],
            [
                [1, "+", [[2, "*", ["-", [3, "^", 4]]], "*", 5]],
                "+",
                ["-", ["+", ["-", 6]]],
            ],
            [[3, "!"], "!"],
        ]
        for test_str, exp_list in zip(test, expected):
            result = expr.parseString(test_str)

            self.assertParseResultsEquals(
                result,
                expected_list=exp_list,
                msg="mismatched results for infixNotation: got %s, expected %s"
                % (result, exp_list),
            )

    def testInfixNotationGrammarTest2(self):

        boolVars = {"True": True, "False": False}

        class BoolOperand:
            reprsymbol = ""

            def __init__(self, t):
                self.args = t[0][0], t[2][0]

            def __str__(self):
                sep = " %s " % self.reprsymbol
                return "(" + sep.join(map(str, self.args)) + ")"

        class BoolAnd(BoolOperand):
            reprsymbol = "&"

            def __bool__(self):
                for a in self.args:
                    if isinstance(a, str):
                        v = boolVars[a]
                    else:
                        v = bool(a)
                    if not v:
                        return False
                return True

        class BoolOr(BoolOperand):
            reprsymbol = "|"

            def __bool__(self):
                for a in self.args:
                    if isinstance(a, str):
                        v = boolVars[a]
                    else:
                        v = bool(a)
                    if v:
                        return True
                return False

        class BoolNot(BoolOperand):
            def __init__(self, t):
                self.arg = t[1][0]

            def __str__(self):
                return "~" + str(self.arg)

            def __bool__(self):
                if isinstance(self.arg, str):
                    v = boolVars[self.arg]
                else:
                    v = bool(self.arg)
                return not v

        boolOperand = Group(oneOf("True False") | Word(alphas, max=1))
        boolExpr = infixNotation(
            boolOperand,
            [
                ("not", 1, opAssoc.RIGHT, BoolNot),
                ("and", 2, opAssoc.LEFT, BoolAnd),
                ("or", 2, opAssoc.LEFT, BoolOr),
            ],
        )
        test = [
            "True and False",
            "p and not q",
            "not not p",
            "not(p and q)",
            "q or not p and r",
            "q or not p or not r",
            "q or not (p and r)",
            "p or q or r",
            "p or q or r and False",
            "(p or q or r) and False",
        ]

        boolVars["p"] = True
        boolVars["q"] = False
        boolVars["r"] = True

        for t in test:
            res = boolExpr.parseString(t)

            expected = eval(t, {}, boolVars)
            self.assertEquals(expected, bool(res[0]))

    def testInfixNotationGrammarTest3(self):

        global count
        count = 0

        def evaluate_int(t):
            global count
            value = int(t[0])

            count += 1
            return value

        integer = Word(nums).setParseAction(evaluate_int)
        variable = Word(alphas, exact=1)
        operand = integer | variable

        expop = Literal("^")
        signop = oneOf("+ -")
        multop = oneOf("* /")
        plusop = oneOf("+ -")
        factop = Literal("!")

        expr = infixNotation(
            operand,
            [
                ("!", 1, opAssoc.LEFT),
                ("^", 2, opAssoc.LEFT),
                (signop, 1, opAssoc.RIGHT),
                (multop, 2, opAssoc.LEFT),
                (plusop, 2, opAssoc.LEFT),
            ],
        )

        test = ["9"]
        for t in test:
            count = 0
            expr.parseString(t)
            self.assertEqual(count, 1, "count evaluated too many times!")

    def testInfixNotationGrammarTest4(self):

        word = Word(alphas)

        def supLiteral(s):
            """Returns the suppressed literal s"""
            return Literal(s).suppress()

        def booleanExpr(atom):
            ops = [
                (supLiteral("!"), 1, opAssoc.RIGHT, lambda s, l, t: ["!", t[0][0]]),
                (oneOf("= !="), 2, opAssoc.LEFT,),
                (supLiteral("&"), 2, opAssoc.LEFT, lambda s, l, t: ["&", t[0]]),
                (supLiteral("|"), 2, opAssoc.LEFT, lambda s, l, t: ["|", t[0]]),
            ]
            return infixNotation(atom, ops)

        f = booleanExpr(word) + StringEnd()

        tests = [
            ("bar = foo", [["bar", "=", "foo"]]),
            (
                "bar = foo & baz = fee",
                ["&", [["bar", "=", "foo"], ["baz", "=", "fee"]]],
            ),
        ]
        for test, expected in tests:

            results = f.parseString(test)

            self.assertParseResultsEquals(results, expected_list=expected)

    def testInfixNotationGrammarTest5(self):

        expop = Literal("**")
        signop = oneOf("+ -")
        multop = oneOf("* /")
        plusop = oneOf("+ -")

        class ExprNode:
            def __init__(self, tokens):
                self.tokens = tokens[0]

            def eval(self):
                return None

        class NumberNode(ExprNode):
            def eval(self):
                return self.tokens

        class SignOp(ExprNode):
            def eval(self):
                mult = {"+": 1, "-": -1}[self.tokens[0]]
                return mult * self.tokens[1].eval()

        class BinOp(ExprNode):
            def eval(self):
                ret = self.tokens[0].eval()
                for op, operand in zip(self.tokens[1::2], self.tokens[2::2]):
                    ret = self.opn_map[op](ret, operand.eval())
                return ret

        class ExpOp(BinOp):
            opn_map = {"**": lambda a, b: b ** a}

        class MultOp(BinOp):

            opn_map = {"*": operator.mul, "/": operator.truediv}

        class AddOp(BinOp):

            opn_map = {"+": operator.add, "-": operator.sub}

        operand = number.setParseAction(NumberNode)
        expr = infixNotation(
            operand,
            [
                (expop, 2, opAssoc.LEFT, (lambda pr: [pr[0][::-1]], ExpOp)),
                (signop, 1, opAssoc.RIGHT, SignOp),
                (multop, 2, opAssoc.LEFT, MultOp),
                (plusop, 2, opAssoc.LEFT, AddOp),
            ],
        )

        tests = """\
            2+7
            2**3
            2**3**2
            3**9
            3**3**2
            """

        for t in tests.splitlines():
            t = t.strip()
            if not t:
                continue

            parsed = expr.parseString(t)
            eval_value = parsed[0].eval()
            self.assertEqual(
                eval_value,
                eval(t),
                "Error evaluating {!r}, expected {!r}, got {!r}".format(
                    t, eval(t), eval_value
                ),
            )

    def testParseResultsWithNamedTuple(self):

        expr = Literal("A")("Achar")
        expr.setParseAction(replaceWith(tuple(["A", "Z"])))

        res = expr.parseString("A")

        self.assertParseResultsEquals(
            res,
            expected_dict={"Achar": ("A", "Z")},
            msg="Failed accessing named results containing a tuple, "
            "got {!r}".format(res.Achar),
        )

    def testParseHTMLTags(self):
        test = """
            <BODY>
            <BODY BGCOLOR="#00FFCC">
            <BODY BGCOLOR="#00FFAA"/>
            <BODY BGCOLOR='#00FFBB' FGCOLOR=black>
            <BODY/>
            </BODY>
        """
        results = [
            ("startBody", False, "", ""),
            ("startBody", False, "#00FFCC", ""),
            ("startBody", True, "#00FFAA", ""),
            ("startBody", False, "#00FFBB", "black"),
            ("startBody", True, "", ""),
            ("endBody", False, "", ""),
        ]

        bodyStart, bodyEnd = makeHTMLTags("BODY")
        resIter = iter(results)
        for t, s, e in (bodyStart | bodyEnd).scanString(test):

            (expectedType, expectedEmpty, expectedBG, expectedFG) = next(resIter)

            if "startBody" in t:
                self.assertEqual(
                    bool(t.empty),
                    expectedEmpty,
                    "expected {} token, got {}".format(
                        expectedEmpty and "empty" or "not empty",
                        t.empty and "empty" or "not empty",
                    ),
                )
                self.assertEqual(
                    t.bgcolor,
                    expectedBG,
                    "failed to match BGCOLOR, expected {}, got {}".format(
                        expectedBG, t.bgcolor
                    ),
                )
                self.assertEqual(
                    t.fgcolor,
                    expectedFG,
                    "failed to match FGCOLOR, expected {}, got {}".format(
                        expectedFG, t.bgcolor
                    ),
                )
            elif "endBody" in t:

                pass
            else:
                Log.error("Bad")

    def testUpcaseDowncaseUnicode(self):

        a = "\u00bfC\u00f3mo esta usted?"
        if not JYTHON_ENV:
            ualphas = parsing_unicode.alphas
        else:
            ualphas = "".join(
                chr(i)
                for i in list(range(0xD800)) + list(range(0xE000, sys.maxunicode))
                if chr(i).isalpha()
            )
        uword = Word(ualphas).setParseAction(upcaseTokens)

        uword.searchString(a)

        uword = Word(ualphas).setParseAction(downcaseTokens)

        uword.searchString(a)

        kw = Keyword("mykey", caseless=True).setParseAction(upcaseTokens)("rname")
        ret = kw.parseString("mykey")

        self.assertEqual(
            ret.rname, "MYKEY", "failed to upcase with named result (parsing_common)"
        )

        kw = Keyword("MYKEY", caseless=True).setParseAction(downcaseTokens)("rname")
        ret = kw.parseString("mykey")

        self.assertEqual(ret.rname, "mykey", "failed to upcase with named result")

        if not IRON_PYTHON_ENV:
            # test html data
            html = "<TR class=maintxt bgColor=#ffffff> \
                <TD vAlign=top>Производитель, модель</TD> \
                <TD vAlign=top><STRONG>BenQ-Siemens CF61</STRONG></TD> \
            "  # .decode('utf-8')

            # 'Manufacturer, model
            text_manuf = "Производитель, модель"
            manufacturer = Literal(text_manuf)

            td_start, td_end = makeHTMLTags("td")
            manuf_body = (
                td_start.suppress()
                + manufacturer
                + SkipTo(td_end)("cells*")
                + td_end.suppress()
            )

            # ~ manuf_body.setDebug()

            # ~ for tokens in manuf_body.scanString(html):
            # ~ print(tokens)

    def testParseUsingRegex(self):

        signedInt = Regex(r"[-+][0-9]+")
        unsignedInt = Regex(r"[0-9]+")
        simpleString = Regex(r'("[^\"]*")|(\'[^\']*\')')
        namedGrouping = Regex(r'("(?P<content>[^\"]*)")')
        compiledRE = Regex(re.compile(r"[A-Z]+"))

        def testMatch(expression, instring, shouldPass, expectedString=None):
            if shouldPass:
                try:
                    result = expression.parseString(instring)
                    print(
                        "{} correctly matched {}".format(
                            repr(expression), repr(instring)
                        )
                    )
                    if expectedString != result[0]:

                        print(
                            "\tproduced %s instead of %s"
                            % (repr(result[0]), repr(expectedString))
                        )
                    return True
                except ParseException:
                    print(
                        "%s incorrectly failed to match %s"
                        % (repr(expression), repr(instring))
                    )
            else:
                try:
                    result = expression.parseString(instring)
                    print(
                        "{} incorrectly matched {}".format(
                            repr(expression), repr(instring)
                        )
                    )

                except ParseException:
                    print(
                        "%s correctly failed to match %s"
                        % (repr(expression), repr(instring))
                    )
                    return True
            return False

        # These should fail
        self.assertTrue(
            testMatch(signedInt, "1234 foo", False), "Re: (1) passed, expected fail"
        )
        self.assertTrue(
            testMatch(signedInt, "    +foo", False), "Re: (2) passed, expected fail"
        )
        self.assertTrue(
            testMatch(unsignedInt, "abc", False), "Re: (3) passed, expected fail"
        )
        self.assertTrue(
            testMatch(unsignedInt, "+123 foo", False), "Re: (4) passed, expected fail"
        )
        self.assertTrue(
            testMatch(simpleString, "foo", False), "Re: (5) passed, expected fail"
        )
        self.assertTrue(
            testMatch(simpleString, "\"foo bar'", False),
            "Re: (6) passed, expected fail",
        )
        self.assertTrue(
            testMatch(simpleString, "'foo bar\"", False),
            "Re: (7) passed, expected fail",
        )

        # These should pass
        self.assertTrue(
            testMatch(signedInt, "   +123", True, "+123"),
            "Re: (8) failed, expected pass",
        )
        self.assertTrue(
            testMatch(signedInt, "+123", True, "+123"), "Re: (9) failed, expected pass"
        )
        self.assertTrue(
            testMatch(signedInt, "+123 foo", True, "+123"),
            "Re: (10) failed, expected pass",
        )
        self.assertTrue(
            testMatch(signedInt, "-0 foo", True, "-0"), "Re: (11) failed, expected pass"
        )
        self.assertTrue(
            testMatch(unsignedInt, "123 foo", True, "123"),
            "Re: (12) failed, expected pass",
        )
        self.assertTrue(
            testMatch(unsignedInt, "0 foo", True, "0"), "Re: (13) failed, expected pass"
        )
        self.assertTrue(
            testMatch(simpleString, '"foo"', True, '"foo"'),
            "Re: (14) failed, expected pass",
        )
        self.assertTrue(
            testMatch(simpleString, "'foo bar' baz", True, "'foo bar'"),
            "Re: (15) failed, expected pass",
        )

        self.assertTrue(
            testMatch(compiledRE, "blah", False), "Re: (16) passed, expected fail"
        )
        self.assertTrue(
            testMatch(compiledRE, "BLAH", True, "BLAH"),
            "Re: (17) failed, expected pass",
        )

        self.assertTrue(
            testMatch(namedGrouping, '"foo bar" baz', True, '"foo bar"'),
            "Re: (16) failed, expected pass",
        )
        ret = namedGrouping.parseString('"zork" blah')

        self.assertEqual(ret.content, "zork", "named group lookup failed")
        self.assertEqual(
            ret[0],
            simpleString.parseString('"zork" blah')[0],
            "Regex not properly returning ParseResults for named vs. unnamed groups",
        )

        try:
            # ~ print "lets try an invalid RE"
            invRe = Regex("(\"[^\"]*\")|('[^']*'")
        except Exception as e:
            pass

        else:
            self.assertTrue(False, "failed to reject invalid RE")

        invRe = Regex("")

    def testRegexAsType(self):

        test_str = "sldkjfj 123 456 lsdfkj"

        expr = Regex(r"\w+ (\d+) (\d+) (\w+)", asGroupList=True)
        expected_group_list = [tuple(test_str.split()[1:])]
        result = expr.parseString(test_str)

        self.assertParseResultsEquals(
            result,
            expected_list=expected_group_list,
            msg="incorrect group list returned by Regex)",
        )

        expr = Regex(
            r"\w+ (?P<num1>\d+) (?P<num2>\d+) (?P<last_word>\w+)", asMatch=True
        )
        result = expr.parseString(test_str)

        self.assertEqual(
            result[0].groupdict(),
            {"num1": "123", "num2": "456", "last_word": "lsdfkj"},
            "invalid group dict from Regex(asMatch=True)",
        )
        self.assertEqual(
            result[0].groups(),
            expected_group_list[0],
            "incorrect group list returned by Regex(asMatch)",
        )

    def testRegexSub(self):

        expr = Regex(r"<title>").sub("'Richard III'")
        result = expr.transformString("This is the title: <title>")

        self.assertEqual(
            result,
            "This is the title: 'Richard III'",
            "incorrect Regex.sub result with simple string",
        )

        expr = Regex(r"([Hh]\d):\s*(.*)").sub(r"<\1>\2</\1>")
        result = expr.transformString(
            "h1: This is the main heading\nh2: This is the sub-heading"
        )

        self.assertEqual(
            result,
            "<h1>This is the main heading</h1>\n<h2>This is the sub-heading</h2>",
            "incorrect Regex.sub result with re string",
        )

        expr = Regex(r"([Hh]\d):\s*(.*)", asMatch=True).sub(r"<\1>\2</\1>")
        result = expr.transformString(
            "h1: This is the main heading\nh2: This is the sub-heading"
        )

        self.assertEqual(
            result,
            "<h1>This is the main heading</h1>\n<h2>This is the sub-heading</h2>",
            "incorrect Regex.sub result with re string",
        )

        expr = Regex(r"<(.*?)>").sub(lambda m: m.group(1).upper())
        result = expr.transformString("I want this in upcase: <what? what?>")

        self.assertEqual(
            result,
            "I want this in upcase: WHAT? WHAT?",
            "incorrect Regex.sub result with callable",
        )

        with TestCase.assertRaises(self, SyntaxError):
            Regex(r"<(.*?)>", asMatch=True).sub(lambda m: m.group(1).upper())

        with TestCase.assertRaises(self, SyntaxError):
            Regex(r"<(.*?)>", asGroupList=True).sub(lambda m: m.group(1).upper())

        with TestCase.assertRaises(self, SyntaxError):
            Regex(r"<(.*?)>", asGroupList=True).sub("")

    def testPrecededBy(self):

        num = Word(nums).setParseAction(lambda t: int(t[0]))
        interesting_num = PrecededBy(Char("abc")("prefix*")) + num
        semi_interesting_num = PrecededBy("_") + num
        crazy_num = PrecededBy(Word("^", "$%^")("prefix*"), 10) + num
        boring_num = ~PrecededBy(Char("abc_$%^" + nums)) + num
        very_boring_num = PrecededBy(WordStart()) + num
        finicky_num = PrecededBy(Word("^", "$%^"), retreat=3) + num

        s = "c384 b8324 _9293874 _293 404 $%^$^%$2939"

        for expr, expected_list, expected_dict in [
            (interesting_num, [384, 8324], {"prefix": ["c", "b"]}),
            (semi_interesting_num, [9293874, 293], {}),
            (boring_num, [404], {}),
            (crazy_num, [2939], {"prefix": ["^%$"]}),
            (finicky_num, [2939], {}),
            (very_boring_num, [404], {}),
        ]:
            # print(expr.searchString(s))
            result = sum(expr.searchString(s))

            self.assertParseResultsEquals(result, expected_list, expected_dict)

        # infinite loop test - from Issue #127
        string_test = "notworking"
        # negs = Or(['not', 'un'])('negs')
        negs_pb = PrecededBy("not", retreat=100)("negs_lb")
        # negs_pb = PrecededBy(negs, retreat=100)('negs_lb')
        pattern = (negs_pb + Literal("working"))("main")

        results = pattern.searchString(string_test)
        try:
            str(results)
        except RecursionError:
            self.assertTrue(False, "got maximum excursion limit exception")
        else:
            self.assertTrue(True, "got maximum excursion limit exception")

    def testCountedArray(self):

        testString = "2 5 7 6 0 1 2 3 4 5 0 3 5 4 3"

        integer = Word(nums).setParseAction(lambda t: int(t[0]))
        countedField = countedArray(integer)

        r = OneOrMore(countedField).parseString(testString)

        self.assertParseResultsEquals(
            r, expected_list=[[5, 7], [0, 1, 2, 3, 4, 5], [], [5, 4, 3]]
        )

    # addresses bug raised by Ralf Vosseler
    def testCountedArrayTest2(self):

        testString = "2 5 7 6 0 1 2 3 4 5 0 3 5 4 3"

        integer = Word(nums).setParseAction(lambda t: int(t[0]))
        countedField = countedArray(integer)

        dummy = Word("A")
        r = OneOrMore(dummy ^ countedField).parseString(testString)

        self.assertParseResultsEquals(
            r, expected_list=[[5, 7], [0, 1, 2, 3, 4, 5], [], [5, 4, 3]]
        )

    def testCountedArrayTest3(self):

        int_chars = "_" + alphas
        array_counter = Word(int_chars).setParseAction(lambda t: int_chars.index(t[0]))

        #             123456789012345678901234567890
        testString = "B 5 7 F 0 1 2 3 4 5 _ C 5 4 3"

        integer = Word(nums).setParseAction(lambda t: int(t[0]))
        countedField = countedArray(integer, intExpr=array_counter)

        r = OneOrMore(countedField).parseString(testString)

        self.assertParseResultsEquals(
            r, expected_list=[[5, 7], [0, 1, 2, 3, 4, 5], [], [5, 4, 3]]
        )

    def testLineStart(self):

        pass_tests = [
            """\
            AAA
            BBB
            """,
            """\
            AAA...
            BBB
            """,
        ]
        fail_tests = [
            """\
            AAA...
            ...BBB
            """,
            """\
            AAA  BBB
            """,
        ]

        # cleanup test strings
        pass_tests = [
            "\n".join(s.lstrip() for s in t.splitlines()).replace(".", " ")
            for t in pass_tests
        ]
        fail_tests = [
            "\n".join(s.lstrip() for s in t.splitlines()).replace(".", " ")
            for t in fail_tests
        ]

        test_patt = Word("A") - LineStart() + Word("B")
        test_patt.streamline()
        success = test_patt.runTests(pass_tests)[0]
        self.assertTrue(success, "failed LineStart passing tests (1)")

        success = test_patt.runTests(fail_tests, failureTests=True)[0]
        self.assertTrue(success, "failed LineStart failure mode tests (1)")

        with Timer(""):

            engine.CURRENT.set_whitespace(" ")

            test_patt = Word("A") - LineStart() + Word("B")

            # should fail the pass tests too, since \n is no longer valid whitespace and we aren't parsing for it
            success = test_patt.runTests(pass_tests, failureTests=True)[0]
            self.assertTrue(success, "failed LineStart passing tests (2)")

            success = test_patt.runTests(fail_tests, failureTests=True)[0]
            self.assertTrue(success, "failed LineStart failure mode tests (2)")

            test_patt = (
                Word("A")
                - LineEnd().suppress()
                + LineStart()
                + Word("B")
                + LineEnd().suppress()
            )
            test_patt.streamline()
            success = test_patt.runTests(pass_tests)[0]
            self.assertTrue(success, "failed LineStart passing tests (3)")

            success = test_patt.runTests(fail_tests, failureTests=True)[0]
            self.assertTrue(success, "failed LineStart failure mode tests (3)")

        test = """\
        AAA 1
        AAA 2

          AAA

        B AAA

        """

        test = dedent(test)

        for t, s, e in (LineStart() + "AAA").scanString(test):

            self.assertEqual(
                test[s], "A", "failed LineStart with insignificant newlines"
            )

        with Timer(""):
            engine.CURRENT.set_whitespace(" ")
            for t, s, e in (LineStart() + "AAA").scanString(test):

                self.assertEqual(
                    test[s], "A", "failed LineStart with insignificant newlines"
                )

    def testLineAndStringEnd(self):
        engine.CURRENT.set_whitespace("")
        NLs = OneOrMore(lineEnd)
        bnf1 = delimitedList(Word(alphanums), NLs)

        Engine()
        bnf2 = Word(alphanums) + stringEnd
        bnf3 = Word(alphanums) + SkipTo(stringEnd)
        tests = [
            ("testA\ntestB\ntestC\n", ["testA", "testB", "testC"]),
            ("testD\ntestE\ntestF", ["testD", "testE", "testF"]),
            ("a", ["a"]),
        ]

        for test, expected in tests:
            res1 = bnf1.parseString(test)

            self.assertParseResultsEquals(
                res1,
                expected_list=expected
            )

            res2 = bnf2.searchString(test)[0]

            self.assertParseResultsEquals(
                res2,
                expected_list=expected[-1:]
            )

            res3 = bnf3.parseString(test)
            first = res3[0]
            rest = coalesce(res3[1], "")

            self.assertEqual(
                rest,
                test[len(first) + 1 :]
            )

        k = Regex(r"a+", flags=re.S + re.M)
        k = k.parseWithTabs()
        k = k.leaveWhitespace()

        tests = [
            (r"aaa", ["aaa"]),
            (r"\naaa", None),
            (r"a\naa", None),
            (r"aaa\n", None),
        ]
        for i, (src, expected) in enumerate(tests):

            if expected is None:
                with self.assertRaisesParseException():
                    k.parseString(src, parseAll=True)
            else:
                res = k.parseString(src, parseAll=True)
                self.assertParseResultsEquals(
                    res, expected, msg="Failed on parseAll=True test %d" % i
                )

    def testVariableParseActionArgs(self):
        pa3 = lambda s, l, t: t
        pa2 = lambda l, t: t
        pa1 = lambda t: t
        pa0 = lambda: None

        class Callable3:
            def __call__(self, s, l, t):
                return t

        class Callable2:
            def __call__(self, l, t):
                return t

        class Callable1:
            def __call__(self, t):
                return t

        class Callable0:
            def __call__(self):
                return

        class CallableS3:
            @staticmethod
            def __call__(s, l, t):
                return t

        class CallableS2:
            @staticmethod
            def __call__(l, t):
                return t

        class CallableS1:
            @staticmethod
            def __call__(t):
                return t

        class CallableS0:
            @staticmethod
            def __call__():
                return

        class CallableC3:
            @classmethod
            def __call__(cls, s, l, t):
                return t

        class CallableC2:
            @classmethod
            def __call__(cls, l, t):
                return t

        class CallableC1:
            @classmethod
            def __call__(cls, t):
                return t

        class CallableC0:
            @classmethod
            def __call__(cls):
                return

        class parseActionHolder:
            @staticmethod
            def pa3(s, l, t):
                return t

            @staticmethod
            def pa2(l, t):
                return t

            @staticmethod
            def pa1(t):
                return t

            @staticmethod
            def pa0():
                return

        def paArgs(*args):

            return args[2]

        class ClassAsPA0:
            def __init__(self):
                pass

            def __str__(self):
                return "A"

        class ClassAsPA1:
            def __init__(self, t):

                self.t = t

            def __str__(self):
                return self.t[0]

        class ClassAsPA2:
            def __init__(self, l, t):
                self.t = t

            def __str__(self):
                return self.t[0]

        class ClassAsPA3:
            def __init__(self, s, l, t):
                self.t = t

            def __str__(self):
                return self.t[0]

        class ClassAsPAStarNew(tuple):
            def __new__(cls, *args):

                return tuple.__new__(cls, *args[2])

            def __str__(self):
                return "".join(self)

        A = Literal("A").setParseAction(pa0)
        B = Literal("B").setParseAction(pa1)
        C = Literal("C").setParseAction(pa2)
        D = Literal("D").setParseAction(pa3)
        E = Literal("E").setParseAction(Callable0())
        F = Literal("F").setParseAction(Callable1())
        G = Literal("G").setParseAction(Callable2())
        H = Literal("H").setParseAction(Callable3())
        I = Literal("I").setParseAction(CallableS0())
        J = Literal("J").setParseAction(CallableS1())
        K = Literal("K").setParseAction(CallableS2())
        L = Literal("L").setParseAction(CallableS3())
        M = Literal("M").setParseAction(CallableC0())
        N = Literal("N").setParseAction(CallableC1())
        O = Literal("O").setParseAction(CallableC2())
        P = Literal("P").setParseAction(CallableC3())
        Q = Literal("Q").setParseAction(paArgs)
        R = Literal("R").setParseAction(parseActionHolder.pa3)
        S = Literal("S").setParseAction(parseActionHolder.pa2)
        T = Literal("T").setParseAction(parseActionHolder.pa1)
        U = Literal("U").setParseAction(parseActionHolder.pa0)
        V = Literal("V")

        gg = OneOrMore(
            A
            | C
            | D
            | E
            | F
            | G
            | H
            | I
            | J
            | K
            | L
            | M
            | N
            | O
            | P
            | Q
            | R
            | S
            | U
            | V
            | B
            | T
        )
        testString = "VUTSRQPONMLKJIHGFEDCBA"
        res = gg.parseString(testString)

        self.assertParseResultsEquals(
            res,
            expected_list=list(testString),
            msg="Failed to parse using variable length parse actions",
        )

        A = Literal("A").setParseAction(ClassAsPA0)
        B = Literal("B").setParseAction(ClassAsPA1)
        C = Literal("C").setParseAction(ClassAsPA2)
        D = Literal("D").setParseAction(ClassAsPA3)
        E = Literal("E").setParseAction(ClassAsPAStarNew)

        gg = OneOrMore(
            A
            | B
            | C
            | D
            | E
            | F
            | G
            | H
            | I
            | J
            | K
            | L
            | M
            | N
            | O
            | P
            | Q
            | R
            | S
            | T
            | U
            | V
        )
        testString = "VUTSRQPONMLKJIHGFEDCBA"
        res = gg.parseString(testString)

        self.assertEqual(
            list(map(str, res)),
            list(testString),
            "Failed to parse using variable length parse actions "
            "using class constructors as parse actions",
        )

    def testSingleArgException(self):

        msg = ""
        raisedMsg = ""
        testMessage = "just one arg"
        try:
            raise ParseFatalException(testMessage)
        except ParseBaseException as pbe:

            raisedMsg = pbe.msg
            self.assertEqual(
                raisedMsg, testMessage, "Failed to get correct exception message"
            )

    def testOriginalTextFor(self):
        def rfn(t):
            return "%s:%d" % (t.src, len("".join(t)))

        makeHTMLStartTag = lambda tag: originalTextFor(
            makeHTMLTags(tag)[0], asString=False
        )

        # use the lambda, Luke
        start = makeHTMLStartTag("IMG")

        # don't replace our fancy parse action with rfn,
        # append rfn to the list of parse actions
        start.addParseAction(rfn)

        text = """_<img src="images/cal.png"
            alt="cal image" width="16" height="15">_"""
        s = start.transformString(text)
        self.assertTrue(
            s.startswith("_images/cal.png:"), "failed to preserve input s properly"
        )
        self.assertTrue(
            s.endswith("77_"), "failed to return full original text properly"
        )

        tag_fields = makeHTMLStartTag("IMG").searchString(text)[0]
        if VERBOSE:
            self.assertEqual(
                sorted(tag_fields.keys()),
                ["alt", "empty", "height", "src", "startImg", "tag", "width"],
                "failed to preserve results names in originalTextFor",
            )

    def testPackratParsingCacheCopy(self):

        integer = Word(nums).set_parser_name("integer")
        id = Word(alphas + "_", alphanums + "_")
        simpleType = Literal("int")
        arrayType = simpleType + ("[" + delimitedList(integer) + "]")[...]
        varType = arrayType | simpleType
        varDec = varType + delimitedList(id + Optional("=" + integer)) + ";"

        codeBlock = Literal("{}")

        funcDef = (
            Optional(varType | "void")
            + id
            + "("
            + (delimitedList(varType + id) | "void" | empty)
            + ")"
            + codeBlock
        )

        program = varDec | funcDef
        input = "int f(){}"
        results = program.parseString(input)

        self.assertEqual(
            results, ["int", "f", "(", ")", "{}"], "Error in packrat parsing"
        )

    def testPackratParsingCacheCopyTest2(self):

        DO, AA = list(map(Keyword, "DO AA".split()))
        LPAR, RPAR = list(map(Suppress, "()"))
        identifier = ~AA + Word("Z")

        function_name = identifier.copy()
        # ~ function_name = ~AA + Word("Z")  #identifier.copy()
        expr = Forward().set_parser_name("expr")
        expr << (
            Group(
                function_name + LPAR + Optional(delimitedList(expr)) + RPAR
            ).set_parser_name("functionCall")
            | identifier.set_parser_name("ident")  # .setDebug()#.setBreak()
        )

        stmt = DO + Group(delimitedList(identifier + ".*" | expr))
        result = stmt.parseString("DO Z")

        self.assertEqual(
            len(result[1]), 1, "packrat parsing is duplicating And term exprs"
        )

    def testWithAttributeParseAction(self):
        """
        This unit test checks withAttribute in these ways:

        * Argument forms as keywords and tuples
        * Selecting matching tags by attribute
        * Case-insensitive attribute matching
        * Correctly matching tags having the attribute, and rejecting tags not having the attribute

        (Unit test written by voigts as part of the Google Highly Open Participation Contest)
        """

        data = """
        <a>1</a>
        <a b="x">2</a>
        <a B="x">3</a>
        <a b="X">4</a>
        <a b="y">5</a>
        <a class="boo">8</ a>
        """
        tagStart, tagEnd = makeHTMLTags("a")

        expr = tagStart + Word(nums)("value") + tagEnd

        expected = (
            [
                ["a", ["b", "x"], False, "2", "</a>"],
                ["a", ["b", "x"], False, "3", "</a>"],
            ],
            [
                ["a", ["b", "x"], False, "2", "</a>"],
                ["a", ["b", "x"], False, "3", "</a>"],
            ],
            [["a", ["class", "boo"], False, "8", "</a>"]],
        )

        for attrib, exp in zip(
            [
                withAttribute(b="x"),
                # withAttribute(B="x"),
                withAttribute(("b", "x")),
                # withAttribute(("B", "x")),
                withClass("boo"),
            ],
            expected,
        ):

            tagStart.setParseAction(attrib)
            result = expr.searchString(data)

            self.assertEqual(
                result,
                exp,
                "Failed test, expected {}, got {}".format(expected, result),
            )

    def testNestedExpressions(self):
        """
        This unit test checks nestedExpr in these ways:
        - use of default arguments
        - use of non-default arguments (such as a mo_parsing-defined comment
          expression in place of quotedString)
        - use of a custom content expression
        - use of a mo_parsing expression for opener and closer is *OPTIONAL*
        - use of input data containing nesting delimiters
        - correct grouping of parsed tokens according to nesting of opening
          and closing delimiters in the input string

        (Unit test written by christoph... as part of the Google Highly Open Participation Contest)
        """

        # All defaults. Straight out of the example script. Also, qualifies for
        # the bonus: note the fact that (Z | (E^F) & D) is not parsed :-).
        # Tests for bug fixed in 1.4.10

        teststring = "((ax + by)*C) (Z | (E^F) & D)"

        expr = nestedExpr()

        expected = [["ax", "+", "by"], "*C"]
        result = expr.parseString(teststring)

        self.assertEqual(result, expected, "Defaults didn't work. That's a bad sign.")

        # Going through non-defaults, one by one; trying to think of anything
        # odd that might not be properly handled.

        # Change opener
        teststring = "[[ ax + by)*C)"
        expected = [["ax", "+", "by"], "*C"]
        expr = nestedExpr(opener="[")
        result = expr.parseString(teststring)

        self.assertEqual(result, expected, "Non-default opener didn't work.")

        # Change closer
        teststring = "((ax + by]*C]"
        expected = [["ax", "+", "by"], "*C"]
        expr = nestedExpr(closer="]")
        result = expr.parseString(teststring)

        self.assertEqual(result, expected, "Non-default closer didn't work.")

        # #Multicharacter opener, closer
        # opener = "bar"
        # closer = "baz"
        opener, closer = map(Literal, ["bar", "baz"])
        expr = nestedExpr(opener, closer, content=Regex(r"([^b ]|b(?!a)|ba(?![rz]))+"))

        teststring = "barbar ax + bybaz*Cbaz"
        expected = [["ax", "+", "by"], "*C"]
        # expr = nestedExpr(opener, closer)
        result = expr.parseString(teststring)

        self.assertEqual(
            result, expected, "Multicharacter opener and closer didn't work."
        )

        # Lisp-ish comments
        comment = Regex(r";;.*")
        teststring = """
        (let ((greeting "Hello, world!")) ;;(foo bar
           (display greeting))
        """

        expected = [
            "let",
            [["greeting", '"Hello,', 'world!"']],
            ";;(foo bar",
            ["display", "greeting"],
        ]

        expr = nestedExpr(ignoreExpr=comment)
        result = expr.parseString(teststring)

        self.assertEqual(
            result, expected, 'Lisp-ish comments (";; <...> $") didn\'t work.'
        )

        # Lisp-ish comments, using a standard bit of mo_parsing, and an Or.
        comment = ";;" + restOfLine
        teststring = """
        (let ((greeting "Hello, )world!")) ;;(foo bar
           (display greeting))
        """

        expected = [
            "let",
            [["greeting", '"Hello, )world!"']],
            ";;",
            "(foo bar",
            ["display", "greeting"],
        ]
        expr = nestedExpr(ignoreExpr=(comment ^ quotedString))
        result = expr.parseString(teststring)

        self.assertEqual(
            result,
            expected,
            'Lisp-ish comments (";; <...> $") and quoted strings didn\'t work.',
        )

    def testWordExclude(self):
        allButPunc = Word(printables, excludeChars=".,:;-_!?")
        test = "Hello, Mr. Ed, it's Wilbur!"
        result = allButPunc.searchString(test)

        self.assertEqual(
            result,
            [["Hello"], ["Mr"], ["Ed"], ["it's"], ["Wilbur"]],
            "failed WordExcludeTest",
        )

    def testParseAll(self):

        testExpr = Word("A")

        tests = [
            ("AAAAA", False, True),
            ("AAAAA", True, True),
            ("AAABB", False, True),
            ("AAABB", True, False),
        ]
        for s, parseAllFlag, shouldSucceed in tests:
            try:
                print(
                    "'{}' parseAll={} (shouldSucceed={})".format(
                        s, parseAllFlag, shouldSucceed
                    )
                )
                testExpr.parseString(s, parseAll=parseAllFlag)
                self.assertTrue(
                    shouldSucceed, "successfully parsed when should have failed"
                )
            except ParseException as pe:

                self.assertFalse(
                    shouldSucceed, "failed to parse when should have succeeded"
                )

        # add test for trailing comments
        engine.CURRENT.add_ignore(cppStyleComment)

        tests = [
            ("AAAAA //blah", False, True),
            ("AAAAA //blah", True, True),
            ("AAABB //blah", False, True),
            ("AAABB //blah", True, False),
        ]
        for s, parseAllFlag, shouldSucceed in tests:
            try:
                print(
                    "'{}' parseAll={} (shouldSucceed={})".format(
                        s, parseAllFlag, shouldSucceed
                    )
                )
                testExpr.parseString(s, parseAll=parseAllFlag)
                self.assertTrue(
                    shouldSucceed, "successfully parsed when should have failed"
                )
            except ParseException as pe:

                self.assertFalse(
                    shouldSucceed, "failed to parse when should have succeeded"
                )

        # add test with very long expression string
        # testExpr = MatchFirst([Literal(c) for c in printables if c != 'B'])[1, ...]
        anything_but_an_f = OneOrMore(
            MatchFirst([Literal(c) for c in printables if c != "f"])
        )
        testExpr = Word("012") + anything_but_an_f

        tests = [
            ("00aab", False, True),
            ("00aab", True, True),
            ("00aaf", False, True),
            ("00aaf", True, False),
        ]
        for s, parseAllFlag, shouldSucceed in tests:
            try:
                print(
                    "'{}' parseAll={} (shouldSucceed={})".format(
                        s, parseAllFlag, shouldSucceed
                    )
                )
                testExpr.parseString(s, parseAll=parseAllFlag)
                self.assertTrue(
                    shouldSucceed, "successfully parsed when should have failed"
                )
            except ParseException as pe:

                self.assertFalse(
                    shouldSucceed, "failed to parse when should have succeeded"
                )

    def testGreedyQuotedStrings(self):
        src = """\
           "string1", "strin""g2"
           'string1', 'string2'
           ^string1^, ^string2^
           <string1>, <string2>"""

        testExprs = (
            sglQuotedString,
            dblQuotedString,
            quotedString,
            QuotedString('"', escQuote='""'),
            QuotedString("'", escQuote="''"),
            QuotedString("^"),
            QuotedString("<", endQuoteChar=">"),
        )
        for expr in testExprs:
            strs = delimitedList(expr).searchString(src)

            self.assertTrue(
                bool(strs), "no matches found for test expression '%s'" % expr
            )
            for lst in strs:
                self.assertEqual(
                    len(lst), 2, "invalid match found for test expression '%s'" % expr
                )

        src = """'ms1',1,0,'2009-12-22','2009-12-22 10:41:22') ON DUPLICATE KEY UPDATE sent_count = sent_count + 1, mtime = '2009-12-22 10:41:22';"""
        tok_sql_quoted_value = QuotedString(
            "'", "\\", "''", True, False
        ) ^ QuotedString('"', "\\", '""', True, False)
        tok_sql_computed_value = Word(nums)
        tok_sql_identifier = Word(alphas)

        val = tok_sql_quoted_value | tok_sql_computed_value | tok_sql_identifier
        vals = delimitedList(val)

        self.assertEqual(
            len(vals.parseString(src)), 5, "error in greedy quote escaping"
        )

    def testWordBoundaryExpressions(self):

        ws = WordStart()
        we = WordEnd()
        vowel = oneOf(list("AEIOUY"))
        consonant = oneOf(list("BCDFGHJKLMNPQRSTVWXZ"))

        leadingVowel = ws + vowel
        trailingVowel = vowel + we
        leadingConsonant = ws + consonant
        trailingConsonant = consonant + we
        internalVowel = ~ws + vowel + ~we

        bnf = leadingVowel | trailingVowel

        tests = """\
        ABC DEF GHI
          JKL MNO PQR
        STU VWX YZ  """.splitlines()
        tests.append("\n".join(tests))

        expectedResult = [
            [["D", "G"], ["A"], ["C", "F"], ["I"], ["E"], ["A", "I"]],
            [["J", "M", "P"], [], ["L", "R"], ["O"], [], ["O"]],
            [["S", "V"], ["Y"], ["X", "Z"], ["U"], [], ["U", "Y"]],
            [
                ["D", "G", "J", "M", "P", "S", "V"],
                ["A", "Y"],
                ["C", "F", "L", "R", "X", "Z"],
                ["I", "O", "U"],
                ["E"],
                ["A", "I", "O", "U", "Y"],
            ],
        ]

        for t, expected in zip(tests, expectedResult):

            results = [
                flatten(e.searchString(t))
                for e in [
                    leadingConsonant,
                    leadingVowel,
                    trailingConsonant,
                    trailingVowel,
                    internalVowel,
                    bnf,
                ]
            ]

            self.assertEqual(
                results,
                expected,
                "Failed WordBoundaryTest, expected {}, got {}".format(
                    expected, results
                ),
            )

    def testRequiredEach(self):

        parser = Keyword("bam") & Keyword("boo")
        try:
            res1 = parser.parseString("bam boo")

            res2 = parser.parseString("boo bam")

        except ParseException:
            failed = True
        else:
            failed = False
            self.assertFalse(failed, "invalid logic in Each")

            self.assertEqual(
                set(res1),
                set(res2),
                "Failed RequiredEachTest, expected "
                + str(res1)
                + " and "
                + str(res2)
                + "to contain same words in any order",
            )

    def testOptionalEachTest1(self):

        the_input = "Major Tal Weiss"
        parser1 = (Optional("Tal") + Optional("Weiss")) & Keyword("Major")
        parser2 = Optional(Optional("Tal") + Optional("Weiss")) & Keyword("Major")
        p1res = parser1.parseString(the_input)
        p2res = parser2.parseString(the_input)
        self.assertEqual(
            p1res,
            p2res,
            "Each failed to match with nested Optionals, "
            + str(p1res)
            + " should match "
            + str(p2res),
        )

    def testOptionalEachTest2(self):

        word = Word(alphanums + "_").set_parser_name("word")
        with_stmt = Group(
            "with" + OneOrMore(Group(word("key") + "=" + word("value")))("overrides")
        )
        using_stmt = Group("using" + Regex("id-[0-9a-f]{8}")("id"))
        modifiers = Optional(with_stmt("with_stmt")) & Optional(
            using_stmt("using_stmt")
        )

        result = modifiers.parseString(
            "with foo=bar bing=baz using id-deadbeef", parseAll=True
        )
        expecting = {
            "with_stmt": {
                "overrides": [
                    {"key": "foo", "value": "bar"},
                    {"key": "bing", "value": "baz"},
                ]
            },
            "using_stmt": {"id": "id-deadbeef"},
        }
        self.assertEqual(result, expecting)

        with self.assertRaisesParseException():
            result = modifiers.parseString(
                "with foo=bar bing=baz using id-deadbeef using id-feedfeed", parseAll=True
            )

    def testOptionalEachTest3(self):

        foo = Literal("foo")
        bar = Literal("bar")

        openBrace = Suppress(Literal("{"))
        closeBrace = Suppress(Literal("}"))

        exp = openBrace + (foo[1, ...]("foo") & bar[...]("bar")) + closeBrace

        tests = """\
            {foo}
            {bar foo bar foo bar foo}
            """.splitlines()
        for test in tests:
            test = test.strip()
            if not test:
                continue
            result = exp.parseString(test)

            self.assertEqual(
                result,
                test.strip("{}").split(),
                "failed to parse Each expression %r" % test,
            )

        with TestCase.assertRaises(self, ParseException):
            exp.parseString("{bar}")

    def testOptionalEachTest4(self):

        expr = (~iso8601_date + integer("id")) & (Group(iso8601_date)("date*")[...])

        expr.runTests(
            """
            1999-12-31 100 2001-01-01
            42
            """
        )

    @skip("Please add tracking of right-most error, so these work")
    def testEachWithParseFatalException(self):
        option_expr = Keyword("options") - "(" + integer + ")"
        step_expr1 = Keyword("step") - "(" + integer + ")"
        step_expr2 = Keyword("step") - "(" + integer + "Z" + ")"
        step_expr = step_expr1 ^ step_expr2
        parser = option_expr & step_expr[...]
        tests = [
            (
                # this test fails because the step_expr[...] means ZeroOrMore
                # so "step(A)" does not match, which means zero matches
                # resulting in an error expecting an early end-of-line
                # 01234567890123456789
                "options(100) step(A)",
                "Expected integer, found 'A'  (at char 18), (line:1, col:19)",
            ),
            (
                "step(A) options(100)",
                "Expected integer, found 'A'  (at char 5), (line:1, col:6)",
            ),
            (
                "options(100) step(100A)",
                """Expected "Z", found 'A'  (at char 21), (line:1, col:22)""",
            ),
            (
                "options(100) step(22) step(100ZA)",
                """Expected ")", found 'A'  (at char 31), (line:1, col:32)""",
            ),
        ]

        success, output = parser.runTests((t[0] for t in tests), failureTests=True)
        for (_, result), (test_str, expected) in zip(output, tests):
            self.assertEqual(
                expected,
                str(result),
                "incorrect exception raised for test string {!r}".format(test_str),
            )

    def testSumParseResults(self):

        samplestr1 = "garbage;DOB 10-10-2010;more garbage\nID PARI12345678;more garbage"
        samplestr2 = "garbage;ID PARI12345678;more garbage\nDOB 10-10-2010;more garbage"
        samplestr3 = "garbage;DOB 10-10-2010"
        samplestr4 = "garbage;ID PARI12345678;more garbage- I am cool"

        res1 = "ID:PARI12345678 DOB:10-10-2010 INFO:"
        res2 = "ID:PARI12345678 DOB:10-10-2010 INFO:"
        res3 = "ID: DOB:10-10-2010 INFO:"
        res4 = "ID:PARI12345678 DOB: INFO: I am cool"

        dob_ref = "DOB" + Regex(r"\d{2}-\d{2}-\d{4}")("dob")
        id_ref = "ID" + Word(alphanums, exact=12)("id")
        info_ref = "-" + restOfLine("info")

        person_data = dob_ref | id_ref | info_ref

        tests = (
            samplestr1,
            samplestr2,
            samplestr3,
            samplestr4,
        )
        results = (
            res1,
            res2,
            res3,
            res4,
        )
        for test, expected in zip(tests, results):
            person = sum(person_data.searchString(test))
            result = "ID:{} DOB:{} INFO:{}".format(person.id, person.dob, person.info)
            self.assertEqual(
                expected,
                result,
                "Failed to parse '{}' correctly, \nexpected '{}', got '{}'".format(
                    test, expected, result
                ),
            )

    def testMarkInputLine(self):

        samplestr1 = "DOB 100-10-2010;more garbage\nID PARI12345678;more garbage"

        dob_ref = "DOB" + Regex(r"\d{2}-\d{2}-\d{4}")("dob")

        try:
            res = dob_ref.parseString(samplestr1)
        except ParseException as pe:
            outstr = pe.markInputline()

            self.assertEqual(
                outstr,
                "DOB >!<100-10-2010;more garbage",
                "did not properly create marked input line",
            )
        else:
            self.assertEqual(
                False, "test construction failed - should have raised an exception"
            )

    def testLocatedExpr(self):

        #             012345678901234567890123456789012345678901234567890
        samplestr1 = "DOB 10-10-2010;more garbage;ID PARI12345678  ;more garbage"

        id_ref = locatedExpr("ID" + Word(alphanums, exact=12)("id"))

        res = id_ref.searchString(samplestr1)[0][0]

        self.assertEqual(
            samplestr1[
                res["locn_start"] : res["locn_end"]
            ].strip(),  # CURRENTLY CAN NOT GET END, ONLY GET BEGINNING OF NEXT TOKEN
            "ID PARI12345678",
            "incorrect location calculation",
        )

    def testAddCondition(self):
        numParser = (
            Word(nums)
            .addParseAction(lambda s, l, t: int(t[0]))
            .addCondition(lambda s, l, t: t[0] % 2)
            .addCondition(lambda s, l, t: t[0] >= 7)
        )

        result = numParser.searchString("1 2 3 4 5 6 7 8 9 10")

        self.assertEqual(result, [[7], [9]], "failed to properly process conditions")

        numParser = Word(nums).addParseAction(lambda s, l, t: int(t[0]))
        rangeParser = numParser("from_") + Suppress("-") + numParser("to")

        result = rangeParser.searchString("1-4 2-4 4-3 5 6 7 8 9 10")

        self.assertEqual(
            result, [[1, 4], [2, 4], [4, 3]], "failed to properly process conditions",
        )

        rangeParser = rangeParser.addCondition(
            lambda t: t["to"] > t["from_"], message="from must be <= to", fatal=False
        )
        result = rangeParser.searchString("1-4 2-4 4-3 5 6 7 8 9 10")

        self.assertEqual(
            result, [[1, 4], [2, 4]], "failed to properly process conditions"
        )

        rangeParser = numParser("from_") + Suppress("-") + numParser("to")
        rangeParser = rangeParser.addCondition(
            lambda t: t["to"] > t["from_"], message="from must be <= to", fatal=True
        )
        with TestCase.assertRaises(self, Exception):
            rangeParser.searchString("1-4 2-4 4-3 5 6 7 8 9 10")

    def testPatientOr(self):

        # Two expressions and a input string which could - syntactically - be matched against
        # both expressions. The "Literal" expression is considered invalid though, so this PE
        # should always detect the "Word" expression.
        def validate(token):
            if token[0] == "def":
                raise ParseException("signalling invalid token")
            return token

        a = Word("de").set_parser_name("Word")  # .setDebug()
        b = (
            Literal("def").set_parser_name("Literal").setParseAction(validate)
        )  # .setDebug()
        c = Literal("d").set_parser_name("d")  # .setDebug()

        # The "Literal" expressions's ParseAction is not executed directly after syntactically
        # detecting the "Literal" Expression but only after the Or-decision has been made
        # (which is too late)...
        try:
            result = (a ^ b ^ c).parseString("def")
            self.assertEqual(
                result, ["de"], "failed to select longest match, chose %s" % result,
            )
        except ParseException:
            failed = True
        else:
            failed = False
        self.assertFalse(
            failed,
            "invalid logic in Or, fails on longest match with exception in parse action",
        )

        # from issue #93
        word = Word(alphas).set_parser_name("word")
        word_1 = (
            Word(alphas)
            .set_parser_name("word_1")
            .addCondition(lambda t: len(t[0]) == 1)
        )

        a = word + (word_1 + word ^ word)
        b = word * 3
        c = a ^ b
        c.streamline()

        test_string = "foo bar temp"
        result = c.parseString(test_string)

        self.assertEqual(result, test_string.split(), "failed to match longest choice")

    def testEachWithOptionalWithResultsName(self):
        result = (Optional("foo")("one") & Optional("bar")("two")).parseString(
            "bar foo"
        )

        self.assertEqual(sorted(result.keys()), ["one", "two"])

    def testUnicodeExpression(self):
        z = "a" | Literal("\u1111")
        z.streamline()
        try:
            z.parseString("b")
        except ParseException as pe:
            self.assertEqual(
                pe.msg,
                r"""Expected {"a"} | {"ᄑ"}""",
                "Invalid error message raised, got %r" % pe.msg,
            )

    def testSetName(self):
        a = oneOf("a b c")
        b = oneOf("d e f")
        arith_expr = infixNotation(
            Word(nums),
            [(oneOf("* /"), 2, opAssoc.LEFT), (oneOf("+ -"), 2, opAssoc.LEFT),],
        )
        arith_expr2 = infixNotation(Word(nums), [(("?", ":"), 3, opAssoc.LEFT),])
        recursive = Forward()
        recursive <<= a + (b + recursive)[...]

        self.assertEqual(str(a), "a | b | c")
        self.assertEqual(str(b), "d | e | f")
        self.assertEqual(str((a | b)), "{a | b | c} | {d | e | f}")
        self.assertEqual(str(arith_expr), "Forward: {+ | - term} | {* | / term}")
        self.assertEqual(str(arith_expr.expr), "{+ | - term} | {* | / term}")
        self.assertEqual(
            str(arith_expr2),
            'Forward: {?: term} | {{W:(0123...)} | {{{"(" Forward: ...} ")"}}}',
        )
        self.assertEqual(
            str(arith_expr2.expr),
            '{?: term} | {{W:(0123...)} | {{{"(" Forward: {?: term} | {{W:(0123...)} | {{{"(" Forward: ...} ")"}}}} ")"}}}',
        )
        self.assertEqual(
            str(recursive), "Forward: {a | b | c [{d | e | f Forward: ...}]...}"
        )
        self.assertEqual(
            str(delimitedList(Word(nums).set_parser_name("int"))), "int [, int]..."
        )
        self.assertEqual(
            str(countedArray(Word(nums).set_parser_name("int"))), "(len) int..."
        )
        self.assertEqual(str(nestedExpr()), "nested () expression")
        self.assertEqual(str(makeHTMLTags("Z")), "(<Z>, </Z>)")
        self.assertEqual(str((anyOpenTag, anyCloseTag)), "(<any tag>, </any tag>)")
        self.assertEqual(str(commonHTMLEntity), "common HTML entity")
        self.assertEqual(
            str(
                commonHTMLEntity.setParseAction(replaceHTMLEntity).transformString(
                    "lsdjkf &lt;lsdjkf&gt;&amp;&apos;&quot;&xyzzy;"
                )
            ),
            "lsdjkf <lsdjkf>&'\"&xyzzy;",
        )

    def testTrimArityExceptionMasking(self):
        invalid_message = "<lambda>() missing 1 required positional argument: 't'"
        try:
            Word("a").setParseAction(lambda t: t[0] + 1).parseString("aaa")
        except Exception as e:
            exc_msg = str(e)
            self.assertNotEqual(
                exc_msg,
                invalid_message,
                "failed to catch TypeError thrown in _trim_arity",
            )

    def testTrimArityExceptionMaskingTest2(self):
        # construct deep call tree
        def A():

            traceback.print_stack(limit=2)
            invalid_message = "<lambda>() missing 1 required positional argument: 't'"
            try:
                Word("a").setParseAction(lambda t: t[0] + 1).parseString("aaa")
            except Exception as e:
                exc_msg = str(e)
                self.assertNotEqual(
                    exc_msg,
                    invalid_message,
                    "failed to catch TypeError thrown in _trim_arity",
                )

        def B():
            A()

        def C():
            B()

        def D():
            C()

        def E():
            D()

        def F():
            E()

        def G():
            F()

        def H():
            G()

        def J():
            H()

        def K():
            J()

        K()

    def testClearParseActions(self):
        realnum = real
        self.assertEqual(
            realnum.parseString("3.14159")[0],
            3.14159,
            "failed basic real number parsing",
        )

        # clear parse action that converts to float
        realnum.setParseAction(None)
        self.assertEqual(
            realnum.parseString("3.14159")[0], "3.14159", "failed clearing parse action"
        )

        # add a new parse action that tests if a '.' is prsent
        realnum.addParseAction(lambda t: "." in t[0])
        self.assertEqual(
            realnum.parseString("3.14159")[0],
            True,
            "failed setting new parse action after clearing parse action",
        )

    def testOneOrMoreStop(self):
        test = "BEGIN aaa bbb ccc END"
        BEGIN, END = map(Keyword, ["BEGIN", "END"])
        body_word = Word(alphas).set_parser_name("word")
        for ender in (END, "END", CaselessKeyword("END")):
            expr = BEGIN + OneOrMore(body_word, stopOn=ender) + END
            result = expr.parseString(test)
            self.assertEqual(
                result,
                test.split(),
                "Did not successfully stop on ending expression %r" % ender,
            )

            expr = BEGIN + body_word[...].stopOn(ender) + END
            result = expr.parseString(test)
            self.assertEqual(
                result,
                test.split(),
                "Did not successfully stop on ending expression %r" % ender,
            )

        number = Word(nums + ",.()").set_parser_name("number with optional commas")
        parser = OneOrMore(Word(alphanums + "-/."), stopOn=number)("id").setParseAction(
            " ".join
        ) + number("data")
        result = parser.parseString("        XXX Y/123          1,234.567890")
        self.assertEqual(
            result,
            ["XXX Y/123", "1,234.567890"],
            "Did not successfully stop on ending expression %r" % number,
        )

    def testZeroOrMoreStop(self):
        test = "BEGIN END"
        BEGIN, END = map(Keyword, "BEGIN,END".split(","))
        body_word = Word(alphas).set_parser_name("word")
        for ender in (END, "END", CaselessKeyword("END")):
            expr = BEGIN + ZeroOrMore(body_word, stopOn=ender) + END
            result = expr.parseString(test)
            self.assertEqual(
                result,
                test.split(),
                "Did not successfully stop on ending expression %r" % ender,
            )

            expr = BEGIN + body_word[0, ...].stopOn(ender) + END
            result = expr.parseString(test)
            self.assertEqual(
                result,
                test.split(),
                "Did not successfully stop on ending expression %r" % ender,
            )

    def testNestedAsDict(self):
        equals = Literal("=").suppress()
        lbracket = Literal("[").suppress()
        rbracket = Literal("]").suppress()
        lbrace = Literal("{").suppress()
        rbrace = Literal("}").suppress()

        value_dict = Forward()
        value_list = Forward()
        value_string = Word(alphanums + "@. ")

        value = value_list ^ value_dict ^ value_string
        values = Group(delimitedList(value, ","))
        # ~ values              = delimitedList(value, ",").setParseAction(lambda toks: [toks])

        value_list << lbracket + values + rbracket

        identifier = Word(alphanums + "_.")

        assignment = Group(identifier + equals + Optional(value))
        assignments = Dict(delimitedList(assignment, ";"))
        value_dict << lbrace + assignments + rbrace

        response = assignments
        #      0         1         2         3         4         5         6         7
        #      0123456789012345678901234567890123456789012345678901234567890123456789012
        rsp = (
            "username=goat; errors={username=[already taken, too short]}; empty_field="
        )
        result = response.parseString(rsp)
        result_dict = result
        self.assertEqual(
            result_dict["username"],
            "goat",
            "failed to process string in ParseResults correctly",
        )
        self.assertEqual(
            result_dict["errors"]["username"],
            ["already taken", "too short"],
            "failed to process nested ParseResults correctly",
        )

    def testSimpleNestedAsDict(self):
        equals = Literal("=").suppress()
        lbrace = Literal("{").suppress()
        rbrace = Literal("}").suppress()

        value_string = Word(alphanums)
        identifier = Word(alphanums)

        value_dict = Forward()
        value = value_dict ^ value_string
        assignment = Group(identifier + equals + value)
        assignments = Dict(delimitedList(assignment, ";"))
        value_dict << lbrace + assignments + rbrace

        #      0         1         2
        #      012345678901234567890123456789
        rsp = "e={u=k}"
        result = assignments.parseString(rsp)
        result_dict = result
        self.assertEqual(
            result_dict["e"]["u"],
            "k",
            "failed to process nested ParseResults correctly",
        )

    def testTraceParseActionDecorator(self):
        @traceParseAction
        def convert_to_int(t):
            return int(t[0])

        class Z:
            def __call__(self, other):
                return other[0] * 1000

        integer = Word(nums).addParseAction(convert_to_int)
        integer.addParseAction(traceParseAction(lambda t: t[0] * 10))
        integer.addParseAction(traceParseAction(Z()))
        integer.parseString("132")

    def testRunTests(self):
        integer = Word(nums).setParseAction(lambda t: int(t[0]))
        intrange = integer("start") + "-" + integer("end")
        intrange.addCondition(
            lambda t: t.end > t.start,
            message="invalid range, start must be <= end",
            fatal=True,
        )

        def _range(s, i, t):
            return list(range(t.start, t.end + 1))

        intrange.addParseAction(_range)

        indices = delimitedList(intrange | integer)
        indices.addParseAction(lambda t: sorted(set(t)))

        tests = """\
            # normal data
            1-3,2-4,6,8-10,16

            # lone integer
            11"""
        success, results = indices.runTests(tests, printResults=False)

        expectedResults = [
            [1, 2, 3, 4, 6, 8, 9, 10, 16],
            [11],
        ]
        for (test, result), expected in zip(results, expectedResults):

            self.assertEqual(result, expected, "failed test: " + str(expected))

        tests = """\
            # invalid range
            1-2, 3-1, 4-6, 7, 12
            """
        success, results = indices.runTests(
            tests, printResults=False, failureTests=True
        )
        self.assertTrue(success, "failed to raise exception on improper range test")

    def testRunTestsPostParse(self):
        fraction = integer("numerator") + "/" + integer("denominator")

        accum = []

        def eval_fraction(test, result):
            accum.append((test, result))
            return "eval: {}".format(result.numerator / result.denominator)

        success = fraction.runTests(
            """\
            1/2
            1/0
        """,
            postParse=eval_fraction,
        )[0]

        self.assertTrue(success, "failed to parse fractions in RunTestsPostParse")

        expected_accum = [("1/2", [1, "/", 2]), ("1/0", [1, "/", 0])]
        self.assertEqual(
            accum, expected_accum, "failed to call postParse method during runTests"
        )

    def testCommonExpressions(self):

        success = mac_address.runTests(
            """
            AA:BB:CC:DD:EE:FF
            AA.BB.CC.DD.EE.FF
            AA-BB-CC-DD-EE-FF
            """
        )[0]
        self.assertTrue(success, "error in parsing valid MAC address")

        success = mac_address.runTests(
            """
            # mixed delimiters
            AA.BB:CC:DD:EE:FF
            """,
            failureTests=True,
        )[0]
        self.assertTrue(success, "error in detecting invalid mac address")

        success = ipv4_address.runTests(
            """
            0.0.0.0
            1.1.1.1
            127.0.0.1
            1.10.100.199
            255.255.255.255
            """
        )[0]
        self.assertTrue(success, "error in parsing valid IPv4 address")

        success = ipv4_address.runTests(
            """
            # out of range value
            256.255.255.255
            """,
            failureTests=True,
        )[0]
        self.assertTrue(success, "error in detecting invalid IPv4 address")

        success = ipv6_address.runTests(
            """
            2001:0db8:85a3:0000:0000:8a2e:0370:7334
            2134::1234:4567:2468:1236:2444:2106
            0:0:0:0:0:0:A00:1
            1080::8:800:200C:417A
            ::A00:1

            # loopback address
            ::1

            # the null address
            ::

            # ipv4 compatibility form
            ::ffff:192.168.0.1
            """
        )[0]
        self.assertTrue(success, "error in parsing valid IPv6 address")

        success = ipv6_address.runTests(
            """
            # too few values
            1080:0:0:0:8:800:200C

            # too many ::'s, only 1 allowed
            2134::1234:4567::2444:2106
            """,
            failureTests=True,
        )[0]
        self.assertTrue(success, "error in detecting invalid IPv6 address")

        success = number.runTests(
            """
            100
            -100
            +100
            3.14159
            6.02e23
            1e-12
            """
        )[0]
        self.assertTrue(success, "error in parsing valid numerics")

        success = sci_real.runTests(
            """
            1e12
            -1e12
            3.14159
            6.02e23
            """
        )[0]
        self.assertTrue(success, "error in parsing valid scientific notation reals")

        # any int or real number, returned as float
        success = fnumber.runTests(
            """
            100
            -100
            +100
            3.14159
            6.02e23
            1e-12
            """
        )[0]
        self.assertTrue(success, "error in parsing valid numerics")

        success, results = iso8601_date.runTests(
            """
            1997
            1997-07
            1997-07-16
            """
        )
        self.assertTrue(success, "error in parsing valid iso8601_date")
        expected = [
            ("1997", None, None),
            ("1997", "07", None),
            ("1997", "07", "16"),
        ]
        for r, exp in zip(results, expected):
            self.assertTrue(
                (r[1]["year"], r[1]["month"], r[1]["day"]) == exp,
                "failed to parse date into fields",
            )

        success, results = iso8601_date.addParseAction(convertToDate()).runTests(
            """
            1997-07-16
            """
        )
        self.assertTrue(
            success, "error in parsing valid iso8601_date with parse action"
        )
        self.assertTrue(results[0][1][0] == datetime.date(1997, 7, 16))

        success, results = iso8601_datetime.runTests(
            """
            1997-07-16T19:20+01:00
            1997-07-16T19:20:30+01:00
            1997-07-16T19:20:30.45Z
            1997-07-16 19:20:30.45
            """
        )
        self.assertTrue(success, "error in parsing valid iso8601_datetime")

        success, results = iso8601_datetime.addParseAction(
            convertToDatetime()
        ).runTests(
            """
            1997-07-16T19:20:30.45
            """
        )
        self.assertTrue(success, "error in parsing valid iso8601_datetime")
        self.assertTrue(
            results[0][1][0] == datetime.datetime(1997, 7, 16, 19, 20, 30, 450000)
        )

        success = uuid.runTests(
            """
            123e4567-e89b-12d3-a456-426655440000
            """
        )[0]
        self.assertTrue(success, "failed to parse valid uuid")

        success = fraction.runTests(
            """
            1/2
            -15/16
            -3/-4
            """
        )[0]
        self.assertTrue(success, "failed to parse valid fraction")

        success = mixed_integer.runTests(
            """
            1/2
            -15/16
            -3/-4
            1 1/2
            2 -15/16
            0 -3/-4
            12
            """
        )[0]
        self.assertTrue(success, "failed to parse valid mixed integer")

        success, results = number.runTests(
            """
            100
            -3
            1.732
            -3.14159
            6.02e23"""
        )
        self.assertTrue(success, "failed to parse numerics")

        for test, result in results:
            expected = ast.literal_eval(test)
            self.assertEqual(
                result[0],
                expected,
                "numeric parse failed (wrong value) ({} should be {})".format(
                    result[0], expected
                ),
            )
            self.assertEqual(
                type(result[0]),
                type(expected),
                "numeric parse failed (wrong type) ({} should be {})".format(
                    type(result[0]), type(expected)
                ),
            )

    def testNumericExpressions(self):

        # disable parse actions that do type conversion so we don't accidentally trigger
        # conversion exceptions when what we want to check is the parsing expression
        real = helpers.real().setParseAction(None)
        sci_real = helpers.sci_real().setParseAction(None)
        signed_integer = helpers.signed_integer().setParseAction(None)

        def make_tests():
            leading_sign = ["+", "-", ""]
            leading_digit = ["0", ""]
            dot = [".", ""]
            decimal_digit = ["1", ""]
            e = ["e", "E", ""]
            e_sign = ["+", "-", ""]
            e_int = ["22", ""]
            stray = ["9", ".", ""]

            seen = set()
            seen.add("")
            for parts in product(
                leading_sign,
                stray,
                leading_digit,
                dot,
                decimal_digit,
                stray,
                e,
                e_sign,
                e_int,
                stray,
            ):
                parts_str = "".join(parts).strip()
                if parts_str in seen:
                    continue
                seen.add(parts_str)
                yield parts_str

        # collect tests into valid/invalid sets, depending on whether they evaluate to valid Python floats or ints
        valid_ints = set()
        valid_reals = set()
        valid_sci_reals = set()
        invalid_ints = set()
        invalid_reals = set()
        invalid_sci_reals = set()

        # check which strings parse as valid floats or ints, and store in related valid or invalid test sets
        for test_str in make_tests():
            if "." in test_str or "e" in test_str.lower():
                try:
                    float(test_str)
                except ValueError:
                    invalid_sci_reals.add(test_str)
                    if "e" not in test_str.lower():
                        invalid_reals.add(test_str)
                else:
                    valid_sci_reals.add(test_str)
                    if "e" not in test_str.lower():
                        valid_reals.add(test_str)

            try:
                int(test_str)
            except ValueError:
                invalid_ints.add(test_str)
            else:
                valid_ints.add(test_str)

        # now try all the test sets against their respective expressions
        all_pass = True
        suppress_results = {"printResults": False}
        for expr, tests, is_fail, fn in zip(
            [real, sci_real, signed_integer] * 2,
            [
                valid_reals,
                valid_sci_reals,
                valid_ints,
                invalid_reals,
                invalid_sci_reals,
                invalid_ints,
            ],
            [False, False, False, True, True, True],
            [float, float, int] * 2,
        ):
            #
            # success, test_results = expr.runTests(sorted(tests, key=len), failureTests=is_fail, **suppress_results)
            # filter_result_fn = (lambda r: isinstance(r, Exception),
            #                     lambda r: not isinstance(r, Exception))[is_fail]
            # print(expr, ('FAIL', 'PASS')[success], "{}valid tests ({})".format(len(tests),
            #                                                                       'in' if is_fail else ''))
            # if not success:
            #     all_pass = False
            #     for test_string, result in test_results:
            #         if filter_result_fn(result):
            #             try:
            #                 test_value = fn(test_string)
            #             except ValueError as ve:
            #                 test_value = str(ve)
            #             print("{!r}: {} {} {}".format(test_string, result,
            #                                                expr.matches(test_string, parseAll=True), test_value))

            success = True
            for t in tests:
                if expr.matches(t, parseAll=True):
                    if is_fail:

                        success = False
                else:
                    if not is_fail:

                        success = False
            print(
                expr,
                ("FAIL", "PASS")[success],
                "{}valid tests ({})".format("in" if is_fail else "", len(tests),),
            )
            all_pass = all_pass and success

        self.assertTrue(all_pass, "failed one or more numeric tests")

    def testTokenMap(self):

        parser = OneOrMore(Word(hexnums)).setParseAction(tokenMap(int, 16))
        success, report = parser.runTests(
            """
            00 11 22 aa FF 0a 0d 1a
            """
        )
        # WAS:
        # self.assertTrue(success, "failed to parse hex integers")
        # print(results)
        # self.assertEqual(results[0][-1], [0, 17, 34, 170, 255, 10, 13, 26], "tokenMap parse action failed")

        # USING JUST assertParseResultsEquals
        # results = [rpt[1] for rpt in report]
        # self.assertParseResultsEquals(results[0], [0, 17, 34, 170, 255, 10, 13, 26],
        #                               msg="tokenMap parse action failed")

        # if I hadn't unpacked the return from runTests, I could have just passed it directly,
        # instead of reconstituting as a tuple
        self.assertRunTestResults(
            (success, report),
            [([0, 17, 34, 170, 255, 10, 13, 26], "tokenMap parse action failed"),],
            msg="failed to parse hex integers",
        )

    def testParseFile(self):

        s = """
        123 456 789
        """
        input_file = StringIO(s)

        results = OneOrMore(integer).parseFile(input_file)

        results = OneOrMore(integer).parseFile(
            "tests/resources/parsefiletest_input_file.txt"
        )

    def testHTMLStripper(self):
        sample = """
        <html>
        Here is some sample <i>HTML</i> text.
        </html>
        """
        read_everything = originalTextFor(OneOrMore(Word(printables)))
        read_everything.addParseAction(stripHTMLTags)

        result = read_everything.parseString(sample)
        self.assertEqual(result[0].strip(), "Here is some sample HTML text.")

    def testExprSplitter(self):

        engine.CURRENT.add_ignore(quotedString)
        engine.CURRENT.add_ignore(pythonStyleComment)
        expr = Literal(";") + Empty()

        sample = """
        def main():
            this_semi_does_nothing();
            neither_does_this_but_there_are_spaces_afterward();
            a = "a;b"; return a # this is a comment; it has a semicolon!

        def b():
            if False:
                z=1000;b("; in quotes");  c=200;return z
            return ';'

        class Foo(object):
            def bar(self):
                '''a docstring; with a semicolon'''
                a = 10; b = 11; c = 12

                # this comment; has several; semicolons
                if self.spam:
                    x = 12; return x # so; does; this; one
                    x = 15;;; y += x; return y

            def baz(self):
                return self.bar
        """
        expected = [
            ["            this_semi_does_nothing()", ""],
            ["            neither_does_this_but_there_are_spaces_afterward()", ""],
            [
                '            a = "a;b"',
                "return a # this is a comment; it has a semicolon!",
            ],
            ["                z=1000", 'b("; in quotes")', "c=200", "return z"],
            ["            return ';'"],
            ["                '''a docstring; with a semicolon'''"],
            ["                a = 10", "b = 11", "c = 12"],
            ["                # this comment; has several; semicolons"],
            ["                    x = 12", "return x # so; does; this; one"],
            ["                    x = 15", "", "", "y += x", "return y"],
        ]

        for expect, line in zip(
            expected, filter(lambda ll: ";" in ll, sample.splitlines())
        ):

            self.assertEqual(
                list(expr.split(line)),
                expect,
                "invalid split on expression"
            )

        expected = [
            ["            this_semi_does_nothing()", ";", ""],
            ["            neither_does_this_but_there_are_spaces_afterward()", ";", ""],
            [
                '            a = "a;b"',
                ";",
                "return a # this is a comment; it has a semicolon!",
            ],
            [
                "                z=1000",
                ";",
                'b("; in quotes")',
                ";",
                "c=200",
                ";",
                "return z",
            ],
            ["            return ';'"],
            ["                '''a docstring; with a semicolon'''"],
            ["                a = 10", ";", "b = 11", ";", "c = 12"],
            ["                # this comment; has several; semicolons"],
            ["                    x = 12", ";", "return x # so; does; this; one"],
            [
                "                    x = 15",
                ";",
                "",
                ";",
                "",
                ";",
                "y += x",
                ";",
                "return y",
            ],
        ]
        exp_iter = iter(expected)
        for line in filter(lambda ll: ";" in ll, sample.splitlines()):

            self.assertEqual(
                list(expr.split(line, includeSeparators=True)),
                next(exp_iter),
                "invalid split on expression",
            )

        expected = [
            ["            this_semi_does_nothing()", ""],
            ["            neither_does_this_but_there_are_spaces_afterward()", ""],
            [
                '            a = "a;b"',
                "return a # this is a comment; it has a semicolon!",
            ],
            ["                z=1000", 'b("; in quotes");  c=200;return z'],
            ["                a = 10", "b = 11; c = 12"],
            ["                    x = 12", "return x # so; does; this; one"],
            ["                    x = 15", ";; y += x; return y"],
        ]
        exp_iter = iter(expected)
        for line in sample.splitlines():
            pieces = list(expr.split(line, maxsplit=1))

            if len(pieces) == 2:
                exp = next(exp_iter)
                self.assertEqual(
                    pieces, exp, "invalid split on expression with maxSplits=1"
                )
            elif len(pieces) == 1:
                self.assertEqual(
                    len(expr.searchString(line)),
                    0,
                    "invalid split with maxSplits=1 when expr not present",
                )
            else:

                self.assertTrue(
                    False, "invalid split on expression with maxSplits=1, corner case"
                )

    def testParseFatalException(self):

        with self.assertRaisesParseException(
            exc_type=ParseFatalException, msg="failed to raise ErrorStop exception"
        ):
            expr = "ZZZ" - Word(nums)
            expr.parseString("ZZZ bad")

        # WAS:
        # success = False
        # try:
        #     expr = "ZZZ" - Word(nums)
        #     expr.parseString("ZZZ bad")
        # except ParseFatalException as pfe:
        #     print('ParseFatalException raised correctly')
        #     success = True
        # except Exception as e:
        #     print(type(e))
        #     print(e)
        #
        # self.assertTrue(success, "bad handling of syntax error")

    def test_default_literal(self):

        wd = Word(alphas)

        engine.CURRENT.set_literal(Suppress)
        result = (wd + "," + wd + oneOf("! . ?")).parseString("Hello, World!")
        self.assertEqual(len(result), 3, "default_literal(Suppress) failed!")

        engine.CURRENT.set_literal(Literal)
        result = (wd + "," + wd + oneOf("! . ?")).parseString("Hello, World!")
        self.assertEqual(len(result), 4, "default_literal(Literal) failed!")

        engine.CURRENT.set_literal(CaselessKeyword)
        # WAS:
        # result = ("SELECT" + wd + "FROM" + wd).parseString("select color from colors")
        # self.assertEqual(result, "SELECT color FROM colors".split(),
        #                  "default_literal(CaselessKeyword) failed!")
        self.assertParseResultsEquals(
            ("SELECT" + wd + "FROM" + wd).parseString("select color from colors"),
            expected_list=["SELECT", "color", "FROM", "colors"],
            msg="default_literal(CaselessKeyword) failed!",
        )

        default_literal(CaselessLiteral)
        # result = ("SELECT" + wd + "FROM" + wd).parseString("select color from colors")
        # self.assertEqual(result, "SELECT color FROM colors".split(),
        #                  "default_literal(CaselessLiteral) failed!")
        self.assertParseResultsEquals(
            ("SELECT" + wd + "FROM" + wd).parseString("select color from colors"),
            expected_list=["SELECT", "color", "FROM", "colors"],
            msg="default_literal(CaselessLiteral) failed!",
        )

        integer = Word(nums)
        default_literal(Literal)
        date_str = integer("year") + "/" + integer("month") + "/" + integer("day")
        # result = date_str.parseString("1999/12/31")
        # self.assertEqual(result, ['1999', '/', '12', '/', '31'], "default_literal(example 1) failed!")
        self.assertParseResultsEquals(
            date_str.parseString("1999/12/31"),
            expected_list=["1999", "/", "12", "/", "31"],
            msg="default_literal(example 1) failed!",
        )

        # change to Suppress
        default_literal(Suppress)
        date_str = integer("year") + "/" + integer("month") + "/" + integer("day")

        # result = date_str.parseString("1999/12/31")  # -> ['1999', '12', '31']
        # self.assertEqual(result, ['1999', '12', '31'], "default_literal(example 2) failed!")
        self.assertParseResultsEquals(
            date_str.parseString("1999/12/31"),
            expected_list=["1999", "12", "31"],
            msg="default_literal(example 2) failed!",
        )

    def testCloseMatch(self):
        searchseq = CloseMatch("ATCATCGAATGGA", 2)

        _, results = searchseq.runTests(
            """
            ATCATCGAATGGA
            XTCATCGAATGGX
            ATCATCGAAXGGA
            ATCAXXGAATGGA
            ATCAXXGAATGXA
            ATCAXXGAATGG
            """
        )
        expected = ([], [0, 12], [9], [4, 5], None, None)

        for (r_str, r_tok), exp in zip(results, expected):
            if exp is not None:
                self.assertEquals(
                    r_tok["mismatches"],
                    exp,
                    "fail CloseMatch between {!r} and {!r}".format(
                        searchseq.match_string, r_str
                    ),
                )

    def testDefaultKeywordChars(self):

        with self.assertRaisesParseException(
            msg="failed to fail matching keyword using updated keyword chars"
        ):
            Keyword("start").parseString("start1000")

        try:
            Keyword("start", identChars=alphas).parseString("start1000")
        except ParseException:
            self.assertTrue(
                False, "failed to match keyword using updated keyword chars"
            )

        with Timer(""):
            engine.CURRENT.set_keyword_chars(alphas)
            try:
                Keyword("start").parseString("start1000")
            except ParseException:
                self.assertTrue(
                    False, "failed to match keyword using updated keyword chars"
                )

        with self.assertRaisesParseException(
            msg="failed to fail matching keyword using updated keyword chars"
        ):
            CaselessKeyword("START").parseString("start1000")

        try:
            CaselessKeyword("START", identChars=alphas).parseString("start1000")
        except ParseException:
            self.assertTrue(
                False, "failed to match keyword using updated keyword chars"
            )

        with Timer(""):
            Keyword.setDefaultKeywordChars(alphas)
            try:
                CaselessKeyword("START").parseString("start1000")
            except ParseException:
                self.assertTrue(
                    False, "failed to match keyword using updated keyword chars"
                )

    def testCol(self):

        test = "*\n* \n*   ALF\n*\n"
        initials = [c for i, c in enumerate(test) if col(i, test) == 1]

        self.assertTrue(
            len(initials) == 4 and all(c == "*" for c in initials), "fail col test"
        )

    def testLiteralException(self):
        for cls in (
            Literal,
            CaselessLiteral,
            Keyword,
            CaselessKeyword,
            Word,
            Regex,
        ):
            expr = cls(
                "xyz"
            )  # .set_parser_name('{}_expr'.format(cls.__name__.lower()))

            try:
                expr.parseString(" ")
            except Exception as e:

                self.assertTrue(
                    isinstance(e, ParseBaseException),
                    "class {} raised wrong exception type {}".format(
                        cls.__name__, type(e).__name__
                    ),
                )

    def testParseActionException(self):

        number = Word(nums)

        def number_action():
            raise IndexError  # this is the important line!

        number.setParseAction(number_action)
        symbol = Word("abcd", max=1)
        expr = number | symbol

        try:
            expr.parseString("1 + 2")
        except Exception as e:
            print_traceback = True
            try:
                self.assertTrue(
                    hasattr(e, "__cause__"),
                    "no __cause__ attribute in the raised exception",
                )
                self.assertTrue(
                    e.__cause__ is not None,
                    "__cause__ not propagated to outer exception",
                )
                self.assertTrue(
                    type(e.__cause__) == IndexError,
                    "__cause__ references wrong exception",
                )
                print_traceback = False
            finally:
                if print_traceback:
                    traceback.print_exc()
        else:
            self.assertTrue(False, "Expected ParseException not raised")

    # tests Issue #22
    def testParseActionNesting(self):

        vals = OneOrMore(integer)("int_values")

        def add_total(tokens):
            tokens["total"] = sum(tokens)
            return tokens

        vals.addParseAction(add_total)
        results = vals.parseString("244 23 13 2343")
        self.assertParseResultsEquals(
            results,
            expected_dict={"int_values": [244, 23, 13, 2343], "total": 2623},
            msg="noop parse action changed ParseResults structure",
        )

        name = Word(alphas)("name")
        score = Word(nums + ".")("score")
        nameScore = Group(name + score)
        line1 = nameScore("Rider")

        result1 = line1.parseString("Mauney 46.5")

        before_pa_dict = result1

        line1.setParseAction(lambda t: t)

        result1 = line1.parseString("Mauney 46.5")
        after_pa_dict = result1

        self.assertEqual(
            before_pa_dict,
            after_pa_dict,
            "noop parse action changed ParseResults structure",
        )

    def testParseResultsNameBelowUngroupedName(self):
        rule_num = Regex("[0-9]+")("LIT_NUM*")
        list_num = Group(
            Literal("[")("START_LIST")
            + delimitedList(rule_num)("LIST_VALUES")
            + Literal("]")("END_LIST")
        )("LIST")

        test_string = "[ 1,2,3,4,5,6 ]"
        list_num.runTests(test_string)

        U = list_num.parseString(test_string)
        self.assertEqual(U.LIST.LIST_VALUES.LIT_NUM, ["1", "2", "3", "4", "5", "6"])

    def testParseResultsNamesInGroupWithDict(self):

        key = identifier()
        value = integer()
        lat = real()
        long = real()
        EQ = Suppress("=")

        data = lat("lat") + long("long") + Dict(OneOrMore(Group(key + EQ + value)))
        site = QuotedString('"')("name") + Group(data)("data")

        test_string = '"Golden Gate Bridge" 37.819722 -122.478611 height=746 span=4200'
        site.runTests(test_string)

        a, aEnd = makeHTMLTags("a")
        attrs = a.parseString("<a href='blah'>")

        self.assertParseResultsEquals(
            attrs,
            expected_dict={
                "startA": {"href": "blah", "tag": "a", "empty": False},
                "href": "blah",
                "tag": "a",
                "empty": False,
            },
        )

    def testFollowedBy(self):
        expr = Word(alphas)("item") + FollowedBy(integer("qty"))
        result = expr.parseString("balloon 99")

        self.assertTrue("qty" in result, "failed to capture results name in FollowedBy")
        self.assertEqual(
            result,
            {"item": "balloon", "qty": 99},
            "invalid results name structure from FollowedBy",
        )

    def testUnicodeTests(self):

        # verify proper merging of ranges by addition
        kanji_printables = parsing_unicode.Japanese.Kanji.printables
        katakana_printables = parsing_unicode.Japanese.Katakana.printables
        hiragana_printables = parsing_unicode.Japanese.Hiragana.printables
        japanese_printables = parsing_unicode.Japanese.printables
        self.assertEqual(
            set(japanese_printables),
            set(kanji_printables + katakana_printables + hiragana_printables),
            "failed to construct ranges by merging Japanese types",
        )

        # verify proper merging of ranges using multiple inheritance
        cjk_printables = parsing_unicode.CJK.printables
        self.assertEqual(
            len(cjk_printables),
            len(set(cjk_printables)),
            "CJK contains duplicate characters - all should be unique",
        )

        chinese_printables = parsing_unicode.Chinese.printables
        korean_printables = parsing_unicode.Korean.printables
        print(
            len(cjk_printables),
            len(set(chinese_printables + korean_printables + japanese_printables)),
        )

        self.assertEqual(
            len(cjk_printables),
            len(set(chinese_printables + korean_printables + japanese_printables)),
            "failed to construct ranges by merging Chinese, Japanese and Korean",
        )

        alphas = parsing_unicode.Greek.alphas
        greet = Word(alphas) + "," + Word(alphas) + "!"

        # input string
        hello = "Καλημέρα, κόσμε!"
        result = greet.parseString(hello)

        self.assertParseResultsEquals(
            result,
            expected_list=["Καλημέρα", ",", "κόσμε", "!"],
            msg="Failed to parse Greek 'Hello, World!' using "
            "parsing_unicode.Greek.alphas",
        )

        # define a custom unicode range using multiple inheritance
        class Turkish_set(parsing_unicode.Latin1, parsing_unicode.LatinA):
            pass

        self.assertEqual(
            set(Turkish_set.printables),
            set(parsing_unicode.Latin1.printables + parsing_unicode.LatinA.printables),
            "failed to construct ranges by merging Latin1 and LatinA (printables)",
        )

        self.assertEqual(
            set(Turkish_set.alphas),
            set(parsing_unicode.Latin1.alphas + parsing_unicode.LatinA.alphas),
            "failed to construct ranges by merging Latin1 and LatinA (alphas)",
        )

        self.assertEqual(
            set(Turkish_set.nums),
            set(parsing_unicode.Latin1.nums + parsing_unicode.LatinA.nums),
            "failed to construct ranges by merging Latin1 and LatinA (nums)",
        )

        key = Word(Turkish_set.alphas)
        value = integer | Word(Turkish_set.alphas, Turkish_set.alphanums)
        EQ = Suppress("=")
        key_value = key + EQ + value

        sample = """\
            şehir=İzmir
            ülke=Türkiye
            nüfus=4279677"""
        result = Dict(OneOrMore(Group(key_value))).parseString(sample)

        self.assertParseResultsEquals(
            result,
            expected_dict={"şehir": "İzmir", "ülke": "Türkiye", "nüfus": 4279677},
            msg="Failed to parse Turkish key-value pairs",
        )

    # Make sure example in indentedBlock docstring actually works!
    def testIndentedBlockExample(self):

        data = dedent(
            """
        def A(z):
          A1
          B = 100
          G = A2
          A2
          A3
        B
        def BB(a,b,c):
          BB1
          def BBA():
            bba1
            bba2
            bba3
        C
        D
        def spam(x,y):
             def eggs(z):
                 pass
        """
        )

        indentStack = [1]
        stmt = Forward()

        identifier = Word(alphas, alphanums)
        funcDecl = (
            "def"
            + identifier
            + Group("(" + Optional(delimitedList(identifier)) + ")")
            + ":"
        )
        func_body = indentedBlock(stmt, indentStack)
        funcDef = Group(funcDecl + func_body)

        rvalue = Forward()
        funcCall = Group(identifier + "(" + Optional(delimitedList(rvalue)) + ")")
        rvalue << (funcCall | identifier | Word(nums))
        assignment = Group(identifier + "=" + rvalue)
        stmt << (funcDef | assignment | identifier)

        module_body = OneOrMore(stmt)

        parseTree = module_body.parseString(data)

        self.assertEqual(
            parseTree,
            [
                [
                    "def",
                    "A",
                    ["(", "z", ")"],
                    ":",
                    [["A1"], [["B", "=", "100"]], [["G", "=", "A2"]], ["A2"], ["A3"]],
                ],
                "B",
                [
                    "def",
                    "BB",
                    ["(", "a", "b", "c", ")"],
                    ":",
                    [
                        ["BB1"],
                        [
                            [
                                "def",
                                "BBA",
                                ["(", ")"],
                                ":",
                                [["bba1"], ["bba2"], ["bba3"]],
                            ]
                        ],
                    ],
                ],
                "C",
                "D",
                [
                    "def",
                    "spam",
                    ["(", "x", "y", ")"],
                    ":",
                    [[["def", "eggs", ["(", "z", ")"], ":", [["pass"]]]]],
                ],
            ],
            "Failed indentedBlock example",
        )

    def testIndentedBlock(self):
        # parse pseudo-yaml indented text
        EQ = Suppress("=")
        stack = [1]
        key = identifier
        value = Forward()
        key_value = key + EQ + value
        compound_value = Dict(ungroup(indentedBlock(key_value, stack)))
        value <<= integer | QuotedString("'") | compound_value
        parser = Dict(OneOrMore(Group(key_value)))

        text = """
            a = 100
            b = 101
            c =
                c1 = 200
                c2 =
                    c21 = 999
                c3 = 'A horse, a horse, my kingdom for a horse'
            d = 505
        """
        text = textwrap.dedent(text)

        result = parser.parseString(text)

        self.assertEqual(result["a"], 100, "invalid indented block result")
        self.assertEqual(result["c"]["c1"], 200, "invalid indented block result")
        self.assertEqual(result["c"]["c2"]["c21"], 999, "invalid indented block result")

    # exercise indentedBlock with example posted in issue #87
    def testIndentedBlockTest2(self):
        indent_stack = [1]

        key = Word(alphas, alphanums) + Suppress(":")
        stmt = Forward()

        suite = indentedBlock(stmt, indent_stack)
        body = key + suite

        pattern = Word(alphas) + Suppress("(") + Word(alphas) + Suppress(")")
        stmt << pattern

        def key_parse_action(toks):
            print("Parsing '%s'..." % toks[0])

        key.setParseAction(key_parse_action)
        header = Suppress("[") + Literal("test") + Suppress("]")
        content = header - OneOrMore(indentedBlock(body, indent_stack, False))

        contents = Forward()
        suites = indentedBlock(content, indent_stack)

        extra = Literal("extra") + Suppress(":") - suites
        contents << (content | extra)

        parser = OneOrMore(contents)

        sample = dedent(
            """
        extra:
            [test]
            one0:
                two (three)
            four0:
                five (seven)
        extra:
            [test]
            one1:
                two (three)
            four1:
                five (seven)
        """
        )

        success, _ = parser.runTests([sample])
        self.assertTrue(success, "Failed indentedBlock test for issue #87")

        sample2 = dedent(
            """
        extra:
            [test]
            one:
                two (three)
            four:
                five (seven)
        extra:
            [test]
            one:
                two (three)
            four:
                five (seven)

            [test]
            one:
                two (three)
            four:
                five (seven)

            [test]
            eight:
                nine (ten)
            eleven:
                twelve (thirteen)

            fourteen:
                fifteen (sixteen)
            seventeen:
                eighteen (nineteen)
        """
        )

        del indent_stack[1:]
        success, _ = parser.runTests([sample2])
        self.assertTrue(success, "Failed indentedBlock multi-block test for issue #87")

    def testIndentedBlockScan(self):
        def get_parser():
            """
            A valid statement is the word "block:", followed by an indent, followed by the letter A only, or another block
            """
            stack = [1]
            block = Forward()
            body = indentedBlock(Literal("A") ^ block, indentStack=stack, indent=True)
            block <<= Literal("block:") + body
            return block

        # This input string is a perfect match for the parser, so a single match is found
        p1 = get_parser()
        r1 = list(
            p1.scanString(
                dedent(
                    """\
        block:
            A
        """
                )
            )
        )
        self.assertEqual(len(r1), 1)

        # This input string is a perfect match for the parser, except for the letter B instead of A, so this will fail (and should)
        p2 = get_parser()
        r2 = list(
            p2.scanString(
                dedent(
                    """\
        block:
            B
        """
                )
            )
        )
        self.assertEqual(len(r2), 0)

        # This input string contains both string A and string B, and it finds one match (as it should)
        p3 = get_parser()
        r3 = list(
            p3.scanString(
                dedent(
                    """\
        block:
            A
        block:
            B
        """
                )
            )
        )
        self.assertEqual(len(r3), 1)

        # This input string contains both string A and string B, but in a different order.
        p4 = get_parser()
        r4 = list(
            p4.scanString(
                dedent(
                    """\
        block:
            B
        block:
            A
        """
                )
            )
        )
        self.assertEqual(len(r4), 1)

        # This is the same as case 3, but with nesting
        p5 = get_parser()
        r5 = list(
            p5.scanString(
                dedent(
                    """\
        block:
            block:
                A
        block:
            block:
                B
        """
                )
            )
        )
        self.assertEqual(len(r5), 1)

        # This is the same as case 4, but with nesting
        p6 = get_parser()
        r6 = list(
            p6.scanString(
                dedent(
                    """\
        block:
            block:
                B
        block:
            block:
                A
        """
                )
            )
        )
        self.assertEqual(len(r6), 1)

    def testParseResultsWithNameMatchFirst(self):

        expr_a = Literal("not") + Literal("the") + Literal("bird")
        expr_b = Literal("the") + Literal("bird")
        expr = (expr_a | expr_b)("rexp")

        success, report = expr.runTests(
            """\
            not the bird
            the bird
        """
        )
        results = [rpt[1] for rpt in report]
        self.assertParseResultsEquals(
            results[0], ["not", "the", "bird"], {"rexp": ["not", "the", "bird"]}
        )
        self.assertParseResultsEquals(
            results[1], ["the", "bird"], {"rexp": ["the", "bird"]}
        )

    def testParseResultsWithNameOr(self):

        expr_a = Literal("not") + Literal("the") + Literal("bird")
        expr_b = Literal("the") + Literal("bird")
        expr = (expr_a ^ expr_b)("rexp")
        expr.runTests(
            """\
            not the bird
            the bird
        """
        )
        result = expr.parseString("not the bird")
        self.assertParseResultsEquals(
            result, ["not", "the", "bird"], {"rexp": ["not", "the", "bird"]}
        )
        result = expr.parseString("the bird")
        self.assertParseResultsEquals(
            result, ["the", "bird"], {"rexp": ["the", "bird"]}
        )

        expr = (expr_a | expr_b)("rexp")
        expr.runTests(
            """\
            not the bird
            the bird
        """
        )
        result = expr.parseString("not the bird")
        self.assertParseResultsEquals(
            result, ["not", "the", "bird"], {"rexp": ["not", "the", "bird"]}
        )
        result = expr.parseString("the bird")
        self.assertParseResultsEquals(
            result, ["the", "bird"], {"rexp": ["the", "bird"]}
        )

    def testEmptyDictDoesNotRaiseException(self):

        key = Word(alphas)
        value = Word(nums)
        EQ = Suppress("=")
        key_value_dict = dictOf(key, EQ + value)

        print(
            key_value_dict.parseString(
                """\
            a = 10
            b = 20
            """
            )
        )

        try:
            key_value_dict.parseString("")
        except ParseException as pe:
            pass  # expected
        else:
            self.assertTrue(
                False, "failed to raise exception when matching empty string"
            )

    def testExplainException(self):

        expr = Word(nums).set_parser_name("int") + Word(alphas).set_parser_name("word")
        try:
            expr.parseString("123 355")
        except ParseException as pe:
            pass

        expr = Word(nums).set_parser_name("int") - Word(alphas).set_parser_name("word")
        try:
            expr.parseString("123 355 (test using ErrorStop)")
        except ParseSyntaxException as pe:
            pass

        integer = Word(nums).set_parser_name("int").addParseAction(lambda t: int(t[0]))
        expr = integer + integer

        def divide_args(t):
            integer.parseString("A")
            return t[0] / t[1]

        expr.addParseAction(divide_args)

        try:
            expr.parseString("123 0")
        except ParseException as pe:
            pass

    def testCaselessKeywordVsKeywordCaseless(self):

        frule = Keyword("t", caseless=True) + Keyword("yes", caseless=True)
        crule = CaselessKeyword("t") + CaselessKeyword("yes")

        flist = frule.searchString("not yes").asList()

        clist = crule.searchString("not yes").asList()

        self.assertEqual(
            flist,
            clist,
            "CaselessKeyword not working the same as Keyword(caseless=True)",
        )

    def testOneOfKeywords(self):

        literal_expr = oneOf("a b c")
        success, _ = literal_expr[...].runTests(
            """
            # literal oneOf tests
            a b c
            a a a
            abc
        """
        )
        self.assertTrue(success, "failed literal oneOf matching")

        keyword_expr = oneOf("a b c", asKeyword=True)
        success, _ = keyword_expr[...].runTests(
            """
            # keyword oneOf tests
            a b c
            a a a
        """
        )
        self.assertTrue(success, "failed keyword oneOf matching")

        success, _ = keyword_expr[...].runTests(
            """
            # keyword oneOf failure tests
            abc
        """,
            failureTests=True,
        )
        self.assertTrue(success, "failed keyword oneOf failure tests")

    def testChainedTernaryOperator(self):

        TERNARY_INFIX = infixNotation(integer, [(("?", ":"), 3, opAssoc.LEFT),])
        self.assertParseResultsEquals(
            TERNARY_INFIX.parseString("1?1:0?1:0", parseAll=True),
            expected_list=[[1, "?", 1, ":", 0], "?", 1, ":", 0],
        )

        TERNARY_INFIX = infixNotation(integer, [(("?", ":"), 3, opAssoc.RIGHT),])
        self.assertParseResultsEquals(
            TERNARY_INFIX.parseString("1?1:0?1:0", parseAll=True),
            expected_list=[1, "?", 1, ":", [0, "?", 1, ":", 0]],
        )

    def testOneOfWithDuplicateSymbols(self):
        # test making oneOf with duplicate symbols

        try:
            test1 = oneOf("a b c d a")
        except RuntimeError:
            self.assertTrue(
                False,
                "still have infinite loop in oneOf with duplicate symbols (string input)",
            )

        try:
            test1 = oneOf(c for c in "a b c d a" if not c.isspace())
        except RuntimeError:
            self.assertTrue(
                False,
                "still have infinite loop in oneOf with duplicate symbols (generator input)",
            )

        try:
            test1 = oneOf("a b c d a".split())
        except RuntimeError:
            self.assertTrue(
                False,
                "still have infinite loop in oneOf with duplicate symbols (list input)",
            )

        try:
            test1 = oneOf(set("a b c d a"))
        except RuntimeError:
            self.assertTrue(
                False,
                "still have infinite loop in oneOf with duplicate symbols (set input)",
            )

    def testMatchFirstIteratesOverAllChoices(self):
        # test MatchFirst bugfix

        results = quotedString.parseString("'this is a single quoted string'")
        self.assertTrue(
            len(results) > 0, "MatchFirst error - not iterating over all choices"
        )

    def testStreamlineOfSubexpressions(self):
        # verify streamline of subexpressions

        compound = Literal("A") + "B" + "C" + "D"
        self.assertEqual(len(compound.exprs), 2, "bad test setup")

        compound.streamline()

        self.assertEqual(len(compound.exprs), 4, "streamline not working")

    def testOptionalWithResultsNameAndNoMatch(self):
        # test for Optional with results name and no match

        testGrammar = Literal("A") + Optional("B")("gotB") + Literal("C")
        try:
            testGrammar.parseString("ABC")
            testGrammar.parseString("AC")
        except ParseException as pe:

            self.assertTrue(False, "error in Optional matching of string %s" % pe.pstr)

    def testReturnOfFurthestException(self):
        # test return of furthest exception
        testGrammar = Literal("A") | (Optional("B") + Literal("C")) | Literal("D")
        try:
            testGrammar.parseString("BC")
            testGrammar.parseString("BD")
        except ParseException as pe:

            self.assertEqual(pe.pstr, "BD", "wrong test string failed to parse")
            self.assertEqual(
                pe.loc, 1, "error in Optional matching, pe.loc=" + str(pe.loc)
            )

    def testValidateCorrectlyDetectsInvalidLeftRecursion(self):
        # test validate

        if IRON_PYTHON_ENV:

            return

        def testValidation(grmr, gnam, isValid):
            try:
                grmr.streamline()
                grmr.validate()
                self.assertTrue(isValid, "validate() accepted invalid grammar " + gnam)
            except RecursiveGrammarException as e:

                self.assertFalse(isValid, "validate() rejected valid grammar " + gnam)

        fwd = Forward()
        g1 = OneOrMore((Literal("A") + "B" + "C") | fwd)
        g2 = ("C" + g1)[...]
        fwd << Group(g2)
        testValidation(fwd, "fwd", isValid=True)

        fwd2 = Forward()
        fwd2 << Group("A" | fwd2)
        testValidation(fwd2, "fwd2", isValid=False)

        fwd3 = Forward()
        fwd3 << Optional("A") + fwd3
        testValidation(fwd3, "fwd3", isValid=False)

    def testGetNameBehavior(self):
        # test getName

        aaa = Group(Word("a")("A"))
        bbb = Group(Word("b")("B"))
        ccc = Group(":" + Word("c")("C"))
        g1 = "XXX" + (aaa | bbb | ccc)[...]
        teststring = "XXX b bb a bbb bbbb aa bbbbb :c bbbbbb aaa"
        names = []

        for t in g1.parseString(teststring):

            try:
                names.append(t[0].getName())
            except Exception:
                try:
                    names.append(t.getName())
                except Exception:
                    names.append(None)

        self.assertEqual(
            names,
            [None, "B", "B", "A", "B", "B", "A", "B", None, "B", "A"],
            "failure in getting names for tokens",
        )

        IF, AND, BUT = map(Keyword, "if and but".split())
        ident = ~(IF | AND | BUT) + Word(alphas)("non-key")
        scanner = OneOrMore(IF | AND | BUT | ident)

        def getNameTester(s, l, t):

            return t

        ident.addParseAction(getNameTester)
        scanner.parseString("lsjd sldkjf IF Saslkj AND lsdjf")

        # test ParseResults.get() method

        # use sum() to merge separate groups into single ParseResults
        res = sum(g1.parseString(teststring)[1:])

        self.assertEqual(
            res.get("A", "A not found"), "aaa", "get on existing key failed"
        )
        self.assertEqual(res.get("D", "!D"), "!D", "get on missing key failed")

    def testOptionalBeyondEndOfString(self):

        testGrammar = "A" + Optional("B") + Optional("C") + Optional("D")
        testGrammar.parseString("A")
        testGrammar.parseString("AB")

    def testCreateLiteralWithEmptyString(self):
        # test creating Literal with empty string

        with self.assertWarns(
            SyntaxWarning, msg="failed to warn use of empty string for Literal"
        ):
            e = Literal("")
        try:
            e.parseString("SLJFD")
        except Exception as e:
            self.assertTrue(False, "Failed to handle empty Literal")

    def testLineMethodSpecialCaseAtStart(self):
        # test line() behavior when starting at 0 and the opening line is an \n

        self.assertEqual(
            line(0, "\nabc\ndef\n"),
            "",
            "Error in line() with empty first line in text",
        )
        txt = "\nabc\ndef\n"
        results = [line(i, txt) for i in range(len(txt))]
        self.assertEqual(
            results,
            ["", "abc", "abc", "abc", "abc", "def", "def", "def", "def"],
            "Error in line() with empty first line in text",
        )
        txt = "abc\ndef\n"
        results = [line(i, txt) for i in range(len(txt))]
        self.assertEqual(
            results,
            ["abc", "abc", "abc", "abc", "def", "def", "def", "def"],
            "Error in line() with non-empty first line in text",
        )

    def testRepeatedTokensWhenPackratting(self):
        # test bugfix with repeated tokens when packrat parsing enabled

        a = Literal("a")
        b = Literal("b")
        c = Literal("c")

        abb = a + b + b
        abc = a + b + c
        aba = a + b + a
        grammar = abb | abc | aba

        self.assertEqual(
            "".join(grammar.parseString("aba")), "aba", "Packrat ABA failure!"
        )

    def testSetResultsNameWithOneOrMoreAndZeroOrMore(self):

        stmt = Keyword("test")

        self.assertEqual(
            len(stmt[...]("tests").parseString("test test").tests),
            2,
            "ZeroOrMore failure with .set_token_name",
        )
        self.assertEqual(
            len(stmt[1, ...]("tests").parseString("test test").tests),
            2,
            "OneOrMore failure with .set_token_name",
        )
        self.assertEqual(
            len(Optional(stmt[1, ...]("tests")).parseString("test test").tests),
            2,
            "OneOrMore failure with .set_token_name",
        )
        self.assertEqual(
            len(Optional(delimitedList(stmt))("tests").parseString("test,test").tests),
            2,
            "delimitedList failure with .set_token_name",
        )
        self.assertEqual(
            len((stmt * 2)("tests").parseString("test test").tests),
            2,
            "multiplied(1) failure with .set_token_name",
        )
        self.assertEqual(
            len(stmt[..., 2]("tests").parseString("test test").tests),
            2,
            "multiplied(2) failure with .set_token_name",
        )
        self.assertEqual(
            len(stmt[1, ...]("tests").parseString("test test").tests),
            2,
            "multipled(3) failure with .set_token_name",
        )
        self.assertEqual(
            len(stmt[2, ...]("tests").parseString("test test").tests),
            2,
            "multipled(3) failure with .set_token_name",
        )
