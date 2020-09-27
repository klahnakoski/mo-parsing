#
# parseTabularData.py
#
# Example of parsing data that is formatted in a tabular listing, with
# potential for missing values. Uses new addCondition method on
# ParserElements.
#
# Copyright 2015, Paul McGuire
#
from mo_parsing import col, Word, Optional, alphas, nums

table = """\
         1         2
12345678901234567890
COLOR      S   M   L
RED       10   2   2
BLUE           5  10
GREEN      3       5
PURPLE     8"""

# function to create column-specific parse conditions
def mustMatchCols(startloc, endloc):
    return lambda t, l, s: startloc <= col(l, s) <= endloc


# helper to define values in a space-delimited table
# (change empty_cell_is_zero to True if a value of 0 is desired for empty cells)
def tableValue(expr, colstart, colend):
    empty_cell_is_zero = False
    if empty_cell_is_zero:
        return Optional(
            expr
            .copy()
            .addCondition(
                mustMatchCols(colstart, colend), message="text not in expected columns"
            ),
            default=0,
        )
    else:
        return Optional(
            expr
            .copy()
            .addCondition(
                mustMatchCols(colstart, colend), message="text not in expected columns"
            )
        )


# define the grammar for this simple table
colorname = Word(alphas)
integer = Word(nums).addParseAction(lambda t: int(t[0])).set_parser_name("integer")
row = (
    colorname("name")
    + tableValue(integer, 11, 12)("S")
    + tableValue(integer, 15, 16)("M")
    + tableValue(integer, 19, 20)("L")
)
