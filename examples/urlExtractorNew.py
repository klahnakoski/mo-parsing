# URL extractor
# Copyright 2004, Paul McGuire
from urllib.request import urlopen

from mo_parsing import makeHTMLTags

# Define the mo_parsing grammar for a URL, that is:
#    URLlink ::= <a href= URL>linkText</a>
#    URL ::= doubleQuotedString | alphanumericWordPath
# Note that whitespace may appear just about anywhere in the link.  Note also
# that it is not necessary to explicitly show this in the mo_parsing grammar; by default,
# mo_parsing skips over whitespace between tokens.
linkOpenTag, linkCloseTag = makeHTMLTags("a")
link = linkOpenTag + linkOpenTag.tag_body("body") + linkCloseTag.suppress()

# Go get some HTML with some links in it.
with urlopen("https://www.cnn.com/") as serverListPage:
    htmlText = serverListPage.read()

# scan_string is a generator that loops through the input htmlText, and for each
# match yields the tokens and start and end locations (for this application, we are
# not interested in the start and end values).
for toks, strt, end in link.scan_string(htmlText):
    print(toks.startA.href, "->", toks.body)

# Create dictionary from list comprehension, assembled from each pair of tokens returned
# from a matched URL.
print(
    {toks.body: toks.startA.href for toks, strt, end in link.scan_string(htmlText)}
)
