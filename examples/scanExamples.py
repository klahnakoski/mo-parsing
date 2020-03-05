#
# scanExamples.py
#
#  Illustration of using mo_parsing's scanString,transformString, and searchString methods
#
# Copyright (c) 2004, 2006 Paul McGuire
#
from mo_parsing import (
    Word,
    alphas,
    alphanums,
    Literal,
    restOfLine,
    OneOrMore,
    empty,
    Suppress,
    replaceWith,
)

# simulate some C++ code
testData = """
#define MAX_LOCS=100
#define USERNAME = "floyd"
#define PASSWORD = "swordfish"

a = MAX_LOCS;
CORBA::initORB("xyzzy", USERNAME, PASSWORD );

"""

#################



# simple grammar to match #define's
ident = Word(alphas, alphanums + "_")
macroDef = (
    Literal("#define")
    + ident.setResultsName("name")
    + "="
    + restOfLine.setResultsName("value")
)
for t, s, e in macroDef.scanString(testData):


# or a quick way to make a dictionary of the names and values
# (return only key and value tokens, and construct dict from key-value pairs)
# - empty ahead of restOfLine advances past leading whitespace, does implicit lstrip during parsing
macroDef = Suppress("#define") + ident + Suppress("=") + empty + restOfLine
macros = dict(list(macroDef.searchString(testData)))




#################



# convert C++ namespaces to mangled C-compatible names
scopedIdent = ident + OneOrMore(Literal("::").suppress() + ident)
scopedIdent.setParseAction(lambda t: "_".join(t))




# or a crude pre-processor (use parse actions to replace matching text)
def substituteMacro(s, l, t):
    if t[0] in macros:
        return macros[t[0]]


ident.setParseAction(substituteMacro)
ident.ignore(macroDef)




#################



from mo_parsing import dblQuotedString, LineStart

# remove all string macro definitions (after extracting to a string resource table?)
stringMacroDef = Literal("#define") + ident + "=" + dblQuotedString + LineStart()
stringMacroDef.setParseAction(replaceWith(""))

