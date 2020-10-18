#
# lucene_grammar.py
#
# Copyright 2011, Paul McGuire
#
# implementation of Lucene grammar, as decribed
# at http://svn.apache.org/viewvc/lucene/dev/trunk/lucene/docs/queryparsersyntax.html
#

from mo_parsing import *
from mo_parsing.helpers import integer, fnumber

COLON, LBRACK, RBRACK, LBRACE, RBRACE, TILDE, CARAT = map(Literal, ":[]{}~^")
LPAR, RPAR = map(Suppress, "()")
and_, or_, not_, to_ = map(CaselessKeyword, "AND OR NOT TO".split())
keyword = and_ | or_ | not_ | to_

expression = Forward()

valid_word = Regex(
    r'([a-zA-Z0-9*_+.-]|\\\\|\\([+\-!(){}\[\]^"~*?:]|\|\||&&))+'
).set_parser_name("word")
valid_word.addParseAction(
    lambda t: t[0].replace("\\\\", chr(127)).replace("\\", "").replace(chr(127), "\\")
)

string = QuotedString('"')

required_modifier = Literal("+")("required")
prohibit_modifier = Literal("-")("prohibit")
proximity_modifier = Group(TILDE + integer("proximity"))
number = fnumber
fuzzy_modifier = TILDE + Optional(number, default=0.5)("fuzzy")

term = Forward()
field_name = valid_word.set_parser_name("fieldname")
incl_range_search = Group(LBRACK - term("lower") + to_ + term("upper") + RBRACK)
excl_range_search = Group(LBRACE - term("lower") + to_ + term("upper") + RBRACE)
range_search = incl_range_search("incl_range") | excl_range_search("excl_range")
boost = CARAT - number("boost")

string_expr = Group(string + proximity_modifier) | string
word_expr = Group(valid_word + fuzzy_modifier) | valid_word
term << (
    Optional(field_name("field") + COLON)
    + (word_expr | string_expr | range_search | Group(LPAR + expression + RPAR))
    + Optional(boost)
)
term.addParseAction(lambda t: [t] if "field" in t or "boost" in t else None)

expression << infixNotation(
    term,
    [
        (required_modifier | prohibit_modifier, 1, RIGHT_ASSOC),
        ((not_ | "!").addParseAction(lambda: "NOT"), 1, RIGHT_ASSOC),
        ((and_ | "&&").addParseAction(lambda: "AND"), 2, LEFT_ASSOC),
        (Optional(or_ | "||").addParseAction(lambda: "OR"), 2, LEFT_ASSOC),
    ],
)

