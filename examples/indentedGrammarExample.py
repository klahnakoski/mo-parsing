# indentedGrammarExample.py
#
# Copyright (c) 2006,2016  Paul McGuire
#
# A sample of a mo_parsing grammar using indentation for
# grouping (like Python does).
#
# Updated to use indentedBlock helper method.
#

from mo_parsing import *

data = """\
def A(z):
  A1
  B = 100
  G = A2
  A2
  A3
B
def BB(a,b,c):
  BB1
  def BBA():
    bba1
    bba2
    bba3
C
D
def spam(x,y):
     def eggs(z):
         pass
"""


indentStack = [1]
stmt = Forward()
suite = indentedBlock(stmt, indentStack)

identifier = Word(alphas, alphanums)
funcDecl = (
    "def" + identifier + Group("(" + Optional(delimitedList(identifier)) + ")") + ":"
)
funcDef = Group(funcDecl + suite)

rvalue = Forward()
funcCall = Group(identifier + "(" + Optional(delimitedList(rvalue)) + ")")
rvalue << (funcCall | identifier | Word(nums))
assignment = Group(identifier + "=" + rvalue)
stmt << (funcDef | assignment | identifier)

module_body = OneOrMore(stmt)

parseTree = module_body.parseString(data)

