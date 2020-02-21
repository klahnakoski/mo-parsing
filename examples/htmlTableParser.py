#
# htmlTableParser.py
#
# Example of parsing a simple HTML table into a list of rows, and optionally into a little database
#
# Copyright 2019, Paul McGuire
#

from mo_parsing import *
import urllib.request


# define basic HTML tags, and compose into a Table
table, table_end = makeHTMLTags("table")
thead, thead_end = makeHTMLTags("thead")
tbody, tbody_end = makeHTMLTags("tbody")
tr, tr_end = makeHTMLTags("tr")
th, th_end = makeHTMLTags("th")
td, td_end = makeHTMLTags("td")
a, a_end = makeHTMLTags("a")

# method to strip HTML tags from a string - will be used to clean up content of table cells
strip_html = (anyOpenTag | anyCloseTag).suppress().transformString

# expression for parsing <a href="url">text</a> links, returning a (text, url) tuple
link = Group(a + a.tag_body("text") + a_end.suppress())
link.addParseAction(lambda t: (t[0].text, t[0].href))

# method to create table rows of header and data tags
def table_row(start_tag, end_tag):
    body = start_tag.tag_body
    body.addParseAction(tokenMap(str.strip), tokenMap(strip_html))
    row = Group(
        tr.suppress()
        + ZeroOrMore(start_tag.suppress() + body + end_tag.suppress())
        + tr_end.suppress()
    )
    return row


th_row = table_row(th, th_end)
td_row = table_row(td, td_end)

# define expression for overall table - may vary slightly for different pages
html_table = (
    table
    + tbody
    + Optional(th_row("headers"))
    + ZeroOrMore(td_row)("rows")
    + tbody_end
    + table_end
)


# read in a web page containing an interesting HTML table
with urllib.request.urlopen(
    "https://en.wikipedia.org/wiki/List_of_tz_database_time_zones"
) as page:
    page_html = page.read().decode()

tz_table = html_table.searchString(page_html)[0]

# convert rows to dicts
rows = [dict(zip(tz_table.headers, row)) for row in tz_table.rows]

# make a dict keyed by TZ database name
tz_db = {row["TZ database name"]: row for row in rows}

from pprint import pprint

print(tz_db["America/Chicago"])
