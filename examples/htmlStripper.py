#
# htmlStripper.py
#
#  Sample code for stripping HTML markup tags and scripts from
#  HTML source files.
#
# Copyright (c) 2006, 2016, Paul McGuire
#
from urllib.request import urlopen
from mo_parsing import (
    makeHTMLTags,
    commonHTMLEntity,
    replaceHTMLEntity,
    htmlComment,
    anyOpenTag,
    anyCloseTag,
    LineEnd,
    replaceWith,
)

scriptOpen, scriptClose = makeHTMLTags("script")
scriptBody = scriptOpen + scriptOpen.tag_body + scriptClose
commonHTMLEntity.addParseAction(replaceHTMLEntity)

# get some HTML
targetURL = "https://wiki.python.org/moin/PythonDecoratorLibrary"
with urlopen(targetURL) as targetPage:
    targetHTML = targetPage.read().decode("UTF-8")

# first pass, strip out tags and translate entities
firstPass = (
    (htmlComment | scriptBody | commonHTMLEntity | anyOpenTag | anyCloseTag)
    .suppress()
    .transformString(targetHTML)
)

# first pass leaves many blank lines, collapse these down
repeatedNewlines = LineEnd() * (2,)
repeatedNewlines = repeatedNewlines.addParseAction(replaceWith("\n\n"))
secondPass = repeatedNewlines.transformString(firstPass)

