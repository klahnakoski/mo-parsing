#
# nested_markup.py
#
# Example markup parser to recursively transform nested markup directives.
#
# Copyright 2019, Paul McGuire
#
from mo_parsing import *
from mo_parsing.helpers import originalTextFor, nestedExpr

wiki_markup = Forward()

# a method that will construct and return a parse action that will
# do the proper wrapping in opening and closing HTML, and recursively call
# wiki_markup.transformString on the markup body text
def convert_markup_to_html(opening, closing):
    def conversionParseAction(t, l, s):
        return opening + wiki_markup.transformString(t[1][1:-1]) + closing

    return conversionParseAction


# use a nestedExpr with originalTextFor to parse nested braces, but return the
# parsed text as a single string containing the outermost nested braces instead
# of a nested list of parsed tokens
markup_body = originalTextFor(nestedExpr("{", "}"))
italicized = ("ital" + markup_body).addParseAction(
    convert_markup_to_html("<I>", "</I>")
)
bolded = ("bold" + markup_body).addParseAction(convert_markup_to_html("<B>", "</B>"))

# another markup and parse action to parse links - again using transform string
# to recursively parse any markup in the link text
def convert_link_to_html(t, l, s):
    link_text, url = t._skipped
    t["link_text"] = wiki_markup.transformString(link_text)
    t["url"] = url
    return '<A href="{url}">{link_text}</A>'.format_map(t)


urlRef = (Keyword("link") + "{" + ... + "->" + ... + "}").addParseAction(
    convert_link_to_html
)

# now inject all the markup bits as possible markup expressions
wiki_markup <<= urlRef | italicized | bolded

# try it out!
wiki_input = """
Here is a simple Wiki input:

  ital{This is in italics}.
  bold{This is in bold}!
  bold{This is in ital{bold italics}! But this is just bold.}
  Here's a URL to link{Pyparsing's bold{Wiki Page}!->https://github.com/mo_parsing/mo_parsing/wiki}
"""

