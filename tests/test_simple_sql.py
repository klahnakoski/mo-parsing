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
    token_map,
    delimited_list,
    upcase_tokens,
)
from mo_parsing.utils import alphas, alphanums
from tests import run_tests


class TestSimpleSQL(TestCase):
    def test_simple_sql(self):
        selectToken = CaselessLiteral("select")
        fromToken = CaselessLiteral("from")

        ident = Word(alphas, alphanums + "_$")

        columnName = delimited_list(
            ident, ".", combine=True
        ).add_parse_action(upcase_tokens)
        columnNameList = Group(delimited_list(columnName)).set_parser_name("columns")
        columnSpec = "*" | columnNameList

        tableName = delimited_list(
            ident, ".", combine=True
        ).add_parse_action(upcase_tokens)
        tableNameList = Group(delimited_list(tableName)).set_parser_name("tables")

        simpleSQL = (
            selectToken("command")
            + columnSpec("columns")
            + fromToken
            + tableNameList("tables")
        )

        # demo run_tests method, including embedded comments in test string
        run_tests(
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

        run_tests(
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

        run_tests(
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
        run_tests(
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

        run_tests(
            hex_integer,
            """
            100
            FF
            """,
        )

        helper_uuid.add_parse_action(token_map(uuid.UUID))
        run_tests(
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
            combined_ident.parse_string("testing")
            self.assertLess(d.parse_count, 7)

    def test_word_has_expecting(self):
        expect = Word(alphanums).expecting()
        self.assertEqual(expect, {})
