# excel_expr.py
#
# Copyright 2010, Paul McGuire
#
# A partial implementation of a parser of Excel formula expressions.
#
from mo_parsing import CaselessKeyword
from mo_parsing.helpers import *
from mo_parsing.infix import one_of, infix_notation, LEFT_ASSOC

EQ, LPAR, RPAR, COLON, COMMA = map(Suppress, "=():,")
EXCL, DOLLAR = map(Literal, "!$")
sheetRef = Word(alphas, alphanums) | QuotedString("'", esc_quote="''")
colRef = Optional(DOLLAR) + Word(alphas, max=2)
rowRef = Optional(DOLLAR) + Word(nums)
cellRef = Combine(
    Group(Optional(sheetRef + EXCL)("sheet") + colRef("col") + rowRef("row"))
)

cellRange = (
    Group(cellRef("start") + COLON + cellRef("end"))("range")
    | cellRef
    | Word(alphas, alphanums)
)

expr = Forward()

COMPARISON_OP = one_of("< = > >= <= != <>")
cond_expr = expr + COMPARISON_OP + expr

ifFunc = (
    CaselessKeyword("if")
    - LPAR
    + Group(cond_expr)("condition")
    + COMMA
    + Group(expr)("if_true")
    + COMMA
    + Group(expr)("if_false")
    + RPAR
)

statFunc = lambda name: Group(
    CaselessKeyword(name) + Group(LPAR + delimited_list(expr) + RPAR)
)
sumFunc = statFunc("sum")
minFunc = statFunc("min")
maxFunc = statFunc("max")
aveFunc = statFunc("ave")
funcCall = ifFunc | sumFunc | minFunc | maxFunc | aveFunc

multOp = one_of("* /")
addOp = one_of("+ -")
numericLiteral = number
operand = numericLiteral | funcCall | cellRange | cellRef
arith_expr = infix_notation(
    operand, [(multOp, 2, LEFT_ASSOC), (addOp, 2, LEFT_ASSOC),]
)

textOperand = dblQuotedString | cellRef
text_expr = infix_notation(textOperand, [("&", 2, LEFT_ASSOC), ])

expr << (arith_expr | text_expr)


(EQ + expr).run_tests(
    """\
    =3*A7+5
    =3*Sheet1!$A$7+5
    =3*'Sheet 1'!$A$7+5
    =3*'O''Reilly''s sheet'!$A$7+5
    =if(Sum(A1:A25)>42,Min(B1:B25),if(Sum(C1:C25)>3.14, (Min(C1:C25)+3)*18,Max(B1:B25)))
    =sum(a1:a25,10,min(b1,c2,d3))
    =if("T"&a2="TTime", "Ready", "Not ready")
"""
)
