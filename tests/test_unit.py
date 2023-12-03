# encoding: utf-8
#
# test_unit.py
#
# Unit tests for mo_parsing module
#
# Copyright 2002-2019, Paul McGuire
#
#
import ast
import json
import math
import sys
import textwrap
import traceback
import unittest
from datetime import date as datetime_date
from datetime import datetime as datetime_datetime
from io import StringIO
from itertools import product
from textwrap import dedent
from unittest import TestCase

from mo_dots import coalesce, Null as print
from mo_times import Timer

from examples import fourFn, configParse, idlParse, ebnf
from examples.jsonParser import jsonObject
from examples.simpleSQL import simpleSQL
from mo_parsing import *
from mo_parsing import helpers
from mo_parsing.utils import parsing_unicode, line, lineno
from mo_parsing.helpers import *

from tests.json_parser_tests import test1, test2, test3, test4, test5
from tests.test_simple_unit import PyparsingExpressionTestCase

# see which Python implementation we are running
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


class TestParsing(PyparsingExpressionTestCase):
    def testParseFourFn(self):
        def test(s, ans):
            fourFn.exprStack[:] = []
            results = fourFn.bnf.parse_string(s)
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
                sqlToks = flatten(simpleSQL.parse_string(s))

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

        test("SELECT * from XYZZY, ABC", 5)
        test("select * from SYS.XYZZY", 4)
        test("Select A from Sys.dual", 4)
        test("Select A,B,C from Sys.dual", 6)
        test("Select A, B, C from Sys.dual", 6)
        test("Select A, B, C from Sys.dual, Table2   ", 7)
        test("Xelect A, B, C from Sys.dual", 0, 0)
        test("Select A, B, C frox Sys.dual", 0, 15)
        test("Select", 0, 6)
        test("Select &&& frox Sys.dual", 0, 7)
        test("Select A from Sys.dual where a in ('RED','GREEN','BLUE')", 12)
        test(
            "Select A from Sys.dual where a in ('RED','GREEN','BLUE') and b in"
            " (10,20,30)",
            20,
        )
        test(
            "Select A,b from table1,table2 where table1.id eq table2.id -- test out"
            " comparison operators",
            10,
        )

    def testParseConfigFile(self):
        def test(fnam, numToks, resCheckList):

            with open(fnam) as infile:
                iniFileLines = "\n".join(infile.read().splitlines())
            iniData = configParse.inifile_BNF().parse_string(iniFileLines)

            self.assertEqual(
                len(flatten(iniData)), numToks, "file %s not parsed correctly" % fnam,
            )
            for path, expected_value in resCheckList:
                var = iniData
                for attr in path.split("."):
                    var = var[attr]

                self.assertEqual(
                    var,
                    expected_value,
                    "ParseConfigFileTest: failed to parse ini {!r} as expected {},"
                    " found {}".format(path, expected_value, var),
                )

        ini_data = configParse.inifile_BNF().parse_string("[users]\nK = 8\n")
        self.assertEqual(ini_data, {"users": {"K": "8"}})

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
        expected = [["glossary", [["title", "example glossary"]]]]
        result = jsonObject.parse_string(jsons)
        self.assertEqual(result, expected, "failed test {}".format(jsons))

    def testParseJSONData(self):
        expected = [
            [[
                "glossary",
                [
                    ["title", "example glossary"],
                    [
                        "GlossDiv",
                        [
                            ["title", "S"],
                            [
                                "GlossList",
                                [[
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
                                        "A meta-markup language, used to create markup"
                                        " languages such as DocBook.",
                                    ],
                                    ["GlossSeeAlso", ["GML", "XML", "markup"]],
                                    ["EmptyDict", []],
                                    ["EmptyList", [[]]],
                                ]],
                            ],
                        ],
                    ],
                ],
            ]],
            [[
                "menu",
                [
                    ["id", "file"],
                    ["value", "File:"],
                    [
                        "popup",
                        [[
                            "menuitem",
                            [
                                [["value", "New"], ["onclick", "CreateNewDoc()"],],
                                [["value", "Open"], ["onclick", "OpenDoc()"]],
                                [["value", "Close"], ["onclick", "CloseDoc()"]],
                            ],
                        ]],
                    ],
                ],
            ]],
            [[
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
                            ["onMouseUp", "sun1.opacity = (sun1.opacity / 100) * 90;",],
                        ],
                    ],
                ],
            ]],
            [[
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
                                        ["configGlossary:adminEmail", "ksm@pobox.com",],
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
                                        ["defaultFileTemplate", "articleTemplate.htm",],
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
                                        ["searchEngineRobotsDb", "WEB-INF/robots.db",],
                                        ["useDataStore", True],
                                        ["dataStoreClass", "org.cofax.SqlDataStore",],
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
                                ["servlet-class", "org.cofax.cms.CofaxToolsServlet",],
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
            ]],
            [[
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
                            [["id", "About"], ["label", "About Adobe CVG Viewer..."],],
                        ],
                    ],
                ],
            ]],
        ]

        for t, exp in zip((test1, test2, test3, test4, test5), expected):
            result = jsonObject.parse_string(t)

            self.assertEqual(result, exp, "failed test {}".format(t))

    def testParseCommaSeparatedValues(self):
        testData = [
            "d, e, j k , m  ",
            "m  ",
            "a,b,c,100.2,,3",
            "'Hello, World', f, g , , 5.1,x",
            "John Doe, 123 Main St., Cleveland, Ohio",
            "Jane Doe, 456 St. James St., Los Angeles , California   ",
            "",
        ]
        testVals = [
            [(2, "j k"), (3, "m")],
            [(0, "m")],
            [(3, "100.2"), (4, ""), (5, "3")],
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
            results = comma_separated_list.parse_string(line)
            for t in tests:
                self.assertTrue(
                    results.length() > t[0] and results[t[0]] == t[1],
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
        table["terminal_string"] = quoted_string
        table["meta_identifier"] = Word(alphas + "_", alphas + "_" + nums)
        table["integer"] = Word(nums)

        parsers = ebnf.parse(grammar, table)
        ebnf_parser = parsers["syntax"]

        self.assertEqual(
            len(list(parsers.keys())), 13, "failed to construct syntax grammar"
        )

        parsed_chars = ebnf_parser.parse_string(grammar)

        self.assertEqual(
            len(flatten(parsed_chars)), 98, "failed to tokenize grammar correctly",
        )

    def testParseIDL(self):
        def test(string, numToks, errloc=0):

            try:
                bnf = idlParse.CORBA_IDL_BNF()
                tokens = bnf.parse_string(string)

                tokens = flatten(tokens)

                self.assertEqual(
                    len(tokens),
                    numToks,
                    "error matching IDL string, {} -> {}".format(string, str(tokens)),
                )
            except ParseException as err:

                self.assertEqual(
                    numToks,
                    0,
                    "unexpected ParseException while parsing {}\n{}".format(
                        string, str(err)
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
            142,
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
            for srvr, startloc, endloc in timeServerPattern.scan_string(testdata)
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
            "failed scan_string()",
        )

        # test for stringEnd detection in scan_string
        foundStringEnds = [r for r in StringEnd().scan_string("xyzzy")]

        self.assertTrue(foundStringEnds, "Failed to find StringEnd in scan_string")

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
            (t[0], b, e) for (t, b, e) in sglQuotedString.scan_string(testData)
        ]

        self.assertTrue(
            len(sglStrings) == 1
            and (sglStrings[0][1] == 17 and sglStrings[0][2] == 47),
            "single quoted string failure",
        )

        dblStrings = [
            (t[0], b, e) for (t, b, e) in dblQuotedString.scan_string(testData)
        ]

        self.assertTrue(
            len(dblStrings) == 1
            and (dblStrings[0][1] == 154 and dblStrings[0][2] == 184),
            "double quoted string failure",
        )

        allStrings = [(t[0], b, e) for (t, b, e) in quoted_string.scan_string(testData)]

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
            (t[0], b, e) for (t, b, e) in sglQuotedString.scan_string(escapedQuoteTest)
        ]

        self.assertTrue(
            len(sglStrings) == 1
            and (sglStrings[0][1] == 17 and sglStrings[0][2] == 66),
            "single quoted string escaped quote failure (%s)" % str(sglStrings[0]),
        )

        dblStrings = [
            (t[0], b, e) for (t, b, e) in dblQuotedString.scan_string(escapedQuoteTest)
        ]

        self.assertTrue(
            len(dblStrings) == 1
            and (dblStrings[0][1] == 83 and dblStrings[0][2] == 132),
            "double quoted string escaped quote failure (%s)" % str(dblStrings[0]),
        )

        allStrings = [
            (t[0], b, e) for (t, b, e) in quoted_string.scan_string(escapedQuoteTest)
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
            (t[0], b, e) for (t, b, e) in sglQuotedString.scan_string(dblQuoteTest)
        ]

        self.assertTrue(
            len(sglStrings) == 1
            and (sglStrings[0][1] == 17 and sglStrings[0][2] == 66),
            "single quoted string escaped quote failure (%s)" % str(sglStrings[0]),
        )
        dblStrings = [
            (t[0], b, e) for (t, b, e) in dblQuotedString.scan_string(dblQuoteTest)
        ]

        self.assertTrue(
            len(dblStrings) == 1
            and (dblStrings[0][1] == 83 and dblStrings[0][2] == 132),
            "double quoted string escaped quote failure (%s)" % str(dblStrings[0]),
        )
        allStrings = [
            (t[0], b, e) for (t, b, e) in quoted_string.scan_string(dblQuoteTest)
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

        for expr, test_string in [
            (dblQuotedString, '"' + "\\xff" * 500),
            (sglQuotedString, "'" + "\\xff" * 500),
            (quoted_string, '"' + "\\xff" * 500),
            (quoted_string, "'" + "\\xff" * 500),
            (QuotedString('"'), '"' + "\\xff" * 500),
            (QuotedString("'"), "'" + "\\xff" * 500),
        ]:
            expr.parse_string(test_string + test_string[0])
            try:
                with Timer("testing catastrophic RE backtracking", silent=True):
                    expr.parse_string(test_string)
            except Exception:
                continue

    def testCaselessOneOf(self):

        caseless1 = one_of("d a b c aA B A C", caseless=True)
        caseless1str = str(caseless1)

        caseless2 = one_of("d a b c Aa B A C", caseless=True)
        caseless2str = str(caseless2)

        self.assertEqual(
            caseless1str.upper(),
            caseless2str.upper(),
            "one_of not handling caseless option properly",
        )

        res = caseless1[...].parse_string("AAaaAaaA")

        self.assertEqual(res.length(), 4, "caseless1 one_of failed")
        self.assertEqual(
            "".join(res), "aA" * 4, "caseless1 CaselessLiteral return failed"
        )

        res = caseless2[...].parse_string("AAaaAaaA")

        self.assertEqual(res.length(), 4, "caseless2 one_of failed")
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
            lineno(s, testdata) for t, s, e in cStyleComment.scan_string(testdata)
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
            lineno(s, testdata) for t, s, e in html_comment.scan_string(testdata)
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
            len(cppStyleComment.search_string(testSource)[1][0]),
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

        results = phrase.parse_string("xavier yeti alpha beta charlie will beaver")

        for key, ln in [("Head", 2), ("ABC", 3), ("Tail", 2)]:
            self.assertEqual(
                results[key].length(),
                ln,
                "expected %d elements in %s, found %s" % (ln, key, str(results[key])),
            )

    def testParseKeyword(self):

        kw = Keyword("if")
        lit = Literal("if")

        def test(s, litShouldPass, kwShouldPass):
            try:
                lit.parse_string(s)
            except Exception:
                if litShouldPass:
                    self.assertTrue(
                        False, "Literal failed to match %s, should have" % s
                    )
            else:
                if not litShouldPass:
                    self.assertTrue(False, "Literal matched %s, should not have" % s)

            try:
                kw.parse_string(s)
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

        num = Word(nums).set_parser_name("num")("base10")
        hexnum = Combine("0x" + Word(nums)).set_parser_name("hexnum")("hex")
        name = Word(alphas).set_parser_name("word")("word")
        list_of_num = delimited_list(hexnum | num | name, ",")

        tokens = list_of_num.parse_string("1, 0x2, 3, 0x4, aaa")
        self.assertParseResultsEquals(
            tokens,
            expected_list=["1", "0x2", "3", "0x4", "aaa"],
            expected_dict={"base10": ["1", "3"], "hex": ["0x2", "0x4"], "word": "aaa",},
        )

        lbrack = Literal("(").suppress()
        rbrack = Literal(")").suppress()
        integer = Word(nums).set_parser_name("int")
        variable = Word(alphas, max=1).set_parser_name("variable")
        relation_body_item = (
            variable | integer | quoted_string.copy().add_parse_action(remove_quotes)
        )
        relation_name = Word(alphas + "_", alphanums + "_")
        relation_body = lbrack + Group(delimited_list(relation_body_item)) + rbrack
        Goal = Dict(Group(relation_name + relation_body))
        Comparison_Predicate = Group(variable + one_of("< >") + integer)("pred")
        Query = Goal("head") + ":-" + delimited_list(Goal | Comparison_Predicate)

        test = """Q(x,y,z):-Bloo(x,"Mitsis",y),Foo(y,z,1243),y>28,x<12,x>3"""

        queryRes = Query.parse_string(test)

        self.assertParseResultsEquals(
            queryRes["pred"],
            expected_list=[["y", ">", "28"], ["x", "<", "12"], ["x", ">", "3"]],
            msg="Incorrect list for attribute pred, %s" % str(queryRes["pred"]),
        )

    def testSkipTo(self):
        thingToFind = Literal("working")
        test_expr = (
            SkipTo(Literal(";"), include=True, ignore=cStyleComment) + thingToFind
        )

        def tryToParse(someText, fail_expected=False):
            if fail_expected:
                with self.assertRaises(ParseException):
                    test_expr.parse_string(someText)
            else:
                test_expr.parse_string(someText)

        # This first test works, as the SkipTo expression is immediately following the ignore expression (cStyleComment)
        self.assertEqual(
            test_expr.parse_string("some text /* comment with ; in */; working"),
            ["some text /* comment with ; in */", [";"], "working"],
        )
        # This second test previously failed, as there is text following the ignore expression, and before the SkipTo expression.
        self.assertEqual(
            test_expr.parse_string(
                "some text /* comment with ; in */some other stuff; working"
            ),
            ["some text /* comment with ; in */some other stuff", [";"], "working"],
        )

        # tests for optional fail_on argument
        test_expr = (
            SkipTo(Literal(";"), include=True, ignore=cStyleComment, fail_on="other")
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
        result = expr.parse_string(text)
        self.assertTrue(
            isinstance(result["prefix"], str),
            "SkipTo created with wrong saveAsList attribute",
        )

        alpha_word = (
            ~Literal("end") + Word(alphas, as_keyword=True)
        ).set_parser_name("alpha")
        num_word = Word(nums, as_keyword=True).set_parser_name("int")

        def test(expr, test_string, expected_list, expected_dict):
            if (expected_list, expected_dict) == (None, None):
                with TestCase.assertRaises(
                    self,
                    Exception,
                    msg="{} failed to parse {!r}".format(expr, test_string),
                ):
                    expr.parse_string(test_string)
            else:
                result = expr.parse_string(test_string)
                self.assertParseResultsEquals(
                    result, expected_list=expected_list, expected_dict=expected_dict
                )

        # ellipses for SkipTo
        e = ... + Literal("end")
        test(e, "start 123 end", ["start 123", "end"], {"_skipped": "start 123"})

        e = Literal("start") + ... + Literal("end")
        test(e, "start 123 end", ["start", "123", "end"], {"_skipped": "123"})

        e = Literal("start") + ...
        test(e, "start 123 end", None, None)

        e = And(["start", ..., "end"], whitespaces.CURRENT)
        test(e, "start 123 end", ["start", "123", "end"], {"_skipped": "123"})

        e = And([..., "end"], whitespaces.CURRENT)
        test(e, "start 123 end", ["start 123", "end"], {"_skipped": "start 123"})

        e = "start" + (num_word | ...) + "end"
        test(e, "start 456 end", ["start", "456", "end"], {})
        test(
            e, "start 123 456 end", ["start", "123", "456", "end"], {"_skipped": "456"},
        )
        test(e, "start end", ["start", "end"], {"_skipped": ""})

        e = "start" + (alpha_word[...] & num_word[...] | ...) + "end"
        test(e, "start 456 red end", ["start", "456", "red", "end"], {})
        test(e, "start red 456 end", ["start", "red", "456", "end"], {})
        test(
            e,
            "start 456 red + end",
            ["start", "456", "red", "+", "end"],
            {"_skipped": "+"},
        )
        test(e, "start red end", ["start", "red", "end"], {})
        test(e, "start 456 end", ["start", "456", "end"], {})
        test(e, "start end", ["start", "end"], {})
        test(e, "start 456 + end", ["start", "456", "+", "end"], {"_skipped": ["+"]})

        e = "start" + (alpha_word[1, ...] & num_word[1, ...] | ...) + "end"
        test(e, "start 456 red end", ["start", "456", "red", "end"], {})
        test(e, "start red 456 end", ["start", "red", "456", "end"], {})
        test(
            e,
            "start 456 red + end",
            ["start", "456", "red", "+", "end"],
            {"_skipped": ["+"]},
        )
        test(e, "start red end", ["start", "red", "end"], {"_skipped": "red"})
        test(e, "start 456 end", ["start", "456", "end"], {"_skipped": "456"})
        test(e, "start end", ["start", "end"], {"_skipped": ""})
        test(e, "start 456 + end", ["start", "456 +", "end"], {"_skipped": "456 +"})

        e = "start" + (alpha_word | ...) + (num_word | ...) + "end"
        test(e, "start red 456 end", ["start", "red", "456", "end"], {})
        test(e, "start red end", ["start", "red", "end"], {"_skipped": ""})
        test(e, "start end", ["start", "end"], {"_skipped": ""})

        e = Literal("start") + ... + "+" + ... + "end"
        test(
            e,
            "start red + 456 end",
            ["start", "red", "+", "456", "end"],
            {"_skipped": ["red", "456"]},
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
            success1, _ = expr.run_tests(successful_tests)
            success2, _ = expr.run_tests(failure_tests, failureTests=True)
            all_success = all_success and success1 and success2
            if not all_success:

                break

        self.assertTrue(all_success, "failed getItem_ellipsis test")

    def testEllipsisRepetionWithResultsNames(self):

        label = Word(alphas)
        val = integer
        parser = label("label") + ZeroOrMore(val)("values")

        _, results = parser.run_tests(
            """
            a 1
            b 1 2 3
            c
            """
        )
        expected = [
            (["a", 1], {"label": "a", "values": 1}),
            (["b", 1, 2, 3], {"label": "b", "values": [1, 2, 3]}),
            (["c"], {"label": "c", "values": []}),
        ]
        for (test, result), (exp_list, exp_dict) in zip(results, expected):
            self.assertParseResultsEquals(
                result, expected_list=exp_list, expected_dict=exp_dict
            )

        parser = label("label") + val[...]("values")

        _, results = parser.run_tests(
            """
            a 1
            b 1 2 3
            c
            """
        )
        expected = [
            (["a", 1], {"label": "a", "values": 1}),
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
        _, results = parser.run_tests(
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

        test_string = r"""
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

        def test(quote_expr, expected):
            self.assertEqual(
                quote_expr.search_string(test_string)[0][0],
                expected,
                "failed to match {}, expected '{}', got '{}'".format(
                    quote_expr, expected, quote_expr.search_string(test_string)[0]
                ),
            )

        test(colonQuotes, r"sdf:jls:djf")
        test(dashQuotes, r"sdf:jls::-djf: sl")
        test(hatQuotes, r"sdf:jls")
        test(hatQuotes1, r"sdf:jls^--djf")
        test(dblEqQuotes, r"sdf:j=ls::--djf: sl")
        test(QuotedString(":::"), "jls::--djf: sl")
        test(QuotedString("==", end_quote_char="--"), r"sdf\:j=lz::")
        test(
            QuotedString("^^^", multiline=True),
            r"""==sdf\:j=lz::--djf: sl=^^=kfsjf
            sdlfjs ==sdf\:j=ls::--djf: sl==kfsjf""",
        )
        with self.assertRaises():
            QuotedString("", "\\")

    def testRecursiveCombine(self):

        testInput = "myc(114)r(11)dd"
        Stream = Forward()
        Stream << Optional(Word(alphas)) + Optional("(" + Word(nums) + ")" + Stream)
        expected = ["".join(Stream.parse_string(testInput))]

        Stream = Forward()
        Stream << Combine(
            Optional(Word(alphas)) + Optional("(" + Word(nums) + ")" + Stream)
        )
        testVal = Stream.parse_string(testInput)

        self.assertParseResultsEquals(testVal, expected_list=expected)

    def testParseResultsWithNamedTuple(self):

        expr = Literal("A")("Achar").add_parse_action(lambda: [("A", "Z")])

        res = expr.parse_string("A")

        self.assertParseResultsEquals(
            res,
            expected_dict={"Achar": ("A", "Z")},
            msg="Failed accessing named results containing a tuple, got {!r}".format(res["Achar"]),
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
        expected = [
            ("startBody", False, "", ""),
            ("startBody", False, "#00FFCC", ""),
            ("startBody", True, "#00FFAA", ""),
            ("startBody", False, "#00FFBB", "black"),
            ("startBody", True, "", ""),
            ("endBody", False, "", ""),
        ]

        bodyStart, bodyEnd = makeHTMLTags("BODY")
        results = list((bodyStart | bodyEnd).scan_string(test))
        for (u, s, e), (expectedType, expectedEmpty, expectedBG, expectedFG) in zip(
            results, expected
        ):
            if "startBody" in u:
                t = u["startBody"]
                self.assertEqual(
                    bool(t["empty"]),
                    expectedEmpty,
                    "expected {} token, got {}".format(
                        expectedEmpty and "empty" or "not empty",
                        t["empty"] and "empty" or "not empty",
                    ),
                )
                self.assertEqual(
                    t["bgcolor"],
                    expectedBG,
                    "failed to match BGCOLOR, expected {}, got {}".format(
                        expectedBG, t["bgcolor"]
                    ),
                )
                self.assertEqual(
                    t["fgcolor"],
                    expectedFG,
                    "failed to match FGCOLOR, expected {}, got {}".format(
                        expectedFG, t["bgcolor"]
                    ),
                )
            elif "endBody" in u:

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
        uword = Word(ualphas).add_parse_action(upcase_tokens)

        uword.search_string(a)

        uword = Word(ualphas).add_parse_action(downcase_tokens)

        uword.search_string(a)

        kw = Group(
            Keyword("mykey", caseless=True).add_parse_action(upcase_tokens)("rname")
        )
        ret = kw.parse_string("mykey")

        self.assertEqual(
            ret["rname"], "MYKEY", "failed to upcase with named result (parsing_common)"
        )

        kw = Group(
            Keyword("MYKEY", caseless=True).add_parse_action(downcase_tokens)("rname")
        )
        ret = kw.parse_string("mykey")

        self.assertEqual(ret["rname"], "mykey", "failed to upcase with named result")

        if not IRON_PYTHON_ENV:
            # test html data
            html = (  # .decode('utf-8')
                "<TR class=maintxt bgColor=#ffffff>                 <TD"
                " vAlign=top>Производитель, модель</TD>                 <TD"
                " vAlign=top><STRONG>BenQ-Siemens CF61</STRONG></TD>             "
            )

            # 'Manufacturer, model
            text_manuf = "Производитель, модель"
            manufacturer = Literal(text_manuf)

            td_start, td_end = makeHTMLTags("td")
            manuf_body = (
                td_start.suppress()
                + manufacturer
                + SkipTo(td_end)("cells")
                + td_end.suppress()
            )

            # ~ manuf_body.setDebug()

            # ~ for tokens in manuf_body.scan_string(html):
            # ~ print(tokens)

    def testPrecededBy(self):

        num = Word(nums).add_parse_action(lambda t: int(t.value()))
        interesting_num = PrecededBy(Char("abc")("prefix")) + num
        semi_interesting_num = PrecededBy("_") + num
        crazy_num = PrecededBy(Word("^", "$%^")("prefix"), 10) + num
        boring_num = ~PrecededBy(Char("abc_$%^" + nums)) + num
        very_boring_num = PrecededBy(WordStart()) + num
        finicky_num = PrecededBy(Word("^", "$%^"), retreat=3) + num

        s = "c384 b8324 _9293874 _293 404 $%^$^%$2939"

        for expr, expected_list, expected_dict in [
            (interesting_num, [384, 8324], {"prefix": ["c", "b"]}),
            (semi_interesting_num, [9293874, 293], {}),
            (boring_num, [404], {}),
            (crazy_num, [2939], {"prefix": "^%$"}),
            (very_boring_num, [404], {}),
            (finicky_num, [2939], {}),
        ]:
            result = sum(expr.search_string(s))

            self.assertParseResultsEquals(result, expected_list, expected_dict)

        # infinite loop test - from Issue #127
        string_test = "notworking"
        # negs = Or(['not', 'un'])('negs')
        negs_pb = PrecededBy("not", retreat=100)("negs_lb")
        # negs_pb = PrecededBy(negs, retreat=100)('negs_lb')
        pattern = (negs_pb + Literal("working"))("main")

        results = pattern.search_string(string_test)
        try:
            str(results)
        except RecursionError:
            self.assertTrue(False, "got maximum excursion limit exception")
        else:
            self.assertTrue(True, "got maximum excursion limit exception")

    def testCountedArray(self):

        test_string = "2 5 7 6 0 1 2 3 4 5 0 3 5 4 3"

        integer = Word(nums).add_parse_action(lambda t: int(t[0]))
        countedField = counted_array(integer)

        r = OneOrMore(countedField).parse_string(test_string)

        self.assertParseResultsEquals(
            r, expected_list=[[5, 7], [0, 1, 2, 3, 4, 5], [], [5, 4, 3]]
        )

    # addresses bug raised by Ralf Vosseler
    def testCountedArrayTest2(self):

        test_string = "2 5 7 6 0 1 2 3 4 5 0 3 5 4 3"

        integer = Word(nums).add_parse_action(lambda t: int(t[0]))
        countedField = counted_array(integer)

        dummy = Word("A")
        r = OneOrMore(dummy ^ countedField).parse_string(test_string)

        self.assertParseResultsEquals(
            r, expected_list=[[5, 7], [0, 1, 2, 3, 4, 5], [], [5, 4, 3]]
        )

    def testCountedArrayTest3(self):

        int_chars = "_" + alphas
        array_counter = (
            Word(int_chars).add_parse_action(lambda t: int_chars.index(t[0]))
        )

        #             123456789012345678901234567890
        test_string = "B 5 7 F 0 1 2 3 4 5 _ C 5 4 3"

        integer = Word(nums).add_parse_action(lambda t: int(t[0]))
        countedField = counted_array(integer, int_expr=array_counter)

        r = OneOrMore(countedField).parse_string(test_string)

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
        success = test_patt.run_tests(pass_tests)[0]
        self.assertTrue(success, "failed LineStart passing tests (1)")

        success = test_patt.run_tests(fail_tests, failureTests=True)[0]
        self.assertTrue(success, "failed LineStart failure mode tests (1)")

        with Timer(""):

            whitespaces.CURRENT.set_whitespace(" ")

            test_patt = Word("A") - LineStart() + Word("B")

            # should fail the pass tests too, since \n is no longer valid whitespace and we aren't parsing for it
            success = test_patt.run_tests(pass_tests, failureTests=True)[0]
            self.assertTrue(success, "failed LineStart passing tests (2)")

            success = test_patt.run_tests(fail_tests, failureTests=True)[0]
            self.assertTrue(success, "failed LineStart failure mode tests (2)")

            test_patt = (
                Word("A")
                - LineEnd().suppress()
                + LineStart()
                + Word("B")
                + LineEnd().suppress()
            )
            test_patt.streamline()
            success = test_patt.run_tests(pass_tests)[0]
            self.assertTrue(success, "failed LineStart passing tests (3)")

            success = test_patt.run_tests(fail_tests, failureTests=True)[0]
            self.assertTrue(success, "failed LineStart failure mode tests (3)")

        test = """\
        AAA 1
        AAA 2

          AAA

        B AAA

        """

        test = dedent(test)

        for t, s, e in (LineStart() + "AAA").scan_string(test):

            self.assertEqual(
                test[s], "A", "failed LineStart with insignificant newlines"
            )

        with Timer(""):
            whitespaces.CURRENT.set_whitespace(" ")
            for t, s, e in (LineStart() + "AAA").scan_string(test):

                self.assertEqual(
                    test[s], "A", "failed LineStart with insignificant newlines"
                )

    def testLineAndStringEnd(self):
        with NO_WHITESPACE:
            NLs = OneOrMore(LineEnd)
            bnf1 = delimited_list(Word(alphanums), NLs)
            bnf2 = Word(alphanums) + StringEnd
            bnf3 = Word(alphanums) + SkipTo(StringEnd)
        # TODO: Is bnf2 match last word?  Does bnf3.skipTo(stringEnd) include the \n?
        tests = [
            ("testA\ntestB\ntestC\n", ["testA", "testB", "testC"]),
            ("testD\ntestE\ntestF", ["testD", "testE", "testF"]),
            ("a", ["a"]),
        ]

        for test, expected in tests:
            res1 = bnf1.parse_string(test)

            self.assertEqual(res1, expected)

            res2 = bnf2.search_string(test)[0]

            self.assertEqual(res2, expected[-1:])

            res3 = bnf3.parse_string(test)
            first = res3[0]
            rest = coalesce(res3[1], "")

            self.assertEqual(rest, test[len(first) :].rstrip())

        k = Regex(r"a+")

        tests = [
            (r"aaa", ["aaa"]),
            (r"\naaa", None),
            (r"a\naa", None),
            (r"aaa\n", None),
        ]
        for i, (src, expected) in enumerate(tests):

            if expected is None:
                with self.assertRaisesParseException():
                    k.parse_string(src, parse_all=True)
            else:
                res = k.parse_string(src, parse_all=True)
                self.assertParseResultsEquals(
                    res, expected, msg="Failed on parse_all=True test %d" % i
                )

    def testVariableParseActionArgs(self):
        pa3 = lambda t, l, s: (t if t[0] else 0)
        pa2 = lambda t, l: t
        pa1 = lambda t: t
        pa0 = lambda: None

        class Callable3:
            def __call__(self, t, l, s):
                return t

        class Callable2:
            def __call__(self, t, l):
                return t

        class Callable1:
            def __call__(self, t):
                return t

        class Callable0:
            def __call__(self):
                return

        class CallableS3:
            @staticmethod
            def __call__(t, l, s):
                return t

        class CallableS2:
            @staticmethod
            def __call__(t, l):
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
            def __call__(cls, t, l, s):
                return t

        class CallableC2:
            @classmethod
            def __call__(cls, t, l):
                return t

        class CallableC1:
            @classmethod
            def __call__(cls, t):
                return t

        class CallableC0:
            @classmethod
            def __call__(cls):
                return

        class parse_actionHolder:
            @staticmethod
            def pa3(t, l, s):
                return t

            @staticmethod
            def pa2(t, l):
                return t

            @staticmethod
            def pa1(t):
                return t

            @staticmethod
            def pa0():
                return

        def paArgs(*args):

            return args[0]

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
            def __init__(self, t, l):
                self.t = t

            def __str__(self):
                return self.t[0]

        class ClassAsPA3:
            def __init__(self, t, l, s):
                self.t = t

            def __str__(self):
                return self.t[0]

        class ClassAsPAStarNew(tuple):
            def __new__(cls, *args):
                return tuple.__new__(cls, *args[0])

            def __str__(self):
                return "".join(self)

        A = Literal("A").add_parse_action(pa0)
        B = Literal("B").add_parse_action(pa1)
        C = Literal("C").add_parse_action(pa2)
        D = Literal("D").add_parse_action(pa3)
        E = Literal("E").add_parse_action(Callable0())
        F = Literal("F").add_parse_action(Callable1())
        G = Literal("G").add_parse_action(Callable2())
        H = Literal("H").add_parse_action(Callable3())
        I = Literal("I").add_parse_action(CallableS0())
        J = Literal("J").add_parse_action(CallableS1())
        K = Literal("K").add_parse_action(CallableS2())
        L = Literal("L").add_parse_action(CallableS3())
        M = Literal("M").add_parse_action(CallableC0())
        N = Literal("N").add_parse_action(CallableC1())
        O = Literal("O").add_parse_action(CallableC2())
        P = Literal("P").add_parse_action(CallableC3())
        Q = Literal("Q").add_parse_action(paArgs)
        R = Literal("R").add_parse_action(parse_actionHolder.pa3)
        S = Literal("S").add_parse_action(parse_actionHolder.pa2)
        T = Literal("T").add_parse_action(parse_actionHolder.pa1)
        U = Literal("U").add_parse_action(parse_actionHolder.pa0)
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
        test_string = "VUTSRQPONMLKJIHGFEDCBA"
        res = gg.parse_string(test_string)

        self.assertParseResultsEquals(
            res,
            expected_list=list(test_string),
            msg="Failed to parse using variable length parse actions",
        )

        A = Literal("A").add_parse_action(ClassAsPA0)
        B = Literal("B").add_parse_action(ClassAsPA1)
        C = Literal("C").add_parse_action(ClassAsPA2)
        D = Literal("D").add_parse_action(ClassAsPA3)
        E = Literal("E").add_parse_action(ClassAsPAStarNew)

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
        test_string = "VUTSRQPONMLKJIHGFEDCBA"
        res = gg.parse_string(test_string)

        self.assertEqual(
            list(map(str, res)),
            list(test_string),
            "Failed to parse using variable length parse actions "
            "using class constructors as parse actions",
        )

    def testSingleArgException(self):
        with self.assertRaises(" missing 2 required positional arguments"):
            raise ParseException("just one arg")

    def testOriginalTextFor(self):
        def rfn(t):
            return "%s:%d" % (t["startImg"]["src"], len("".join(t)))

        start = originalTextFor(makeHTMLTags("IMG")[0], as_string=False)

        # don't replace our fancy parse action with rfn,
        # append rfn to the list of parse actions
        start1 = start.add_parse_action(rfn).set_parser_name("get image")

        text = """_<img src="images/cal.png"
            alt="cal image" width="16" height="15">_"""
        s = start1.transform_string(text)
        self.assertTrue(
            s.startswith("_images/cal.png:"), "failed to preserve input s properly"
        )
        self.assertTrue(
            s.endswith("77_"), "failed to return full original text properly"
        )

        tag_fields = start.search_string(text)[0][0]["startImg"]
        if VERBOSE:
            self.assertEqual(
                sorted(tag_fields.keys()),
                ["alt", "empty", "height", "src", "tag", "width"],
                "failed to preserve results names in originalTextFor",
            )

    def testPackratParsingCacheCopy(self):

        integer = Word(nums).set_parser_name("integer")
        id = Word(alphas + "_", alphanums + "_")
        simpleType = Literal("int")
        arrayType = simpleType + ("[" + delimited_list(integer) + "]")[...]
        varType = arrayType | simpleType
        varDec = varType + delimited_list(id + Optional("=" + integer)) + ";"

        codeBlock = Literal("{}")
        funcDef = (
            Optional(varType | "void")
            + id
            + "("
            + (delimited_list(varType + id) | "void" | Empty)
            + ")"
            + codeBlock
        )

        program = varDec | funcDef
        input = "int f(){}"
        results = program.parse_string(input)

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
                function_name + LPAR + Optional(delimited_list(expr)) + RPAR
            ).set_parser_name("functionCall")
            | identifier.set_parser_name("ident")  # .setDebug()#.setBreak()
        )

        stmt = DO + Group(delimited_list(identifier + ".*" | expr))
        result = stmt.parse_string("DO Z")

        self.assertEqual(
            result[1].length(), 1, "packrat parsing is duplicating And term exprs"
        )

    def testWithAttributeParseAction(self):
        """
        This unit test checks with_attribute in these ways:

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
                with_attribute(b="x"),
                # with_attribute(B="x"),
                with_attribute(**{"b": "x"}),
                # with_attribute(("B", "x")),
                with_class("boo"),
            ],
            expected,
        ):
            expr = tagStart.add_parse_action(attrib) + Word(nums)("value") + tagEnd
            result = expr.search_string(data)

            self.assertEqual(
                result,
                exp,
                "Failed test, expected {}, got {}".format(expected, result),
            )

    def testNestedExpressions(self):
        """
        This unit test checks nested_expr in these ways:
        - use of default arguments
        - use of non-default arguments (such as a mo_parsing-defined comment
          expression in place of quoted_string)
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

        expr = nested_expr()

        expected = [["ax", "+", "by"], "*C"]
        result = expr.parse_string(teststring)

        self.assertEqual(result, expected, "Defaults didn't work. That's a bad sign.")

        # Going through non-defaults, one by one; trying to think of anything
        # odd that might not be properly handled.

        # Change opener
        teststring = "[[ ax + by)*C)"
        expected = [["ax", "+", "by"], "*C"]
        expr = nested_expr(opener="[")
        result = expr.parse_string(teststring)

        self.assertEqual(result, expected, "Non-default opener didn't work.")

        # Change closer
        teststring = "((ax + by]*C]"
        expected = [["ax", "+", "by"], "*C"]
        expr = nested_expr(closer="]")
        result = expr.parse_string(teststring)

        self.assertEqual(result, expected, "Non-default closer didn't work.")

        # #Multicharacter opener, closer
        # opener = "bar"
        # closer = "baz"
        opener, closer = map(Literal, ["bar", "baz"])
        expr = nested_expr(opener, closer, content=Regex(r"([^b ]|b(?!a)|ba(?![rz]))+"))

        teststring = "barbar ax + bybaz*Cbaz"
        expected = [["ax", "+", "by"], "*C"]
        # expr = nested_expr(opener, closer)
        result = expr.parse_string(teststring)

        self.assertEqual(
            result, expected, "Multicharacter opener and closer didn't work."
        )

        # Lisp-ish comments
        comment = Regex(r";;[^\n]*")
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

        expr = nested_expr(ignore_expr=comment)
        result = expr.parse_string(teststring)

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
        expr = nested_expr(ignore_expr=(comment ^ quoted_string))
        result = expr.parse_string(teststring)

        self.assertEqual(
            result,
            expected,
            'Lisp-ish comments (";; <...> $") and quoted strings didn\'t work.',
        )

    def testWordExclude(self):
        allButPunc = Word(printables, exclude=".,:;-_!?")
        test = "Hello, Mr. Ed, it's Wilbur!"
        result = allButPunc.search_string(test)

        self.assertEqual(
            result,
            [["Hello"], ["Mr"], ["Ed"], ["it's"], ["Wilbur"]],
            "failed WordExcludeTest",
        )

    def testParseAll(self):

        test_expr = Word("A")

        tests = [
            ("AAAAA", False, True),
            ("AAAAA", True, True),
            ("AAABB", False, True),
            ("AAABB", True, False),
        ]
        for s, parse_allFlag, shouldSucceed in tests:
            try:
                print("'{}' parse_all={} (shouldSucceed={})".format(
                    s, parse_allFlag, shouldSucceed
                ))
                test_expr.parse_string(s, parse_all=parse_allFlag)
                self.assertTrue(
                    shouldSucceed, "successfully parsed when should have failed"
                )
            except ParseException as pe:
                self.assertFalse(
                    shouldSucceed, "failed to parse when should have succeeded"
                )

        # add test for trailing comments
        whitespaces.CURRENT.add_ignore(cppStyleComment)

        tests = [
            ("AAAAA //blah", False, True),
            ("AAAAA //blah", True, True),
            ("AAABB //blah", False, True),
            ("AAABB //blah", True, False),
        ]
        for s, parse_allFlag, shouldSucceed in tests:
            try:
                print("'{}' parse_all={} (shouldSucceed={})".format(
                    s, parse_allFlag, shouldSucceed
                ))
                test_expr.parse_string(s, parse_all=parse_allFlag)
                self.assertTrue(
                    shouldSucceed, "successfully parsed when should have failed"
                )
            except ParseException as pe:
                self.assertFalse(
                    shouldSucceed, "failed to parse when should have succeeded"
                )

        # add test with very long expression string
        # test_expr = MatchFirst([Literal(c) for c in printables if c != 'B'])[1, ...]
        anything_but_an_f = OneOrMore(MatchFirst([
            Literal(c) for c in printables if c != "f"
        ]))
        test_expr = Word("012") + anything_but_an_f

        tests = [
            ("00aab", False, True),
            ("00aab", True, True),
            ("00aaf", False, True),
            ("00aaf", True, False),
        ]
        for s, parse_allFlag, shouldSucceed in tests:
            try:
                print("'{}' parse_all={} (shouldSucceed={})".format(
                    s, parse_allFlag, shouldSucceed
                ))
                test_expr.parse_string(s, parse_all=parse_allFlag)
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
            quoted_string,
            QuotedString('"', esc_quote='""'),
            QuotedString("'", esc_quote="''"),
            QuotedString("^"),
            QuotedString("<", end_quote_char=">"),
        )
        for expr in testExprs:
            strs = delimited_list(expr).search_string(src)

            self.assertTrue(
                bool(strs), "no matches found for test expression '%s'" % expr
            )
            for lst in strs:
                self.assertEqual(
                    lst.length(),
                    2,
                    "invalid match found for test expression '%s'" % expr,
                )

        src = """'ms1',1,0,'2009-12-22','2009-12-22 10:41:22') ON DUPLICATE KEY UPDATE sent_count = sent_count + 1, mtime = '2009-12-22 10:41:22';"""
        tok_sql_quoted_value = QuotedString(
            "'", "\\", "''", True, False
        ) ^ QuotedString('"', "\\", '""', True, False)
        tok_sql_computed_value = Word(nums)
        tok_sql_identifier = Word(alphas)

        val = tok_sql_quoted_value | tok_sql_computed_value | tok_sql_identifier
        vals = delimited_list(val)

        self.assertEqual(
            vals.parse_string(src).length(), 5, "error in greedy quote escaping"
        )

    def testWordBoundaryExpressions(self):

        ws = WordStart()
        we = WordEnd()
        vowel = one_of(list("AEIOUY"))
        consonant = one_of(list("BCDFGHJKLMNPQRSTVWXZ"))

        with whitespaces.NO_WHITESPACE:
            leadingConsonant = ws + consonant
            leadingVowel = ws + vowel
            trailingConsonant = consonant + we
            trailingVowel = vowel + we
            internalVowel = ~ws + vowel + ~we

            bnf = leadingVowel | trailingVowel

        trailingConsonant.search_string("ABC DEF")

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
                flatten(e.search_string(t))
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
            res1 = parser.parse_string("bam boo")

            res2 = parser.parse_string("boo bam")

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
        p1res = parser1.parse_string(the_input)
        p2res = parser2.parse_string(the_input)
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
        modifiers = (
            Optional(with_stmt("with_stmt")) & Optional(using_stmt("using_stmt"))
        )

        result = modifiers.parse_string(
            "with foo=bar bing=baz using id-deadbeef", parse_all=True
        )
        expecting = {
            "with_stmt": {"overrides": [
                {"key": "foo", "value": "bar"},
                {"key": "bing", "value": "baz"},
            ]},
            "using_stmt": {"id": "id-deadbeef"},
        }
        self.assertEqual(result, expecting)

        with self.assertRaisesParseException():
            result = modifiers.parse_string(
                "with foo=bar bing=baz using id-deadbeef using id-feedfeed",
                parse_all=True,
            )

    def testOptionalEachTest3(self):

        foo = Literal("foo")
        bar = Literal("bar")

        openBrace = Suppress(Literal("{"))
        closeBrace = Suppress(Literal("}"))

        exp = openBrace + (foo[1, ...]("foo") & bar[...]("bar")) + closeBrace

        self.assertEqual(exp.parse_string("{foo}"), ["foo"])
        self.assertEqual(
            exp.parse_string("{bar foo bar foo bar foo}"),
            ["bar", "foo", "bar", "foo", "bar", "foo"],
        )

        self.assertEqual(
            exp.parse_string("{foo foo bar foo bar bar}"),
            ["foo", "foo", "bar", "foo", "bar", "bar"],
        )

        with TestCase.assertRaises(self, ParseException):
            exp.parse_string("{bar}")

    def testOptionalEachTest4(self):

        expr = (~iso8601_date + integer("id")) & (Group(iso8601_date)("date*")[...])

        expr.run_tests(
            """
            1999-12-31 100 2001-01-01
            42
            """
        )

    def testEachWithParseFatalException(self):
        option_expr = Keyword("options") - "(" + integer + ")"
        step_expr1 = Keyword("step") - "(" + integer + ")"
        step_expr2 = Keyword("step") - "(" + integer + "Z" + ")"
        step_expr = step_expr1 ^ step_expr2
        parser = option_expr & step_expr[...]

        with self.assertRaises(
            'Expecting integer, found "A) options" (at char 5), (line:1, col:6)'
        ):
            parser.parse_string("step(A) options(100)", parse_all=True)

        with self.assertRaises('Expecting integer, found "A'):
            parser.parse_string("options(100) step(A)", parse_all=True)

        tests = [
            (
                # this test fails because the step_expr[...] means ZeroOrMore
                # so "step(A)" does not match, which means zero matches
                # resulting in an error expecting an early end-of-line
                # 01234567890123456789
                "options(100) step(A)",
                'Expecting integer, found "A)" (at char 18), (line:1, col:19)',
            ),
            (
                "step(A) options(100)",
                'Expecting integer, found "A) options" (at char 5), (line:1, col:6)',
            ),
            (
                "options(100) step(100A)",
                """Expecting {)} | {Z}, found "A)" (at char 21), (line:1, col:22)""",
            ),
            (
                "options(100) step(22) step(100ZA)",
                """Expecting ), found "A)" (at char 31), (line:1, col:32)""",
            ),
        ]

        success, output = parser.run_tests(
            [test_str for test_str, expected in tests], failureTests=True
        )
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
        res4 = "ID:PARI12345678 DOB: INFO:I am cool"

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
            # search_string RETURNS Tokens IN Groups, ADD THEM TOGETHER FOR ONE Group
            person = sum(person_data.search_string(test))
            result = "ID:{} DOB:{} INFO:{}".format(
                person["id"], person["dob"], person["info"]
            )
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
            res = dob_ref.parse_string(samplestr1)
        except ParseException as pe:
            outstr = pe.mark_inputline()

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

        id_ref = located_expr("ID" + Word(alphanums, exact=12)("id"))

        res = id_ref.search_string(samplestr1)[0][0]

        self.assertEqual(
            samplestr1[res["locn_start"] : res["locn_end"]].strip(),  # CURRENTLY CAN NOT GET END, ONLY GET BEGINNING OF NEXT TOKEN
            "ID PARI12345678",
            "incorrect location calculation",
        )

    def testAddCondition(self):
        numParser = (
            Word(nums)
            .add_parse_action(lambda t: int(t[0]))
            .add_condition(lambda t: t[0] % 2)
            .add_condition(lambda t: t[0] >= 7)
        )

        result = numParser.search_string("1 2 3 4 5 6 7 8 9 10")

        self.assertEqual(result, [[7], [9]], "failed to properly process conditions")

        numParser = Word(nums).add_parse_action(lambda t: int(t[0]))
        rangeParser = numParser("from_") + Suppress("-") + numParser("to")

        result = rangeParser.search_string("1-4 2-4 4-3 5 6 7 8 9 10")

        self.assertEqual(
            result, [[1, 4], [2, 4], [4, 3]], "failed to properly process conditions",
        )

        rangeParser = rangeParser.add_condition(
            lambda t: t["to"] > t["from_"], message="from must be <= to", fatal=False
        )
        result = rangeParser.search_string("1-4 2-4 4-3 5 6 7 8 9 10")

        self.assertEqual(
            result, [[1, 4], [2, 4]], "failed to properly process conditions"
        )

        rangeParser = numParser("from_") + Suppress("-") + numParser("to")
        def check(t):
            return t["to"] > t["from_"]

        rangeParser = rangeParser.add_condition(
            check, message="from must be <= to", fatal=True
        )
        with TestCase.assertRaises(self, Exception):
            rangeParser.search_string("1-4 2-4 4-3 5 6 7 8 9 10")

    def testPatientOr(self):

        # Two expressions and a input string which could - syntactically - be matched against
        # both expressions. The "Literal" expression is considered invalid though, so this PE
        # should always detect the "Word" expression.
        def validate(token):
            if token[0] == "def":
                raise ParseException(token, token.start, "signalling invalid token")
            return token

        a = Word("de").set_parser_name("Word")  # .setDebug()
        b = (
            Literal("def").set_parser_name("Literal").add_parse_action(validate)
        )  # .setDebug()
        c = Literal("d").set_parser_name("d")  # .setDebug()

        # The "Literal" expressions's ParseAction is not executed directly after syntactically
        # detecting the "Literal" Expression but only after the Or-decision has been made
        # (which is too late)...
        try:
            result = (a ^ b ^ c).parse_string("def")
            self.assertEqual(
                result, ["de"], "failed to select longest match, chose %s" % result,
            )
        except ParseException:
            failed = True
        else:
            failed = False
        self.assertFalse(
            failed,
            "invalid logic in Or, fails on longest match with exception in parse"
            " action",
        )

        # from issue #93
        word = Word(alphas).set_parser_name("word")
        word_1 = (
            Word(alphas)
            .set_parser_name("word_1")
            .add_condition(lambda t: len(t[0]) == 1)
        )

        a = word + (word_1 + word ^ word)
        b = word * 3
        c = a ^ b
        c.streamline()

        test_string = "foo bar temp"
        result = c.parse_string(test_string)

        self.assertEqual(result, test_string.split(), "failed to match longest choice")

    def testEachWithOptionalWithResultsName(self):
        result = (
            Optional("foo")("one") & Optional("bar")("two")
        ).parse_string("bar foo")

        self.assertEqual(sorted(result.keys()), ["one", "two"])

    def testEachWithSuppressedOptionalWithResultsName(self):
        result = (
            Suppress(Optional("foo"))("one") & Optional("bar")("two")
        ).parse_string("bar foo")

        self.assertEqual(list(result), ["bar"])
        self.assertEqual(sorted(result.keys()), ["two"])
        self.assertEqual(list(result.items()), [("two", ["bar"])])


    def testUnicodeExpression(self):
        z = "a" | Literal("\u1111")
        z.streamline()
        with self.assertRaises('Expecting {a} | {ᄑ}, found "b"'):
            z.parse_string("b")

    def testTrimArityExceptionMasking(self):
        invalid_message = "<lambda>() missing 1 required positional argument: 't'"
        try:
            Word("a").add_parse_action(lambda t: t[0] + 1).parse_string("aaa")
        except Exception as e:
            exc_msg = str(e)
            self.assertNotEqual(
                exc_msg,
                invalid_message,
                "failed to catch TypeError thrown in wrap_parse_action",
            )

    def testTrimArityExceptionMaskingTest2(self):
        # construct deep call tree
        def A():
            with self.assertRaises("TypeError:"):
                Word("a").add_parse_action(lambda t: t[0] + 1).parse_string("aaa")

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
            realnum.parse_string("3.14159")[0],
            3.14159,
            "failed basic real number parsing",
        )

        # clear parse action that converts to float
        realnum = realnum.clear_parse_action()
        self.assertEqual(
            realnum.parse_string("3.14159")[0],
            "3.14159",
            "failed clearing parse action",
        )

        # add a new parse action that tests if a '.' is prsent
        realnum = realnum.add_parse_action(lambda t: "." in t[0])
        self.assertEqual(
            realnum.parse_string("3.14159")[0],
            True,
            "failed setting new parse action after clearing parse action",
        )

    def testOneOrMoreStop(self):
        test = "BEGIN aaa bbb ccc END"
        BEGIN, END = map(Keyword, ["BEGIN", "END"])
        body_word = Word(alphas).set_parser_name("word")
        for ender in (END, "END", CaselessKeyword("END")):
            expr = BEGIN + OneOrMore(body_word, stop_on=ender) + END
            result = expr.parse_string(test)
            self.assertEqual(
                result,
                test.split(),
                "Did not successfully stop on ending expression %r" % ender,
            )

            expr = BEGIN + body_word[...].stop_on(ender) + END
            result = expr.parse_string(test)
            self.assertEqual(
                result,
                test.split(),
                "Did not successfully stop on ending expression %r" % ender,
            )

        number = Word(nums + ",.()").set_parser_name("number with optional commas")
        parser = OneOrMore(
            Word(alphanums + "-/."), stop_on=number
        )("id").add_parse_action(" ".join) + number("data")
        result = parser.parse_string("        XXX Y/123          1,234.567890")
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
            expr = BEGIN + ZeroOrMore(body_word, stop_on=ender) + END
            result = expr.parse_string(test)
            self.assertEqual(
                result,
                test.split(),
                "Did not successfully stop on ending expression %r" % ender,
            )

            expr = BEGIN + body_word[0, ...].stop_on(ender) + END
            result = expr.parse_string(test)
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
        values = Group(delimited_list(value, ","))

        value_list << lbracket + values + rbracket

        identifier = Word(alphanums + "_.")

        assignment = Group(identifier + equals + Optional(value))
        assignments = Dict(delimited_list(assignment, ";"))
        value_dict << lbrace + assignments + rbrace

        response = assignments
        #      0         1         2         3         4         5         6         7
        #      0123456789012345678901234567890123456789012345678901234567890123456789012
        rsp = (
            "username=goat; errors={username=[already taken, too short]}; empty_field="
        )
        result = response.parse_string(rsp)
        self.assertEqual(
            result["username"],
            "goat",
            "failed to process string in ParseResults correctly",
        )
        self.assertEqual(
            result["errors"]["username"],
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
        assignments = Dict(delimited_list(assignment, ";"))
        value_dict << lbrace + assignments + rbrace

        #      0         1         2
        #      012345678901234567890123456789
        rsp = "e={u=k}"
        result = assignments.parse_string(rsp)
        result_dict = result
        self.assertEqual(
            result_dict["e"]["u"],
            "k",
            "failed to process nested ParseResults correctly",
        )

    def testCondition(self):
        integer = Word(nums).add_parse_action(lambda t: int(t[0]))
        intrange = integer("start") + "-" + integer("end")

        intrange = intrange.add_condition(
            lambda t: t["end"] > t["start"],
            message="invalid range, start must be <= end",
            fatal=True,
        )

        def _range(t, l, s):
            return list(range(t["start"], t["end"] + 1))

        intrange = intrange.add_parse_action(_range)

        indices = delimited_list(intrange | integer)
        indices = indices.add_parse_action(lambda t: sorted(set(t)))

        tests = """\
            # normal data
            1-3,2-4,6,8-10,16

            # lone integer
            11"""
        success, results = indices.run_tests(tests, printResults=False)

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
        success, results = indices.run_tests(
            tests, printResults=False, failureTests=True
        )
        self.assertTrue(success, "failed to raise exception on improper range test")

    def testRunTestsPostParse(self):
        fraction = integer("numerator") + "/" + integer("denominator")

        accum = []

        def eval_fraction(test, result):
            accum.append((test, result))
            return "eval: {}".format(result["numerator"] / result["denominator"])

        success = fraction.run_tests(
            """
                1/2
                3/10
            """,
            postParse=eval_fraction,
        )[0]

        self.assertTrue(success, "failed to parse fractions in RunTestsPostParse")

        expected_accum = [("1/2", [1, "/", 2]), ("3/10", [3, "/", 10])]
        self.assertEqual(
            accum, expected_accum, "failed to call postParse method during run_tests"
        )

    def testRunTestsPostException(self):
        fraction = integer("numerator") + "/" + integer("denominator")
        accum = []

        def eval_fraction(test, result):
            accum.append((test, result))
            return "eval: {}".format(result["numerator"] / result["denominator"])

        with self.assertRaises(Exception):
            fraction.run_tests(
                """
                    1/2
                    1/0
                """,
                postParse=eval_fraction,
            )

    def testCommonExpressions(self):

        success = mac_address.run_tests(
            """
            AA:BB:CC:DD:EE:FF
            AA.BB.CC.DD.EE.FF
            AA-BB-CC-DD-EE-FF
            """
        )[0]
        self.assertTrue(success, "error in parsing valid MAC address")

        success = mac_address.run_tests(
            """
            # mixed delimiters
            AA.BB:CC:DD:EE:FF
            """,
            failureTests=True,
        )[0]
        self.assertTrue(success, "error in detecting invalid mac address")

        success = ipv4_address.run_tests(
            """
            0.0.0.0
            1.1.1.1
            127.0.0.1
            1.10.100.199
            255.255.255.255
            """
        )[0]
        self.assertTrue(success, "error in parsing valid IPv4 address")

        success = ipv4_address.run_tests(
            """
            # out of range value
            256.255.255.255
            """,
            failureTests=True,
        )[0]
        self.assertTrue(success, "error in detecting invalid IPv4 address")

        success = ipv6_address.run_tests(
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

        success = ipv6_address.run_tests(
            """
            # too few values
            1080:0:0:0:8:800:200C

            # too many ::'s, only 1 allowed
            2134::1234:4567::2444:2106
            """,
            failureTests=True,
        )[0]
        self.assertTrue(success, "error in detecting invalid IPv6 address")

        success = number.run_tests(
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

        success = sci_real.run_tests(
            """
            1e12
            -1e12
            3.14159
            6.02e23
            """
        )[0]
        self.assertTrue(success, "error in parsing valid scientific notation reals")

        # any int or real number, returned as float
        success = fnumber.run_tests(
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

        success, results = iso8601_date.run_tests(
            """
            1997
            1997-07
            1997-07-16
            """
        )
        self.assertTrue(success, "error in parsing valid iso8601_date")
        expected = [("1997", None, None), ("1997", "07", None), ("1997", "07", "16")]
        for r, exp in zip(results, expected):
            self.assertTrue(
                (r[1]["year"], r[1]["month"], r[1]["day"]) == exp,
                "failed to parse date into fields",
            )

        success, results = (
            iso8601_date
            .add_parse_action(convertToDate())
            .run_tests("""
            1997-07-16
            """)
        )
        self.assertTrue(
            success, "error in parsing valid iso8601_date with parse action"
        )
        self.assertTrue(results[0][1][0] == datetime_date(1997, 7, 16))

        success, results = iso8601_datetime.run_tests(
            """
            1997-07-16T19:20+01:00
            1997-07-16T19:20:30+01:00
            1997-07-16T19:20:30.45Z
            1997-07-16 19:20:30.45
            """
        )
        self.assertTrue(success, "error in parsing valid iso8601_datetime")

        success, results = (
            iso8601_datetime
            .add_parse_action(convertToDatetime())
            .run_tests("""
            1997-07-16T19:20:30.45
            """)
        )
        self.assertTrue(success, "error in parsing valid iso8601_datetime")
        self.assertTrue(results[0][1][0] == datetime_datetime(
            1997, 7, 16, 19, 20, 30, 450000
        ))

        success = uuid.run_tests(
            """
            123e4567-e89b-12d3-a456-426655440000
            """
        )[0]
        self.assertTrue(success, "failed to parse valid uuid")

        success = fraction.run_tests(
            """
            1/2
            -15/16
            -3/-4
            """
        )[0]
        self.assertTrue(success, "failed to parse valid fraction")

        success = mixed_integer.run_tests(
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

        success, results = number.run_tests(
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
                result,
                expected,
                "numeric parse failed (wrong value) ({} should be {})".format(
                    result, expected
                ),
            )
            self.assertEqual(
                type(result[0]),
                type(expected),
                "numeric parse failed (wrong type) ({} should be {})".format(
                    type(result), type(expected)
                ),
            )

    def testNumericExpressions(self):

        # disable parse actions that do type conversion so we don't accidentally trigger
        # conversion exceptions when what we want to check is the parsing expression
        real = helpers.real.clear_parse_action()
        sci_real = helpers.sci_real.clear_parse_action()
        signed_integer = helpers.signed_integer.clear_parse_action()

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
            success = True
            for t in tests:
                if expr.matches(t, parse_all=True):
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

        parser = OneOrMore(Word(hexnums)).add_parse_action(token_map(int, 16))
        success, report = parser.run_tests(
            """
            00 11 22 aa FF 0a 0d 1a
            """
        )
        # WAS:
        # self.assertTrue(success, "failed to parse hex integers")
        # print(results)
        # self.assertEqual(results[0][-1], [0, 17, 34, 170, 255, 10, 13, 26], "token_map parse action failed")

        # USING JUST assertParseResultsEquals
        # results = [rpt[1] for rpt in report]
        # self.assertParseResultsEquals(results[0], [0, 17, 34, 170, 255, 10, 13, 26],
        #                               msg="token_map parse action failed")

        # if I hadn't unpacked the return from run_tests, I could have just passed it directly,
        # instead of reconstituting as a tuple
        self.assertRunTestResults(
            (success, report),
            [([0, 17, 34, 170, 255, 10, 13, 26], "token_map parse action failed"),],
            msg="failed to parse hex integers",
        )

    def testParseFile(self):

        s = """
        123 456 789
        """
        input_file = StringIO(s)

        results = OneOrMore(integer).parse_file(input_file)

        results = OneOrMore(integer).parse_file(
            "tests/resources/parsefiletest_input_file.txt"
        )

    def testHTMLStripper(self):
        sample = """
        <html>
        Here is some sample <i>HTML</i> text.
        </html>
        """
        read_everything = (
            originalTextFor(OneOrMore(Word(printables))).add_parse_action(stripHTMLTags)
        )

        result = read_everything.parse_string(sample)
        self.assertEqual(result[0].strip(), "Here is some sample HTML text.")

    def testExprSplitter(self):
        whitespaces.CURRENT.add_ignore(quoted_string)
        whitespaces.CURRENT.add_ignore(pythonStyleComment)
        expr = Literal(";") + Empty()

        self.assertEqual(
            list(expr.split(
                'a = "a;b"; return a # this is a comment; it has a semicolon!'
            )),
            ['a = "a;b"', "return a # this is a comment; it has a semicolon!"],
        )

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
                list(expr.split(line)), expect, "invalid split on expression"
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
                list(expr.split(line, include_separators=True)),
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
                    expr.search_string(line).length(),
                    0,
                    "invalid split with maxSplits=1 when expr not present",
                )
            else:

                self.assertTrue(
                    False, "invalid split on expression with maxSplits=1, corner case"
                )

    def testParseFatalException(self):

        with self.assertRaises(Exception):
            expr = "ZZZ" - Word(nums)
            expr.parse_string("ZZZ bad")

    def test_default_literal(self):

        wd = Word(alphas)

        whitespaces.CURRENT.set_literal(Suppress)
        result = (wd + "," + wd + one_of("! . ?")).parse_string("Hello, World!")
        self.assertEqual(result.length(), 3, "default_literal(Suppress) failed!")

        whitespaces.CURRENT.set_literal(Literal)
        result = (wd + "," + wd + one_of("! . ?")).parse_string("Hello, World!")
        self.assertEqual(result.length(), 4, "default_literal(Literal) failed!")

        whitespaces.CURRENT.set_literal(CaselessKeyword)
        # WAS:
        # result = ("SELECT" + wd + "FROM" + wd).parse_string("select color from colors")
        # self.assertEqual(result, "SELECT color FROM colors".split(),
        #                  "default_literal(CaselessKeyword) failed!")
        self.assertParseResultsEquals(
            ("SELECT" + wd + "FROM" + wd).parse_string("select color from colors"),
            expected_list=["SELECT", "color", "FROM", "colors"],
            msg="default_literal(CaselessKeyword) failed!",
        )

        whitespaces.CURRENT.set_literal(CaselessLiteral)
        # result = ("SELECT" + wd + "FROM" + wd).parse_string("select color from colors")
        # self.assertEqual(result, "SELECT color FROM colors".split(),
        #                  "default_literal(CaselessLiteral) failed!")
        self.assertParseResultsEquals(
            ("SELECT" + wd + "FROM" + wd).parse_string("select color from colors"),
            expected_list=["SELECT", "color", "FROM", "colors"],
            msg="default_literal(CaselessLiteral) failed!",
        )

        integer = Word(nums)
        whitespaces.CURRENT.set_literal(Literal)
        date_str = integer("year") + "/" + integer("month") + "/" + integer("day")
        # result = date_str.parse_string("1999/12/31")
        # self.assertEqual(result, ['1999', '/', '12', '/', '31'], "default_literal(example 1) failed!")
        self.assertParseResultsEquals(
            date_str.parse_string("1999/12/31"),
            expected_list=["1999", "/", "12", "/", "31"],
            msg="default_literal(example 1) failed!",
        )

        # change to Suppress
        whitespaces.CURRENT.set_literal(Suppress)
        date_str = integer("year") + "/" + integer("month") + "/" + integer("day")

        # result = date_str.parse_string("1999/12/31")  # -> ['1999', '12', '31']
        # self.assertEqual(result, ['1999', '12', '31'], "default_literal(example 2) failed!")
        self.assertParseResultsEquals(
            date_str.parse_string("1999/12/31"),
            expected_list=["1999", "12", "31"],
            msg="default_literal(example 2) failed!",
        )

    def testCloseMatch(self):
        searchseq = CloseMatch("ATCATCGAATGGA", 2)

        _, results = searchseq.run_tests(
            """
            ATCATCGAATGGA
            XTCATCGAATGGX
            ATCATCGAAXGGA
            ATCAXXGAATGGA
            ATCAXXGAATGXA
            ATCAXXGAATGG
            """,
            failureTests=[False, False, False, False, True, True],
        )
        expected = ([], [0, 12], 9, [4, 5], None, None)

        for (r_str, r_tok), exp in zip(results, expected):
            if exp is not None:
                self.assertEqual(
                    r_tok["mismatches"],
                    exp,
                    "fail CloseMatch between {!r} and {!r}".format(
                        searchseq.parser_config.match, r_str
                    ),
                )

    def testDefaultKeywordChars(self):

        with self.assertRaisesParseException(msg="failed to fail matching keyword using updated keyword chars"):
            Keyword("start").parse_string("start1000")

        try:
            Keyword("start", ident_chars=alphas).parse_string("start1000")
        except ParseException:
            self.assertTrue(
                False, "failed to match keyword using updated keyword chars"
            )

        whitespaces.CURRENT.set_keyword_chars(alphas)
        try:
            Keyword("start").parse_string("start1000")
        except ParseException:
            self.assertTrue(
                False, "failed to match keyword using updated keyword chars"
            )

        whitespaces.CURRENT.set_keyword_chars(alphanums)
        with self.assertRaisesParseException(msg="failed to fail matching keyword using updated keyword chars"):
            CaselessKeyword("START").parse_string("start1000")

        try:
            CaselessKeyword("START", ident_chars=alphas).parse_string("start1000")
        except ParseException:
            self.assertTrue(
                False, "failed to match keyword using updated keyword chars"
            )

        whitespaces.CURRENT.set_keyword_chars(alphas)
        try:
            CaselessKeyword("START").parse_string("start1000")
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
            expr = cls("xyz")  # .set_parser_name('{}_expr'.format(cls.__name__.lower()))

            try:
                expr.parse_string(" ")
            except Exception as e:

                self.assertTrue(
                    isinstance(e, ParseException),
                    "class {} raised wrong exception type {}".format(
                        cls.__name__, type(e).__name__
                    ),
                )

    def testParseActionException(self):

        number = Word(nums)

        def number_action():
            raise IndexError()  # this is the important line!

        number = number.add_parse_action(number_action)
        symbol = Word("abcd", max=1)
        expr = number | symbol

        with self.assertRaises("IndexError"):
            expr.parse_string("1 + 2")

    # tests Issue #22
    def testParseActionNesting(self):

        vals = OneOrMore(integer)("int_values")

        def add_total(tokens):
            tokens["total"] = sum(tokens)
            return tokens

        vals = vals.add_parse_action(add_total)
        results = vals.parse_string("244 23 13 2343")
        self.assertParseResultsEquals(
            results,
            expected_dict={"int_values": [244, 23, 13, 2343]},
            msg="noop parse action changed ParseResults structure",
        )
        # THE result IS NOT A dict(): THE LIST OF INTEGERS HAS A PROPERTY CALLED total
        self.assertParseResultsEquals(
            results["int_values"],
            expected_dict={"total": 2623},
            msg="noop parse action changed ParseResults structure",
        )

        name = Word(alphas)("name")
        score = Word(nums + ".")("score")
        nameScore = Group(name + score)
        line1 = nameScore("Rider")

        result1 = line1.parse_string("Mauney 46.5")

        before_pa_dict = result1

        line1.add_parse_action(lambda t: t)

        result1 = line1.parse_string("Mauney 46.5")
        after_pa_dict = result1

        self.assertEqual(
            before_pa_dict,
            after_pa_dict,
            "noop parse action changed ParseResults structure",
        )

    def testParseResultsNameBelowUngroupedName(self):
        rule_num = Regex("[0-9]+")("LIT_NUM")
        list_num = Group(
            Literal("[")("START_LIST")
            + Group(delimited_list(rule_num))("LIST_VALUES")
            + Literal("]")("END_LIST")
        )("LIST")

        test_string = "[ 1,2,3,4,5,6 ]"
        list_num.run_tests(test_string)

        U = list_num.parse_string(test_string)
        self.assertEqual(
            U["LIST"]["LIST_VALUES"]["LIT_NUM"], ["1", "2", "3", "4", "5", "6"]
        )

    def testParseResultsNamesInGroupWithDict(self):

        key = identifier
        value = integer
        lat = real
        long = real
        EQ = Suppress("=")

        data = lat("lat") + long("long") + OpenDict(OneOrMore(Group(key + EQ + value)))
        site = QuotedString('"')("name") + Group(data)("data")

        test_string = '"Golden Gate Bridge" 37.819722 -122.478611 height=746 span=4200'
        result = site.parse_string(test_string)
        self.assertEqual(
            result,
            {
                "name": "Golden Gate Bridge",
                "data": {
                    "lat": 37.819722,
                    "long": -122.478611,
                    "height": 746,
                    "span": 4200,
                },
            },
        )

        a, _ = makeHTMLTags("a")
        attrs = a.parse_string("<a href='blah'>")
        self.assertParseResultsEquals(
            attrs,
            expected_dict={
                "startA": {"href": "blah", "tag": "a", "empty": False},
                "href": None,
                "tag": None,
                "empty": None,
            },
        )

    def testFollowedBy(self):
        expr = Word(alphas)("item") + FollowedBy(integer("qty"))
        result = expr.parse_string("balloon 99")

        self.assertTrue("qty" in result, "failed to capture results name in FollowedBy")
        self.assertEqual(
            result,
            {"item": "balloon", "qty": 99},
            "invalid results name structure from FollowedBy",
        )

        data_word = Word(alphas)
        label = data_word + FollowedBy(":")
        attr_expr = Group(
            label
            + Suppress(":")
            + OneOrMore(data_word, stop_on=label).add_parse_action(" ".join)
        )

        result = OneOrMore(attr_expr).parse_string(
            "shape: SQUARE ball color: BLACK posn: upper left"
        )
        expected = [
            ["shape", "SQUARE ball"],
            ["color", "BLACK"],
            ["posn", "upper left"],
        ]
        self.assertEqual(result, expected)

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
        result = greet.parse_string(hello)

        self.assertParseResultsEquals(
            result,
            expected_list=["Καλημέρα", ",", "κόσμε", "!"],
            msg=(
                "Failed to parse Greek 'Hello, World!' using "
                "parsing_unicode.Greek.alphas"
            ),
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
        result = Dict(OneOrMore(Group(key_value))).parse_string(sample)

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
            + Group("(" + Optional(delimited_list(identifier)) + ")")
            + ":"
        )
        func_body = indented_block(stmt, indentStack)
        funcDef = Group(funcDecl + func_body)

        rvalue = Forward()
        funcCall = Group(identifier + "(" + Optional(delimited_list(rvalue)) + ")")
        rvalue << (funcCall | identifier | Word(nums))
        assignment = Group(identifier + "=" + rvalue)
        stmt << (funcDef | assignment | identifier)

        module_body = OneOrMore(stmt)

        parseTree = module_body.parse_string(data)

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
                        [[
                            "def",
                            "BBA",
                            ["(", ")"],
                            ":",
                            [["bba1"], ["bba2"], ["bba3"]],
                        ]],
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
        compound_value = Dict(ungroup(indented_block(key_value, stack)))
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

        result = parser.parse_string(text)

        self.assertEqual(result["a"], 100, "invalid indented block result")
        self.assertEqual(result["c"]["c1"], 200, "invalid indented block result")
        self.assertEqual(result["c"]["c2"]["c21"], 999, "invalid indented block result")

    def testIndentedBlockTest2(self):
        key = Word(alphas, alphanums) + Suppress(":")
        stmt = Forward()
        suite = indented_block(stmt)
        pattern = Word(alphas) + Suppress("(") + Word(alphas) + Suppress(")")
        stmt << pattern

        def key_parse_action(toks):
            print("Parsing '%s'..." % toks[0])

        body = key.add_parse_action(key_parse_action) + suite
        header = Suppress("[") + Literal("test") + Suppress("]")
        content = header - OneOrMore(indented_block(body, False))

        contents = Forward()
        suites = indented_block(OneOrMore(content))

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

        success, _ = parser.run_tests([sample])
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
            aone:
                atwo (athree)
            afour:
                afive (aseven)

            [test]
            bone:
                btwo (bthree)
            bfour:
                bfive (bseven)

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

        success, _ = parser.run_tests([sample2])
        self.assertTrue(success, "Failed indentedBlock multi-block test for issue #87")

    @unittest.skip("need a stack of parse state to do this correctly")
    def testIndentedBlockScan(self):
        def get_parser():
            """
            A valid statement is the word "block:", followed by an indent, followed by the letter A only, or another block
            """
            block = Forward()
            body = indented_block(Literal("A") ^ block)
            block <<= Literal("block:") + body
            return block

        # This input string is a perfect match for the parser, so a single match is found
        p1 = get_parser()
        r1 = list(p1.scan_string(dedent(
            """\
        block:
            A
        """
        )))
        self.assertEqual(len(r1), 1)

        # This input string is a perfect match for the parser, except for the letter B instead of A, so this will fail (and should)
        p2 = get_parser()
        r2 = list(p2.scan_string(dedent(
            """\
        block:
            B
        """
        )))
        self.assertEqual(len(r2), 0)

        # This input string contains both string A and string B, and it finds one match (as it should)
        p3 = get_parser()
        r3 = list(p3.scan_string(dedent(
            """\
        block:
            A
        block:
            B
        """
        )))
        self.assertEqual(len(r3), 1)

        # This input string contains both string A and string B, but in a different order.
        p4 = get_parser()
        r4 = list(p4.scan_string(dedent(
            """\
        block:
            B
        block:
            A
        """
        )))
        self.assertEqual(len(r4), 1)

        # This is the same as case 3, but with nesting
        p5 = get_parser()
        r5 = list(p5.scan_string(dedent(
            """\
        block:
            block:
                A
        block:
            block:
                B
        """
        )))
        self.assertEqual(len(r5), 1)

        # This is the same as case 4, but with nesting
        p6 = get_parser()
        r6 = list(p6.scan_string(dedent(
            """\
        block:
            block:
                B
        block:
            block:
                A
        """
        )))
        self.assertEqual(len(r6), 1)

    def testParseResultsWithNameMatchFirst(self):

        expr_a = Literal("not") + Literal("the") + Literal("bird")
        expr_b = Literal("the") + Literal("bird")
        expr = (expr_a | expr_b)("rexp")

        success, report = expr.run_tests(
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
        expr.run_tests(
            """\
            not the bird
            the bird
        """
        )
        result = expr.parse_string("not the bird")
        self.assertParseResultsEquals(
            result, ["not", "the", "bird"], {"rexp": ["not", "the", "bird"]}
        )
        result = expr.parse_string("the bird")
        self.assertParseResultsEquals(
            result, ["the", "bird"], {"rexp": ["the", "bird"]}
        )

        expr = (expr_a | expr_b)("rexp")
        expr.run_tests(
            """\
            not the bird
            the bird
        """
        )
        result = expr.parse_string("not the bird")
        self.assertParseResultsEquals(
            result, ["not", "the", "bird"], {"rexp": ["not", "the", "bird"]}
        )
        result = expr.parse_string("the bird")
        self.assertParseResultsEquals(
            result, ["the", "bird"], {"rexp": ["the", "bird"]}
        )

    def testEmptyDictDoesNotRaiseException(self):

        key = Word(alphas)
        value = Word(nums)
        EQ = Suppress("=")
        key_value_dict = dict_of(key, EQ + value)

        print(key_value_dict.parse_string(
            """\
            a = 10
            b = 20
            """
        ))

        try:
            key_value_dict.parse_string("")
        except ParseException as pe:
            pass  # expected
        else:
            self.assertTrue(
                False, "failed to raise exception when matching empty string"
            )

    def testExplainException(self):

        expr = Word(nums).set_parser_name("int") + Word(alphas).set_parser_name("word")
        with self.assertRaises(
            'Expecting word, found "355" (at char 4), (line:1, col:5)'
        ):
            expr.parse_string("123 355")

        expr = Word(nums).set_parser_name("int") - Word(alphas).set_parser_name("word")
        with self.assertRaises(
            'Expecting word, found "355 (test " (at char 4), (line:1, col:5)'
        ):
            expr.parse_string("123 355 (test using ErrorStop)")

        integer = (
            Word(nums).set_parser_name("int").add_parse_action(lambda t: int(t[0]))
        )
        expr = integer + integer

        def divide_args(t):
            return t[0] / t[1]

        expr = expr.add_parse_action(divide_args)

        with self.assertRaises("""division by zero"""):
            expr.parse_string("123 0")

    def testCaselessKeywordVsKeywordCaseless(self):

        frule = Keyword("t", caseless=True) + Keyword("yes", caseless=True)
        crule = CaselessKeyword("t") + CaselessKeyword("yes")

        flist = frule.search_string("not yes").as_list()

        clist = crule.search_string("not yes").as_list()

        self.assertEqual(
            flist,
            clist,
            "CaselessKeyword not working the same as Keyword(caseless=True)",
        )

    def testOneOfKeywords(self):

        literal_expr = one_of("a b c")
        success, _ = literal_expr[...].run_tests(
            """
            # literal one_of tests
            a b c
            a a a
            abc
        """
        )
        self.assertTrue(success, "failed literal one_of matching")

        keyword_expr = one_of("a b c", as_keyword=True)
        success, _ = keyword_expr[...].run_tests(
            """
            # keyword one_of tests
            a b c
            a a a
        """
        )
        self.assertTrue(success, "failed keyword one_of matching")

        success, _ = keyword_expr[...].run_tests(
            """
            # keyword one_of failure tests
            abc
        """,
            failureTests=True,
        )
        self.assertTrue(success, "failed keyword one_of failure tests")

    def testOneOfWithDuplicateSymbols(self):
        # test making one_of with duplicate symbols

        try:
            test1 = one_of("a b c d a")
        except RuntimeError:
            self.assertTrue(
                False,
                "still have infinite loop in one_of with duplicate symbols (string"
                " input)",
            )

        try:
            test1 = one_of(c for c in "a b c d a" if not c.isspace())
        except RuntimeError:
            self.assertTrue(
                False,
                "still have infinite loop in one_of with duplicate symbols (generator"
                " input)",
            )

        try:
            test1 = one_of("a b c d a".split())
        except RuntimeError:
            self.assertTrue(
                False,
                "still have infinite loop in one_of with duplicate symbols (list"
                " input)",
            )

        try:
            test1 = one_of(set("a b c d a"))
        except RuntimeError:
            self.assertTrue(
                False,
                "still have infinite loop in one_of with duplicate symbols (set input)",
            )

    def testMatchFirstIteratesOverAllChoices(self):
        # test MatchFirst bugfix

        results = quoted_string.parse_string("'this is a single quoted string'")
        self.assertTrue(
            results.length() > 0, "MatchFirst error - not iterating over all choices"
        )

    def testStreamlineOfSubexpressions(self):
        # verify streamline of subexpressions

        compound = Literal("A") + "B" + "C" + "D"
        compound.streamline()
        self.assertEqual(len(compound.exprs), 4, "streamline not working")

    def testOptionalWithResultsNameAndNoMatch(self):
        # test for Optional with results name and no match

        testGrammar = Literal("A") + Optional("B")("gotB") + Literal("C")
        try:
            testGrammar.parse_string("ABC")
            testGrammar.parse_string("AC")
        except ParseException as pe:

            self.assertTrue(
                False, "error in Optional matching of string %s" % pe.string
            )

    def testReturnOfFurthestException(self):
        # test return of furthest exception
        testGrammar = Literal("A") | (Optional("B") + Literal("C")) | Literal("D")
        try:
            testGrammar.parse_string("BC")
            testGrammar.parse_string("BD")
        except ParseException as pe:
            self.assertEqual(pe.string, "BD", "wrong test string failed to parse")
            self.assertEqual(
                pe.loc, 1, "error in Optional matching, pe.loc=" + str(pe.loc)
            )

    def testValidateCorrectlyDetectsInvalidLeftRecursion(self):
        # OK
        fwd = Forward()
        g1 = OneOrMore((Literal("A") + "B" + "C") | fwd)
        g2 = ("C" + g1)[...]
        fwd << Group(g2)

        with self.assertRaises(RecursiveGrammarException):
            fwd2 = Forward()
            fwd2 << Group("A" | fwd2)

        with self.assertRaises(RecursiveGrammarException):
            fwd3 = Forward()
            fwd3 << Optional("A") + fwd3

    def testGetNameBehavior(self):
        # test get_name

        aaa = Group(Word("a")("A"))
        bbb = Group(Word("b")("B"))
        ccc = Group(":" + Word("c")("C"))
        g1 = "XXX" + (aaa | bbb | ccc)[...]
        teststring = "XXX b bb a bbb bbbb aa bbbbb :c bbbbbb aaa"
        names = []

        for t in g1.parse_string(teststring):

            try:
                names.append(t[0].get_name())
            except Exception:
                try:
                    names.append(t.get_name())
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

        def getNameTester(t, l, s):

            return t

        ident.add_parse_action(getNameTester)
        scanner.parse_string("lsjd sldkjf IF Saslkj AND lsdjf")

        # test ParseResults.get() method

        # use sum() to merge separate groups into single ParseResults
        res = sum(g1.parse_string(teststring)[1:])

        self.assertEqual(
            res.get("A", "A not found"),
            ["a", "aa", "aaa"],
            "get on existing key failed",
        )
        self.assertEqual(res.get("D", "!D"), "!D", "get on missing key failed")

    def testOptionalBeyondEndOfString(self):

        testGrammar = "A" + Optional("B") + Optional("C") + Optional("D")
        testGrammar.parse_string("A")
        testGrammar.parse_string("AB")

    def testCreateLiteralWithEmptyString(self):
        # test creating Literal with empty string

        with self.assertRaises(Exception):
            e = Literal("")

        try:
            e = Empty()
            e.parse_string("SLJFD")
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
            "".join(grammar.parse_string("aba")), "aba", "Packrat ABA failure!"
        )

    def testSetResultsNameWithOneOrMoreAndZeroOrMore(self):

        stmt = Keyword("test")

        self.assertEqual(
            stmt[...]("tests").parse_string("test test")["tests"].length(),
            2,
            "ZeroOrMore failure with .set_token_name",
        )
        self.assertEqual(
            stmt[1, ...]("tests").parse_string("test test")["tests"].length(),
            2,
            "OneOrMore failure with .set_token_name",
        )
        self.assertEqual(
            Optional(stmt[1, ...]("tests")).parse_string("test test")["tests"].length(),
            2,
            "OneOrMore failure with .set_token_name",
        )
        self.assertEqual(
            Optional(delimited_list(stmt))("tests")
            .parse_string("test,test")["tests"]
            .length(),
            2,
            "delimited_list failure with .set_token_name",
        )
        self.assertEqual(
            (stmt * 2)("tests").parse_string("test test")["tests"].length(),
            2,
            "multiplied(1) failure with .set_token_name",
        )
        self.assertEqual(
            stmt[..., 2]("tests").parse_string("test test")["tests"].length(),
            2,
            "multiplied(2) failure with .set_token_name",
        )
        self.assertEqual(
            stmt[1, ...]("tests").parse_string("test test")["tests"].length(),
            2,
            "multipled(3) failure with .set_token_name",
        )
        self.assertEqual(
            stmt[2, ...]("tests").parse_string("test test")["tests"].length(),
            2,
            "multipled(3) failure with .set_token_name",
        )
