from mo_parsing.helpers import QuotedString

wikiInput = """
Here is a simple Wiki input:
  *This is in italics.*
  **This is in bold!**
  ***This is in bold italics!***
  Here's a URL to {{Pyparsing's Wiki Page->https://site-closed.wikispaces.com}}
"""


def convertToHTML(opening, closing):
    def conversionParseAction(t, l, s):
        return opening + t[0] + closing

    return conversionParseAction


italicized = QuotedString("*").add_parse_action(convertToHTML("<I>", "</I>"))
bolded = QuotedString("**").add_parse_action(convertToHTML("<B>", "</B>"))
boldItalicized = QuotedString("***").add_parse_action(convertToHTML("<B><I>", "</I></B>"))


def convertToHTML_A(t, l, s):
    try:
        text, url = t[0].split("->")
    except ValueError:
        raise ParseFatalException(s, l, "invalid URL link reference: " + t[0])
    return '<A href="{}">{}</A>'.format(url, text)


urlRef = QuotedString("{{", end_quote_char="}}").add_parse_action(convertToHTML_A)

wikiMarkup = urlRef | boldItalicized | bolded | italicized



