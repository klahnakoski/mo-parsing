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
    infixNotation,
    CaselessKeyword,
)
from mo_parsing.engine import Engine
from mo_parsing.helpers import restOfLine, upcaseTokens, real, signed_integer, quotedString
from mo_parsing.infix import delimitedList, oneOf, RIGHT_ASSOC, LEFT_ASSOC
from mo_parsing.utils import alphas, alphanums

engine = Engine().use()

selectStmt = Forward()
SELECT, FROM, WHERE, AND, OR, IN, IS, NOT, NULL = map(
    CaselessKeyword, "select from where and or in is not null".split()
)
NOT_NULL = NOT + NULL

ident = Word(alphas, alphanums + "_$").set_parser_name("identifier")
columnName = delimitedList(ident, ".", combine=True).set_parser_name("column name")
columnName.addParseAction(upcaseTokens)
columnNameList = Group(delimitedList(columnName))
tableName = delimitedList(ident, ".", combine=True).set_parser_name("table name")
tableName.addParseAction(upcaseTokens)
tableNameList = Group(delimitedList(tableName))

binop = oneOf("= != < > >= <= eq ne lt le gt ge", caseless=True)
realNum = real
intNum = signed_integer

columnRval = (
    realNum | intNum | quotedString | columnName
)  # need to add support for alg expressions
whereCondition = Group(
    (columnName + binop + columnRval)
    | (columnName + IN + Group("(" + delimitedList(columnRval) + ")"))
    | (columnName + IN + Group("(" + selectStmt + ")"))
    | (columnName + IS + (NULL | NOT_NULL))
)

whereExpression = infixNotation(
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
engine.add_ignore(oracleSqlComment)
engine.release()
