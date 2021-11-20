# stackish.py
#
# Stackish is a data representation syntax, similar to JSON or YAML.  For more info on
# stackish, see http://www.savingtheinternetwithhate.com/stackish.html
#
# Copyright 2008, Paul McGuire
#

"""
NUMBER A simple integer type that's just any series of digits.
FLOAT A simple floating point type.
STRING A string is double quotes with anything inside that's not a " or
    newline character. You can include \n and \" to include these
    characters.
MARK Marks a point in the stack that demarcates the boundary for a nested
    group.
WORD Marks the root node of a group, with the other end being the nearest
    MARK.
GROUP Acts as the root node of an anonymous group.
ATTRIBUTE Assigns an attribute name to the previously processed node.
    This means that just about anything can be an attribute, unlike in XML.
BLOB A BLOB is unique to Stackish and allows you to record any content
    (even binary content) inside the structure. This is done by pre-
    sizing the data with the NUMBER similar to Dan Bernstein's netstrings
    setup.
SPACE White space is basically ignored. This is interesting because since
    Stackish is serialized consistently this means you can use \n as the
    separation character and perform reasonable diffs on two structures.
"""

from mo_testing.fuzzytestcase import assertAlmostEqual

from mo_parsing.helpers import *
from mo_parsing.infix import one_of

MARK, UNMARK, AT, COLON, QUOTE = map(Suppress, "[]@:'")

NUMBER = Word(nums).add_parse_action(lambda t: int(t[0]))
FLOAT = Combine(
    one_of("+ -") + Word(nums) + "." + Optional(Word(nums))
).add_parse_action(lambda t: float(t[0]))
STRING = QuotedString('"', multiline=True)
WORD = Word(alphas, alphanums + "_:")
ATTRIBUTE = Combine(AT + WORD)

strBody = Forward()


def setBodyLength(tokens):
    strBody << Many(AnyChar(), exact=int(tokens[0]))
    return ""


BLOB = Combine(
    QUOTE + Word(nums).add_parse_action(setBodyLength) + COLON + strBody + QUOTE
)

item = Forward()


def assignUsing(s):
    def assignPA(tokens):
        if s in tokens:
            tokens[tokens[s]] = tokens[0]
            del tokens[s]

    return assignPA


GROUP = (
    MARK
    + Group(ZeroOrMore(
        (item + Optional(ATTRIBUTE)("attr")).add_parse_action(assignUsing("attr"))
    ))
    + (WORD("name") | UNMARK)
).add_parse_action(assignUsing("name"))
item << (NUMBER | FLOAT | STRING | BLOB | GROUP)

result = item.parse_string("[ '10:1234567890' @name 25 @age +0.45 @percentage person:zed")
expected = {"person:zed": {"name": "1234567890", "age": 25, "percentage": 0.45}}
assertAlmostEqual(result, expected)

result = item.parse_string('[ [ "hello" 1 child root')
expected = {"root": {"child": ["hello", 1]}}
assertAlmostEqual(result, expected)

result = item.parse_string("[ \"child\" [ 200 '4:like' \"I\" \"hello\" things root")
expected = {"root": {"things": [200, "like", "I", "hello"]}}
assertAlmostEqual(result, expected)
expected = {"root": ["child"]}
assertAlmostEqual(result, expected)

result = item.parse_string("[ [ \"data\" [ 2 1 ] @numbers child root")
expected = {"root": {"child": ["data"]}}
assertAlmostEqual(result, expected)
expected = {"root": {"child": {"numbers": [2, 1]}}}
assertAlmostEqual(result, expected)

result = item.parse_string("[ [ 1 2 3 ] @test 4 5 6 root")
expected = {"root": {"test": [1, 2, 3]}}
assertAlmostEqual(result, expected)
expected = {"root": [[1, 2, 3], 4, 5, 6]}
assertAlmostEqual(result, expected)
