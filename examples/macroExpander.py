# macroExpander.py
#
# Example mo_parsing program for performing macro expansion, similar to
# the C pre-processor.  This program is not as fully-featured, simply
# processing macros of the form:
#     #def xxx yyyyy
# and replacing xxx with yyyyy in the rest of the input string.  Macros
# can also be composed using other macros, such as
#     #def zzz xxx+1
# Since xxx was previously defined as yyyyy, then zzz will be replaced
# with yyyyy+1.
#
# Copyright 2007 by Paul McGuire
#
from mo_parsing import *

# define the structure of a macro definition (the empty term is used
# to advance to the next non-whitespace character)
identifier = Word(alphas + "_", alphanums + "_")
macroDef = "#def" + identifier("macro") + Empty + restOfLine("value")

# define a placeholder for defined macros - initially nothing
macroExpr = Forward()
macroExpr << NoMatch()

# global dictionary for macro definitions
macros = {}

# parse action for macro definitions
def processMacroDefn(t, l, s):
    macroVal = macroExpander.transformString(t.value)
    macros[t.macro] = macroVal
    macroExpr << MatchFirst(map(Keyword, macros.keys()))
    return "#def " + t.macro + " " + macroVal


# parse action to replace macro references with their respective definition
def processMacroRef(t, l, s):
    return macros[t[0]]


# attach parse actions to expressions
macroExpr.addParseAction(processMacroRef)
macroDef.addParseAction(processMacroDefn)

# define pattern for scanning through the input string
macroExpander = macroExpr | macroDef


# test macro substitution using transformString
testString = """
    #def A 100
    #def ALEN A+1

    char Astring[ALEN];
    char AA[A];
    typedef char[ALEN] Acharbuf;
    """


