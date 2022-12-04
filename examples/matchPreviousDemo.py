#
# matchPreviousDemo.py
#

from mo_parsing import *

src = """
class a
...
end a;

class b
...
end b;

class c
...
end d;"""


identifier = Word(alphas)

classIdent = identifier("classname")  # note that this also makes a copy of identifier
classHead = "class" + classIdent
classBody = "..."
classEnd = "end" + matchPreviousLiteral(classIdent) + ";"
classDefn = classHead + classBody + classEnd

# use this form to catch syntax error
# classDefn = classHead + classBody - classEnd

for tokens in classDefn.search_string(src):

