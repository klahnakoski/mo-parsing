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

integer = Regex(r"[+-]?\d+").set_parser_name("integer").add_parse_action(cvtInt)
real = Regex(r"[+-]?\d+\.\d*([Ee][+-]?\d+)?").set_parser_name("real").add_parse_action(cvtReal)
tupleStr = Forward()
listStr = Forward()
dictStr = Forward()

unicode_string.add_parse_action(lambda t: t[0][2:-1])
quoted_string.add_parse_action(lambda t: t[0][1:-1])
boolLiteral = one_of("True False").add_parse_action(cvtBool)
noneLiteral = Literal("None").add_parse_action(lambda: [None])

listItem = (
    real
    | integer
    | quoted_string
    | unicode_string
    | boolLiteral
    | noneLiteral
    | Group(listStr)
    | tupleStr
    | dictStr
)

tupleStr << (lparen + Optional(delimited_list(listItem)) + Optional(comma) + rparen)
tupleStr.add_parse_action(cvtTuple)

listStr << (lbrack + Optional(delimited_list(listItem) + Optional(comma)) + rbrack)
listStr.add_parse_action(cvtList, lambda t: t[0])

dictEntry = Group(listItem + colon + listItem)
dictStr << (lbrace + Optional(delimited_list(dictEntry) + Optional(comma)) + rbrace)
dictStr.add_parse_action(cvtDict)

tests = """['a', 100, ('A', [101,102]), 3.14, [ +2.718, 'xyzzy', -1.414] ]
           [{0: [2], 1: []}, {0: [], 1: [], 2: []}, {0: [1, 2]}]
           { 'A':1, 'B':2, 'C': {'a': 1.2, 'b': 3.4} }
           3.14159
           42
           6.02E23
           6.02e+023
           1.0e-7
           'a quoted string'"""

listItem.run_tests(tests)
