#
#  withAttribute.py
#  Copyright, 2007 - Paul McGuire
#
#  Simple example of using withAttribute parse action helper
#  to define
#
from mo_future import zip_longest
from mo_testing.fuzzytestcase import assertAlmostEqual

from mo_parsing import *
from mo_parsing.helpers import makeHTMLTags, real, withAttribute

data = """\
    <td align=right width=80><font size=2 face="New Times Roman,Times,Serif">&nbsp;49.950&nbsp;</font></td>
    <td align=left width=80><font size=2 face="New Times Roman,Times,Serif">&nbsp;50.950&nbsp;</font></td>
    <td align=right width=80><font size=2 face="New Times Roman,Times,Serif">&nbsp;51.950&nbsp;</font></td>
    """

td, tdEnd = makeHTMLTags("TD")
font, fontEnd = makeHTMLTags("FONT")
realNum = real
NBSP = Literal("&nbsp;")
patt = (
    td.addParseAction(withAttribute(align="right", width="80"))
    + font
    + NBSP
    + realNum("value")
    + NBSP
    + fontEnd
    + tdEnd
)

expecting = [{"value": 49.95}, {"value": 51.95}]

result = patt.searchString(data)
for r, e in zip_longest(patt.searchString(data), expecting):
    assertAlmostEqual(r, e)
