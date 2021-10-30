#
# htmlStripper.py
#
#  Sample code for stripping HTML markup tags and scripts from
#  HTML source files.
#
# Copyright (c) 2006, 2016, Paul McGuire
#
from mo_testing.fuzzytestcase import assertAlmostEqual
from mo_threads import MAIN_THREAD
from mo_times import Timer

from mo_parsing import LineEnd
from mo_parsing.helpers import makeHTMLTags, replaceHTMLEntity, commonHTMLEntity, html_comment, anyOpenTag, anyCloseTag
from mo_parsing.utils import Log

scriptOpen, scriptClose = makeHTMLTags("script")
scriptBody = scriptOpen + scriptOpen.tag_body + scriptClose
commonHTMLEntity.add_parse_action(replaceHTMLEntity)


# get some HTML
with open("examples/htmlStripper.html", "rb") as f:
    targetHTML = f.read().decode('utf8')

# first pass, strip out tags and translate entities
Log.start(cprofile=True)
with Timer("remove html"):
    firstPass = (
        (html_comment | scriptBody | commonHTMLEntity | anyOpenTag | anyCloseTag)
        .suppress()
        .transform_string(targetHTML)
    )

# first pass leaves many blank lines, collapse these down
with Timer("remove extra blank lines"):
    repeatedNewlines = LineEnd()[2:...].add_parse_action(lambda: "\n")
    secondPass = repeatedNewlines.transform_string(firstPass)

with open("examples/htmlStripper.out.txt", "wb") as f:
    f.write(secondPass.encode('utf8'))

with open("examples/htmlStripper.txt", "rb") as f:
    expected = f.read().decode('utf8')

assertAlmostEqual(secondPass.strip(), expected.strip())
MAIN_THREAD.stop()