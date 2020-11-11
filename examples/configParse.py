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
    printables,
    restOfLine,
    engine,
    Empty,
)

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
        engine.CURRENT.add_ignore(comment)

        nonrbrack = "".join([c for c in printables if c != "]"]) + " \t"
        nonequals = "".join([c for c in printables if c != "="]) + " \t"

        sectionDef = lbrack + Word(nonrbrack) + rbrack

        # strip any leading or trailing blanks from key
        def stripKey(tokens):
            return [t.strip() for t in tokens]

        keyDef = ~lbrack + Word(nonequals).addParseAction(stripKey) + equals + Empty + restOfLine

        # using Dict will allow retrieval of named data fields as attributes of the parsed results
        inibnf = Dict(ZeroOrMore(Group(sectionDef + Dict(ZeroOrMore(Group(keyDef))))))

    return inibnf
