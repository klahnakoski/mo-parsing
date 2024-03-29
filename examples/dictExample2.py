#
# dictExample2.py
#
#  Illustration of using mo_parsing's Dict class to process tabular data
#  Enhanced Dict example, courtesy of Mike Kelly
#
# Copyright (c) 2004, Paul McGuire
#
from mo_parsing import *
from mo_parsing.helpers import integer

testData = """
+-------+------+------+------+------+------+------+------+------+
|       |  A1  |  B1  |  C1  |  D1  |  A2  |  B2  |  C2  |  D2  |
+=======+======+======+======+======+======+======+======+======+
| min   |   7  |  43  |   7  |  15  |  82  |  98  |   1  |  37  |
| max   |  11  |  52  |  10  |  17  |  85  | 112  |   4  |  39  |
| ave   |   9  |  47  |   8  |  16  |  84  | 106  |   3  |  38  |
| sdev  |   1  |   3  |   1  |   1  |   1  |   3  |   1  |   1  |
+-------+------+------+------+------+------+------+------+------+
"""

# define grammar for datatable
underline = Word("-=")
number = integer

vert = Literal("|").suppress()

rowDelim = ("+" + ZeroOrMore(underline + "+")).suppress()
columnHeader = Group(vert + vert + delimited_list(Word(alphas + nums), "|") + vert)

heading = rowDelim + columnHeader("columns") + rowDelim
rowData = Group(vert + Word(alphas) + vert + delimited_list(number, "|") + vert)
trailing = rowDelim

datatable = heading + Dict(ZeroOrMore(rowData)) + trailing

# now parse data and print results
data = datatable.parse_string(testData)







# now print transpose of data table, using column labels read from table header and
# values from data lists


for i in range(1, len(data)):



for i in range(len(data.columns)):

    for j in range(len(data) - 1):


