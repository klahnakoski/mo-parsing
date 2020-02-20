# commasep.py
#
# comma-separated list example, to illustrate the advantages of using
# the mo_parsing comma_separated_list as opposed to string.split(","):
# - leading and trailing whitespace is implicitly trimmed from list elements
# - list elements can be quoted strings, which can safely contain commas without breaking
#    into separate elements
#
# Copyright (c) 2004-2016, Paul McGuire
#

import mo_parsing as pp

ppc = pp.mo_parsing_common

testData = [
    "a,b,c,100.2,,3",
    "d, e, j k , m  ",
    "'Hello, World', f, g , , 5.1,x",
    "John Doe, 123 Main St., Cleveland, Ohio",
    "Jane Doe, 456 St. James St., Los Angeles , California ",
    "",
]

ppc.comma_separated_list.runTests(testData)