# test strings taken from grammar description doc, and TestQueryParser.java
tests = r"""
    # Success tests
    a and b
    a and not b
    a and !b
    a && !b
    a&&!b
    name:a
    name:a and not title:b
    (a^100 c d f) and !z
    name:"blah de blah"
    title:(+return +"pink panther")
    title:"The Right Way" AND text:go
    title:"Do it right" AND right
    title:Do it right
    roam~
    roam~0.8
    "jakarta apache"~10
    mod_date:[20020101 TO 20030101]
    title:{Aida TO Carmen}
    jakarta apache
    jakarta^4 apache
    "jakarta apache"^4 "Apache Lucene"
    "jakarta apache" jakarta
    "jakarta apache" OR jakarta
    "jakarta apache" AND "Apache Lucene"
    +jakarta lucene
    "jakarta apache" NOT "Apache Lucene"
    "jakarta apache" -"Apache Lucene"
    (jakarta OR apache) AND website
    \(1+1\)\:2
    c\:\\windows
    (fieldX:xxxxx OR fieldy:xxxxxxxx)^2 AND (fieldx:the OR fieldy:foo)
    (fieldX:xxxxx fieldy:xxxxxxxx)^2 AND (fieldx:the fieldy:foo)
    (fieldX:xxxxx~0.5 fieldy:xxxxxxxx)^2 AND (fieldx:the fieldy:foo)
    +term -term term
    foo:term AND field:anotherTerm
    germ term^2.0
    (term)^2.0
    (foo OR bar) AND (baz OR boo)
    +(apple \"steve jobs\") -(foo bar baz)
    +title:(dog OR cat) -author:\"bob dole\"
    a AND b
    +a +b
    (a AND b)
    c OR (a AND b)
    c (+a +b)
    a AND NOT b
    +a -b
    a AND -b
    a AND !b
    a && b
    a && ! b
    a OR b
    a b
    a || b
    a OR !b
    a -b
    a OR ! b
    a OR -b
    a - b
    a + b
    a ! b
    +foo:term +anotherterm
    hello
    term^2.0
    (germ term)^2.0
    term^2
    +(foo bar) +(baz boo)
    ((a OR b) AND NOT c) OR d
    (+(a b) -c) d
    field
    a&&b
    .NET
    term
    germ
    3
    term 1.0 1 2
    term term1 term2
    term term term
    term*
    term*^2
    term*^2.0
    term~
    term~2.0
    term~0.7
    term~^3
    term~2.0^3.0
    term*germ
    term*germ^3
    term*germ^3.0
    term~1.1
    [A TO C]
    t*erm*
    *term*
    term term^3.0 term
    term stop^3.0 term
    term +stop term
    term -stop term
    drop AND (stop) AND roll
    +drop +roll
    term +(stop) term
    term -(stop) term
    drop AND stop AND roll
    term phrase term
    term (phrase1 phrase2) term
    term AND NOT phrase term
    +term -(phrase1 phrase2) term
    stop^3
    stop
    (stop)^3
    ((stop))^3
    (stop^3)
    ((stop)^3)
    (stop)
    ((stop))
    term +stop
    [ a TO z]
    [a TO z]
    [ a TO z ]
    { a TO z}
    {a TO z}
    { a TO z }
    { a TO z }^2.0
    {a TO z}^2.0
    [ a TO z] OR bar
    [a TO z] bar
    [ a TO z] AND bar
    +[a TO z] +bar
    ( bar blar { a TO z})
    bar blar {a TO z}
    gack ( bar blar { a TO z})
    gack (bar blar {a TO z})
    [* TO Z]
    [* TO z]
    [A TO *]
    [a TO *]
    [* TO *]
    [\* TO \*]
    \!blah
    \:blah
    blah
    \~blah
    \*blah
    a
    a-b:c
    a+b:c
    a\:b:c
    a\\b:c
    a:b-c
    a:b+c
    a:b\:c
    a:b\\c
    a:b-c*
    a:b+c*
    a:b\:c*
    a:b\\c*
    a:b-c~2.0
    a:b+c~2.0
    a:b\:c~
    a:b\\c~
    [a- TO a+]
    [ a\\ TO a\* ]
    c\:\\temp\\\~foo.txt
    abc
    XYZ
    (item:\\ item:ABCD\\)
    \*
    *
    \\
    \||
    \&&
    a\:b\:c
    a\\b\:c
    a\:b\\c
    a\:b\:c\*
    a\:b\\\\c\*
    a:b-c~
    a:b+c~
    a\:b\:c\~
    a\:b\\c\~
    +weltbank +worlbank
    +term +term +term
    term +term term
    term term +term
    term +term +term
    -term term term
    -term +term +term
    on
    on^1.0
    hello^2.0
    the^3
    the
    some phrase
    xunit~
    one two three
    A AND B OR C AND D
    +A +B +C +D
    foo:zoo*
    foo:zoo*^2
    zoo
    foo:*
    foo:*^2
    *:foo
    a:the OR a:foo
    a:woo OR a:the
    *:*
    (*:*)
    +*:* -*:*
    the wizard of ozzy
    """

failtests = r"""
    # Failure tests

    # multiple ':'s in term
    field:term:with:colon some more terms

    # multiple '^'s in term
    (sub query)^5.0^2.0 plus more
    a:b:c
    a:b:c~
    a:b:c*
    a:b:c~2.0
    # \+blah
    # \-blah
    # foo \|| bar
    foo \AND bar
    \a
    # a\-b:c
    # a\+b:c
    a\b:c
    # a:b\-c
    # a:b\+c
    # a\-b\:c
    # a\+b\:c
    a:b\c*
    # a:b\-c~
    # a:b\+c~
    a:b\c
    # a:b\-c*
    # a:b\+c*
    # [ a\- TO a\+ ]
    [a\ TO a*]
    # a\\\+b
    # a\+b
    c:\temp\~foo.txt
    XY\
    a\u0062c
    a:b\c~2.0
    XY\u005a
    XY\u005A
    item:\ item:ABCD\
    \
    a\ or b
    # a\:b\-c
    # a\:b\+c
    # a\:b\-c\*
    # a\:b\+c\*
    # a\:b\-c\~
    # a\:b\+c\~
    a:b\c~
    [ a\ TO a* ]
    """

success1, _ = expression.runTests(tests)
if not success1:
    raise Exception("All tests: FAIL")

success2, _ = expression.runTests(failtests, failureTests=True)
if not success2:
    raise Exception("All tests: FAIL")
