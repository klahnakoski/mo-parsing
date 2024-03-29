# jsonParser.py
#
# Implementation of a simple JSON parser, returning a hierarchical
# ParseResults object support both list- and dict-style data access.
#
# Copyright 2006, by Paul McGuire
#
# Updated 8 Jan 2007 - fixed dict grouping bug, and made elements and
#   members optional in array and object collections
#
# Updated 9 Aug 2016 - use more current mo_parsing constructs/idioms
#
from mo_future import text

from examples.jsonParser import jsonObject

testdata = """
{
    "glossary": {
        "title": "example glossary",
        "GlossDiv": {
            "title": "S",
            "GlossList":
                {
                "ID": "SGML",
                "SortAs": "SGML",
                "GlossTerm": "Standard Generalized Markup Language",
                "TrueValue": true,
                "FalseValue": false,
                "Gravity": -9.8,
                "LargestPrimeLessThan100": 97,
                "AvogadroNumber": 6.02E23,
                "EvenPrimesGreaterThan2": null,
                "PrimesLessThan10" : [2,3,5,7],
                "Acronym": "SGML",
                "Abbrev": "ISO 8879:1986",
                "GlossDef": "A meta-markup language, used to create markup languages such as DocBook.",
                "GlossSeeAlso": ["GML", "XML", "markup"],
                "EmptyDict" : {},
                "EmptyList" : []
                }
        }
    }
}
"""

results = jsonObject.parse_string(testdata)



def testPrint(x):
    print(text(x))


testPrint(results.glossary.title)
testPrint(results.glossary.GlossDiv.GlossList.ID)
testPrint(results.glossary.GlossDiv.GlossList.FalseValue)
testPrint(results.glossary.GlossDiv.GlossList.Acronym)
testPrint(results.glossary.GlossDiv.GlossList.EvenPrimesGreaterThan2)
testPrint(results.glossary.GlossDiv.GlossList.PrimesLessThan10)
