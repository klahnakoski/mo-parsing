# URL extractor
# Copyright 2004, Paul McGuire
import pprint
from urllib.request import urlopen

from mo_parsing import makeHTMLTags
from mo_parsing.helpers import stripHTMLTags

linkOpenTag, linkCloseTag = makeHTMLTags("a")

linkBody = linkOpenTag.tag_body
linkBody.setParseAction(stripHTMLTags)
linkBody.addParseAction(lambda toks: " ".join(toks[0].strip().split()))

link = linkOpenTag + linkBody("body") + linkCloseTag.suppress()

# Go get some HTML with some links in it.
with urlopen("https://www.cnn.com/") as serverListPage:
    htmlText = serverListPage.read().decode("UTF-8")

# scanString is a generator that loops through the input htmlText, and for each
# match yields the tokens and start and end locations (for this application, we are
# not interested in the start and end values).
for toks, strt, end in link.scanString(htmlText):
    print(toks)

# Create dictionary from list comprehension, assembled from each pair of tokens returned
# from a matched URL.
print({toks.body: toks.href for toks, strt, end in link.scanString(htmlText)})
