#
# cpp_enum_parser.py
#
# Posted by Mark Tolonen on comp.lang.python in August, 2009,
# Used with permission.
#
# Parser that scans through C or C++ code for enum definitions, and
# generates corresponding Python constant definitions.
#
#
from mo_testing.fuzzytestcase import assertAlmostEqual

from mo_parsing.helpers import *

# sample string with enums and other stuff
sample = """
    stuff before
    enum hello {
        Zero,
        One,
        Two,
        Three,
        Five=5,
        Six,
        Ten=10
        };
    in the middle
    enum blah
        {
        alpha,
        beta,
        gamma = 10 ,
        zeta = 50
        };
    at the end
    """

# syntax we don't want to see in the final parse tree
LBRACE, RBRACE, EQ, COMMA = map(Suppress, "{}=,")
_enum = Suppress("enum")
identifier = Word(alphas, alphanums + "_")
integer = Word(nums)
enumValue = Group(
    identifier("name")
    + Optional(EQ + integer("value").add_parse_action(lambda t: int(t[0])))
)
enumList = Group(enumValue + ZeroOrMore(COMMA + enumValue))
enum = _enum + identifier("enum") + LBRACE + enumList("names") + RBRACE

assertAlmostEqual(
    list(t for t, _, _ in enum.scan_string(sample)),
    [
        {
            "enum": "hello",
            "names": [
                {"name": "Zero"},
                {"name": "One"},
                {"name": "Two"},
                {"name": "Three"},
                {"name": "Five", "value": 5},
                {"name": "Six"},
                {"name": "Ten", "value": 10},
            ],
        },
        {
            "enum": "blah",
            "names": [
                {"name": "alpha"},
                {"name": "beta"},
                {"name": "gamma", "value": 10},
                {"name": "zeta", "value": 50},
            ],
        },
    ],
)
