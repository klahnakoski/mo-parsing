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
    Optional(one_of("+ -")) + Word(nums) + "." + Optional(Word(nums))
).set_parser_name("real")

listItem = real | integer | quoted_string

listStr = lbrack + delimited_list(listItem) + rbrack

test = "['a', 100, 3.14]"



# second pass, cleanup and add converters
lbrack = Literal("[").suppress()
rbrack = Literal("]").suppress()
cvtInt = lambda toks, l, s: int(toks[0])
cvtReal = lambda toks, l, s: float(toks[0])
integer = Word(nums).set_parser_name("integer").add_parse_action(cvtInt)
real = (
    Combine(Optional(one_of("+ -")) + Word(nums) + "." + Optional(Word(nums)))
    .set_parser_name("real")
    .add_parse_action(cvtReal)
)
listItem = real | integer | quoted_string.add_parse_action(removeQuotes)

listStr = lbrack + delimited_list(listItem) + rbrack

test = "['a', 100, 3.14]"


# third pass, add nested list support
lbrack, rbrack = map(Suppress, "[]")

cvtInt = token_map(int)
cvtReal = token_map(float)

integer = Word(nums).set_parser_name("integer").add_parse_action(cvtInt)
real = Regex(r"[+-]?\d+\.\d*").set_parser_name("real").add_parse_action(cvtReal)

listStr = Forward()
listItem = real | integer | quoted_string.add_parse_action(removeQuotes) | Group(listStr)
listStr << lbrack + delimited_list(listItem) + rbrack

test = "['a', 100, 3.14, [ +2.718, 'xyzzy', -1.414] ]"

