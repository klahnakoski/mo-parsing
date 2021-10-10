# encoding: utf-8
import uuid
from unittest import TestCase

from mo_parsing import (
    CaselessLiteral,
    Group,
    Word,
    Regex,
)
from mo_parsing.debug import Debugger
from mo_parsing.helpers import (
    number,
    hex_integer,
    fnumber,
    uuid as helper_uuid,
    tokenMap,
    delimitedList,
    upcaseTokens,
)
from mo_parsing.utils import alphas, alphanums
from tests import runTests


class TestSimpleSQL(TestCase):
    def test_simple_sql(self):
        selectToken = CaselessLiteral("select")
        fromToken = CaselessLiteral("from")

        ident = Word(alphas, alphanums + "_$")

        columnName = delimitedList(
            ident, ".", combine=True
        ).addParseAction(upcaseTokens)
        columnNameList = Group(delimitedList(columnName)).set_parser_name("columns")
        columnSpec = "*" | columnNameList

        tableName = delimitedList(ident, ".", combine=True).addParseAction(upcaseTokens)
        tableNameList = Group(delimitedList(tableName)).set_parser_name("tables")

        simpleSQL = (
            selectToken("command")
            + columnSpec("columns")
            + fromToken
            + tableNameList("tables")
        )

        # demo runTests method, including embedded comments in test string
        runTests(
            simpleSQL,
            """
            # '*' as column list and dotted table name
            select * from SYS.XYZZY
    
            # caseless match on "SELECT", and casts back to "select"
            SELECT * from XYZZY, ABC
    
            # list of column names, and mixed case SELECT keyword
            Select AA,BB,CC from Sys.dual
    
            # multiple tables
            Select A, B, C from Sys.dual, Table2
        """,
        )

        runTests(
            simpleSQL,
            """            
            # invalid SELECT keyword - should fail
            Xelect A, B, C from Sys.dual
    
            # incomplete command - should fail
            Select
    
            # invalid column name - should fail
            Select ^^^ frox Sys.dual
    
            """,
            failureTests=True,
        )

        runTests(
            number,
            """
            100
            -100
            +100
            3.14159
            6.02e23
            1e-12
            """,
        )

        # any int or real number, returned as float
        runTests(
            fnumber,
            """
            100
            -100
            +100
            3.14159
            6.02e23
            1e-12
            """,
        )

        runTests(
            hex_integer,
            """
            100
            FF
            """,
        )

        helper_uuid.addParseAction(tokenMap(uuid.UUID))
        runTests(
            helper_uuid,
            """
            12345678-1234-5678-1234-567812345678
            """,
        )

    def test_faster(self):
        ansi_ident = Regex(r'\"(\"\"|[^"])*\"')
        mysql_backtick_ident = Regex(r"\`(\`\`|[^`])*\`")
        sqlserver_ident = Regex(r"\[(\]\]|[^\]])*\]")

        combined_ident = (
            ansi_ident | mysql_backtick_ident | sqlserver_ident | Word(alphanums)
        )

        with Debugger() as d:
            combined_ident.parseString("testing")
            self.assertLess(d.parse_count, 7)

    def test_word_has_expecting(self):
        expect = Word(alphanums).expecting()
        self.assertEqual(expect, {})
