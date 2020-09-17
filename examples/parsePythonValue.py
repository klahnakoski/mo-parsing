# parsePythonValue.py
#
# Copyright, 2006, by Paul McGuire
#
from mo_parsing import *


cvtBool = lambda t: t[0] == "True"
cvtInt = lambda toks: int(toks[0])
cvtReal = lambda toks: float(toks[0])
cvtTuple = lambda toks: tuple(toks)
cvtDict = lambda toks: dict(toks)
cvtList = lambda toks: [toks]

# define punctuation as suppressed literals
lparen, rparen, lbrack, rbrack, lbrace, rbrace, colon, comma = map(Suppress, "()[]{}:,")

integer = Regex(r"[+-]?\d+").set_parser_name("integer").addParseAction(cvtInt)
real = Regex(r"[+-]?\d+\.\d*([Ee][+-]?\d+)?").set_parser_name("real").addParseAction(cvtReal)
tupleStr = Forward()
listStr = Forward()
dictStr = Forward()

unicodeString.addParseAction(lambda t: t[0][2:-1])
quotedString.addParseAction(lambda t: t[0][1:-1])
boolLiteral = oneOf("True False").addParseAction(cvtBool)
noneLiteral = Literal("None").addParseAction(replaceWith(None))

listItem = (
    real
    | integer
    | quotedString
    | unicodeString
    | boolLiteral
    | noneLiteral
    | Group(listStr)
    | tupleStr
    | dictStr
)

tupleStr << (lparen + Optional(delimitedList(listItem)) + Optional(comma) + rparen)
tupleStr.addParseAction(cvtTuple)

listStr << (lbrack + Optional(delimitedList(listItem) + Optional(comma)) + rbrack)
listStr.addParseAction(cvtList, lambda t: t[0])

dictEntry = Group(listItem + colon + listItem)
dictStr << (lbrace + Optional(delimitedList(dictEntry) + Optional(comma)) + rbrace)
dictStr.addParseAction(cvtDict)

tests = """['a', 100, ('A', [101,102]), 3.14, [ +2.718, 'xyzzy', -1.414] ]
           [{0: [2], 1: []}, {0: [], 1: [], 2: []}, {0: [1, 2]}]
           { 'A':1, 'B':2, 'C': {'a': 1.2, 'b': 3.4} }
           3.14159
           42
           6.02E23
           6.02e+023
           1.0e-7
           'a quoted string'"""

listItem.runTests(tests)
