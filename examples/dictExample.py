#
# dictExample.py
#
#  Illustration of using mo_parsing's Dict class to process tabular data
#
# Copyright (c) 2003, Paul McGuire
#
from mo_testing.fuzzytestcase import assertAlmostEqual

from mo_parsing import *
from mo_parsing import engines

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
heading = (
    Literal("+-------+------+------+------+------+------+------+------+------+")
    + "|       |  A1  |  B1  |  C1  |  D1  |  A2  |  B2  |  C2  |  D2  |"
    + "+=======+======+======+======+======+======+======+======+======+"
).suppress()
vert = Literal("|").suppress()
number = Word(nums).addParseAction(float)
rowData = Group(vert + Word(alphas) + vert + delimitedList(number, "|") + vert)
trailing = Literal(
    "+-------+------+------+------+------+------+------+------+------+"
).suppress()

datatable = heading + Dict(ZeroOrMore(rowData)) + trailing

engines.CURRENT.set_debug_actions()

# now parse data and print results
data = datatable.parseString(testData)

expected = {
    "min": [7, 43, 7, 15, 82, 98, 1, 37],
    "max": [11, 52, 10, 17, 85, 112, 4, 39],
    "ave": [9, 47, 8, 16, 84, 106, 3, 38],
    "sdev": [1, 3, 1, 1, 1, 3, 1, 1],
}

assertAlmostEqual(data, expected)
