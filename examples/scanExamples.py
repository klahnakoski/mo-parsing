#
# scanExamples.py
#
#  Illustration of using mo_parsing's scan_string,transform_string, and search_string methods
#
# Copyright (c) 2004, 2006 Paul McGuire
#
from mo_parsing import (
    Word,
    Literal,
    OneOrMore,
    Suppress, LineStart
)

# simulate some C++ code
from mo_parsing.helpers import restOfLine, dblQuotedString
from mo_parsing.utils import alphas, alphanums

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
    + ident.set_token_name("name")
    + "="
    + restOfLine.set_token_name("value")
)
for t, s, e in macroDef.scan_string(testData):
    pass

# or a quick way to make a dictionary of the names and values
# (return only key and value tokens, and construct dict from key-value pairs)
# - empty ahead of restOfLine advances past leading whitespace, does implicit lstrip during parsing
macroDef = Suppress("#define") + ident + Suppress("=") + Empty + restOfLine
macros = dict(list(macroDef.search_string(testData)))




#################



# convert C++ namespaces to mangled C-compatible names
scopedIdent = ident + OneOrMore(Literal("::").suppress() + ident)
scopedIdent.add_parse_action(lambda t: "_".join(t))




# or a crude pre-processor (use parse actions to replace matching text)
def substituteMacro(t, l, s):
    if t[0] in macros:
        return macros[t[0]]


ident.add_parse_action(substituteMacro)
ident.ignore(macroDef)


# remove all string macro definitions (after extracting to a string resource table?)
stringMacroDef = Literal("#define") + ident + "=" + dblQuotedString + LineStart()
stringMacroDef.add_parse_action(lambda: "")

