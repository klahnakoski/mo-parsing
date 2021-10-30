#
# A simple example showing the use of the implied listAllMatches=True for
# results names with a trailing '*' character.
#
# This example performs work similar to itertools.groupby, but without
# having to sort the input first.
#
# Copyright 2004-2016, by Paul McGuire
#
from mo_parsing import Word, ZeroOrMore
from mo_parsing.utils import nums

a_expr = Word("A", nums)
b_expr = Word("B", nums)
c_expr = Word("C", nums)
grammar = ZeroOrMore(a_expr("A*") | b_expr("B*") | c_expr("C*"))

grammar.run_tests("A1 B1 A2 C1 B2 A3")
