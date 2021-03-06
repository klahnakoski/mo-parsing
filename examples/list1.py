#
# list1.py
#
# an example of using parse actions to convert type of parsed data.
#
# Copyright (c) 2006-2016, Paul McGuire
#
from mo_parsing import *

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
cvtReal = lambda toks, l, s: float(toks[0])
integer = Word(nums).set_parser_name("integer").addParseAction(cvtInt)
real = (
    Combine(Optional(oneOf("+ -")) + Word(nums) + "." + Optional(Word(nums)))
    .set_parser_name("real")
    .addParseAction(cvtReal)
)
listItem = real | integer | quotedString.addParseAction(removeQuotes)

listStr = lbrack + delimitedList(listItem) + rbrack

test = "['a', 100, 3.14]"


# third pass, add nested list support
lbrack, rbrack = map(Suppress, "[]")

cvtInt = tokenMap(int)
cvtReal = tokenMap(float)

integer = Word(nums).set_parser_name("integer").addParseAction(cvtInt)
real = Regex(r"[+-]?\d+\.\d*").set_parser_name("real").addParseAction(cvtReal)

listStr = Forward()
listItem = real | integer | quotedString.addParseAction(removeQuotes) | Group(listStr)
listStr << lbrack + delimitedList(listItem) + rbrack

test = "['a', 100, 3.14, [ +2.718, 'xyzzy', -1.414] ]"

