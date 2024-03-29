# jsonParser.py
#
# Implementation of a simple JSON parser, returning a hierarchical
# ParseResults object support both list- and dict-style data access.
#
# Copyright 2006, by Paul McGuire
#
# Updated 8 Jan 2007 - fixed dict grouping bug, and made elements and
#   members optional in array and object collections
#
# Updated 9 Aug 2016 - use more current mo_parsing constructs/idioms
#
from mo_parsing.helpers import number, dblQuotedString, remove_quotes, delimited_list, cppStyleComment
from mo_parsing.whitespaces import Whitespace

json_bnf = """
object
    { members }
    {}
members
    string : value
    members , string : value
array
    [ elements ]
    []
elements
    value
    elements , value
value
    string
    number
    object
    array
    true
    false
    null
"""

from mo_parsing import *


def make_keyword(kwd_str, kwd_value):
    return Keyword(kwd_str).add_parse_action(lambda: kwd_value)


with Whitespace() as whitespace:

    TRUE = make_keyword("true", True)
    FALSE = make_keyword("false", False)
    NULL = make_keyword("null", None)

    LBRACK, RBRACK, LBRACE, RBRACE, COLON = map(Suppress, "[]{}:")

    json_string = dblQuotedString.add_parse_action(remove_quotes)
    jsonNumber = number

    jsonObject = Forward()
    jsonValue = Forward()
    jsonElements = delimited_list(jsonValue)
    jsonArray = Group(LBRACK + Optional(jsonElements, []) + RBRACK)
    jsonValue << (
        json_string | jsonNumber | jsonObject | jsonArray | TRUE | FALSE | NULL
    )
    memberDef = Group(json_string + COLON + jsonValue)
    jsonMembers = delimited_list(memberDef)
    jsonObject << Dict(LBRACE + Optional(jsonMembers) + RBRACE)
    jsonComment = cppStyleComment
    whitespace.add_ignore(jsonComment)
