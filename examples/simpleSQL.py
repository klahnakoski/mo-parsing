# simpleSQL.py
#
# simple demo of using the parsing library to do simple-minded SQL parsing
# could be extended to include where clauses etc.
#
# Copyright (c) 2003,2016, Paul McGuire
#
from mo_parsing import (
    Word,
    Optional,
    Group,
    Forward,
    infix_notation,
    CaselessKeyword, Combine,
)
from mo_parsing.helpers import restOfLine, upcase_tokens, real, signed_integer, quoted_string
from mo_parsing.infix import delimited_list, one_of, RIGHT_ASSOC, LEFT_ASSOC
from mo_parsing.utils import alphas, alphanums
from mo_parsing.whitespaces import Whitespace

whitespace = Whitespace().use()

selectStmt = Forward()
SELECT, FROM, WHERE, AND, OR, IN, IS, NOT, NULL = map(
    CaselessKeyword, "select from where and or in is not null".split()
)
NOT_NULL = NOT + NULL

ident = Word(alphas, alphanums + "_$").set_parser_name("identifier")
columnName = delimited_list(ident, ".", combine=True).set_parser_name("column name")
columnName.add_parse_action(upcase_tokens)
columnNameList = Group(delimited_list(columnName))
tableName = delimited_list(ident, ".", combine=True).set_parser_name("table name")
tableName.add_parse_action(upcase_tokens)
tableNameList = Group(delimited_list(tableName))

binop = one_of("= != < > >= <= eq ne lt le gt ge", caseless=True)
realNum = real
intNum = signed_integer

columnRval = (
    realNum | intNum | quoted_string | columnName
)  # need to add support for alg expressions
whereCondition = Group(
    (columnName + binop + columnRval)
    | (columnName + IN + Group("(" + delimited_list(columnRval) + ")"))
    | (columnName + IN + Group("(" + selectStmt + ")"))
    | (columnName + IS + (NULL | NOT_NULL))
)

whereExpression = infix_notation(
    whereCondition,
    [(NOT, 1, RIGHT_ASSOC), (AND, 2, LEFT_ASSOC), (OR, 2, LEFT_ASSOC)],
)

# define the grammar
selectStmt <<= (
    SELECT
    + ("*" | columnNameList)("columns")
    + FROM
    + tableNameList("tables")
    + Optional(Group(WHERE + whereExpression), "")("where")
)

simpleSQL = selectStmt

# define Oracle comment format, and ignore them
oracleSqlComment = "--" + restOfLine
whitespace.add_ignore(oracleSqlComment)
whitespace.release()
