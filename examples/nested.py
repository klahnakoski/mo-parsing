#
#  nested.py
#  Copyright, 2007 - Paul McGuire
#
#  Simple example of using nestedExpr to define expressions using
#  paired delimiters for grouping lists and sublists
#

from mo_parsing import *

data = """
{
     { item1 "item with } in it" }
     {
      {item2a item2b }
      {item3}
     }

}
"""

# use {}'s for nested lists
nestedItems = nestedExpr("{", "}")


# use default delimiters of ()'s
mathExpr = nestedExpr()

