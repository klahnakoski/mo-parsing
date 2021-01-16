# parseListString.py
#
# Copyright, 2006, by Paul McGuire
#

from mo_parsing.helpers import *

# first pass

lbrack = Literal("[")
rbrack = Literal("]")
integer = Word(nums).set_parser_name("integer")
real = Combine(
    Optional(oneOf("+ -")) + Word(nums) + "." + Optional(Word(nums))
).set_parser_name("real")

listItem = real | integer | quotedString

listStr = lbrack + delimitedList(listItem) + rbrack

test = "['a', 100, 3.14]"



# second pass, cleanup and add converters
lbrack = Literal("[").suppress()
rbrack = Literal("]").suppress()
cvtInt = lambda toks, l, s: int(toks[0])
integer = Word(nums).set_parser_name("integer").addParseAction(cvtInt)
cvtReal = lambda toks, l, s: float(toks[0])
real = Regex(r"[+-]?\d+\.\d*").set_parser_name("floating-point number").addParseAction(cvtReal)
listItem = real | integer | quotedString.addParseAction(removeQuotes)

listStr = lbrack + delimitedList(listItem) + rbrack

test = "['a', 100, 3.14]"


# third pass, add nested list support, and tuples, too!
cvtInt = lambda toks, l, s: int(toks[0])
cvtReal = lambda toks, l, s: float(toks[0])

lbrack = Literal("[").suppress()
rbrack = Literal("]").suppress()
integer = Word(nums).set_parser_name("integer").addParseAction(cvtInt)
real = Regex(r"[+-]?\d+\.\d*").set_parser_name("floating-point number").addParseAction(cvtReal)
tupleStr = Forward()
listStr = Forward()
listItem = (
    real
    | integer
    | quotedString.addParseAction(removeQuotes)
    | Group(listStr)
    | tupleStr
)
tupleStr << (
    Suppress("(") + delimitedList(listItem) + Optional(Suppress(",")) + Suppress(")")
)
tupleStr.addParseAction(lambda t: tuple(t))
listStr << lbrack + delimitedList(listItem) + Optional(Suppress(",")) + rbrack

test = "['a', 100, ('A', [101,102]), 3.14, [ +2.718, 'xyzzy', -1.414] ]"


# fourth pass, add parsing of dicts
cvtInt = lambda toks, l, s: int(toks[0])
cvtReal = lambda toks, l, s: float(toks[0])
cvtDict = lambda toks, l, s: dict(toks[0])

lbrack = Literal("[").suppress()
rbrack = Literal("]").suppress()
lbrace = Literal("{").suppress()
rbrace = Literal("}").suppress()
colon = Literal(":").suppress()
integer = Word(nums).set_parser_name("integer").addParseAction(cvtInt)
real = Regex(r"[+-]?\d+\.\d*").set_parser_name("real").addParseAction(cvtReal)

tupleStr = Forward()
listStr = Forward()
dictStr = Forward()
listItem = (
    real
    | integer
    | quotedString.addParseAction(removeQuotes)
    | Group(listStr)
    | tupleStr
    | dictStr
)
tupleStr <<= (
    Suppress("(") + delimitedList(listItem) + Optional(Suppress(",")) + Suppress(")")
)
tupleStr.addParseAction(lambda t: tuple(t))
listStr <<= (
    lbrack + Optional(delimitedList(listItem)) + Optional(Suppress(",")) + rbrack
)
dictKeyStr = real | integer | quotedString.addParseAction(removeQuotes)
dictStr <<= (
    lbrace
    + Optional(delimitedList(Group(dictKeyStr + colon + listItem)))
    + Optional(Suppress(","))
    + rbrace
)
dictStr.addParseAction(
    lambda t: {
        k_v[0]: (k_v[1] if isinstance(k_v[1], ParseResults) else k_v[1])
        for k_v in t
    }
)

test = "[{0: [2], 1: []}, {0: [], 1: [], 2: [,]}, {0: [1, 2,],}]"

