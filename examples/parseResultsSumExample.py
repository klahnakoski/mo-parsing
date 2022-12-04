#
# parseResultsSumExample.py
#
# Sample script showing the value in merging ParseResults retrieved by search_string,
# using Python's builtin sum() method
#

from mo_parsing.helpers import *

samplestr1 = "garbage;DOB 10-10-2010;more garbage\nID PARI12345678;more garbage"
samplestr2 = "garbage;ID PARI12345678;more garbage\nDOB 10-10-2010;more garbage"
samplestr3 = "garbage;DOB 10-10-2010"
samplestr4 = "garbage;ID PARI12345678;more garbage- I am cool"

dob_ref = "DOB" + Regex(r"\d{2}-\d{2}-\d{4}")("dob")
id_ref = "ID" + Word(alphanums, exact=12)("id")
info_ref = "-" + restOfLine("info")

person_data = dob_ref | id_ref | info_ref

for test in (
    samplestr1,
    samplestr2,
    samplestr3,
    samplestr4,
):
    person = sum(person_data.search_string(test))



