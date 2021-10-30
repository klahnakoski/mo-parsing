#
#  nested.py
#  Copyright, 2007 - Paul McGuire
#
#  Simple example of using nested_expr to define expressions using
#  paired delimiters for grouping lists and sublists
#

from mo_parsing.helpers import nested_expr

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
nestedItems = nested_expr("{", "}")


# use default delimiters of ()'s
math_expr = nested_expr()

