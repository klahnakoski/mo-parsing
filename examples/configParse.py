#
# configparse.py
#
# an example of using the parsing module to be able to process a .INI configuration file
#
# Copyright (c) 2003, Paul McGuire
#

from mo_parsing import (
    Literal,
    Word,
    ZeroOrMore,
    Group,
    Dict,
    Optional,
    whitespaces,
    Empty,
)
from mo_parsing.helpers import restOfLine
from mo_parsing.utils import printables

inibnf = None


def inifile_BNF():
    global inibnf

    if not inibnf:

        # punctuation
        lbrack = Literal("[").suppress()
        rbrack = Literal("]").suppress()
        equals = Literal("=").suppress()
        semi = Literal(";")

        comment = semi + Optional(restOfLine)
        whitespaces.CURRENT.add_ignore(comment)

        nonrbrack = "".join([c for c in printables if c != "]"]) + " \t"
        nonequals = "".join([c for c in printables if c != "="]) + " \t"

        sectionDef = lbrack + Word(nonrbrack) + rbrack
        keyDef = ~lbrack + Word(nonequals) + equals + Empty + restOfLine
        # strip any leading or trailing blanks from key
        def stripKey(tokens):
            return [t.strip() for t in tokens]

        keyDef = keyDef.add_parse_action(stripKey)

        # using Dict will allow retrieval of named data fields as attributes of the parsed results
        inibnf = Dict(ZeroOrMore(Group(sectionDef + Dict(ZeroOrMore(Group(keyDef)))))).streamline()

    return inibnf
