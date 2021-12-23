# encoding: utf-8
import ast
from unittest import TestCase, skip

from mo_dots import unwraplist
from mo_files import File
from mo_future import is_text, text
from mo_http import http
from mo_threads import stop_main_thread
from mo_threads.profiles import CProfiler, write_profiles
from mo_times import Timer

from mo_parsing import (
    Whitespace,
    Literal,
    Regex,
    Word,
    Group,
    Forward,
    Log,
    ParseException,
    Optional,
    OneOrMore,
    Suppress,
    SkipTo,
    OpenDict,
    Annotation,
)

tag_stack = []


def push_name(tokens):
    tag_stack.append(tokens[0])


def pop_name(tokens, index, string):
    expecting = tag_stack[-1]
    if tokens[0] == expecting:
        tag_stack.pop()
        return
    raise ParseException(tokens.type, index, string, f"expecting close tag {expecting}")


def pop():
    tag_stack.pop()


def unquote(tokens):
    return ast.literal_eval(tokens[0])


def to_dict(tokens):
    output = {}
    for a in tokens.tokens:
        key, value = list(a)
        output[key] = value
    return output


class XmlParser(object):
    def __init__(self):
        with Whitespace() as white:
            white.set_literal(lambda v: Literal(v).suppress())

            init = "".join(sorted(set(
                Regex("[A-Za-z:_\u00C0-\u00D6\u00D8-\u00F6\u00F8-\u02FF]")
                .expr
                .parser_config
                .include
            )))
            rest = "".join(sorted(
                set(Regex("[\\-.0-9\u00B7\u0300-\u036F]").expr.parser_config.include)
                | set(init)
            ))
            name = Word(init_chars=init, body_chars=rest)

            attr = Group(
                name / (lambda t: t[0])
                + "="
                + ((Regex('"[^"]*"') | Regex("'[^']*'")) / unquote)
            )

            text = Regex("[^<]+")
            cdata = "<![CDATA[" + SkipTo("]]>") / (lambda t: t[0])

            tag = Forward()
            tag << (
                "<"
                + (name("name") / push_name)
                + Optional((OneOrMore(attr) / to_dict)("attributes"))
                + (
                    Suppress("/>") / pop
                    | (
                        ">"
                        + Optional(Group(OneOrMore(tag | cdata | text))("children"))
                        + "</"
                        + (name / pop_name)
                        + ">"
                    )
                )
            ) / dict

            self.tag = OneOrMore(tag | cdata | text).finalize()

    def parse(self, content):
        tag_stack.clear()
        try:
            return self.tag.parse(content)[0]
        finally:
            if tag_stack:
                Log.error(
                    "expecting closing tags: {{tags}}",
                    tags=unwraplist(list(reversed(tag_stack))),
                )


parse = XmlParser().parse


class TestXmlParser(TestCase):
    def test_tag(self):
        result = parse("<simple></simple>")
        self.assertEqual(result, {"name": "simple"})

    def test_content(self):
        xml = """<greeting>Hello, world!</greeting>"""
        result = parse(xml)
        self.assertEqual(result, {"name": "greeting", "children": "Hello, world!"})

    def test_contents(self):
        xml = """<greeting>Hello, world!<cr/></greeting>"""
        result = parse(xml)
        self.assertEqual(
            result, {"name": "greeting", "children": ["Hello, world!", {"name": "cr"}]}
        )

    def test_cdata(self):
        result = parse("""<![CDATA[<greeting>Hello, world!</greeting>]]>""")
        self.assertEqual(result, "<greeting>Hello, world!</greeting>")

    def test_mismatch(self):
        with self.assertRaises(Exception):
            parse("<simple></simpler>")

    def test_attributes(self):
        result = parse("""<a href="234"/>""")
        self.assertEqual(result, {"name": "a", "attributes": {"href": "234"}})

    @skip("not a fancy parser")
    def test_header(self):
        xml = """<?xml version="1.0"?>
        <greeting>Hello, world!</greeting> """
        result = parse(xml)
        self.assertEqual(result, {"name": "simple", "children": ["Hello, world!"]})

    def test_speed(self):
        http.default_headers["Referer"] = "https://github.com/klahnakoski/mo-parsing"
        xml = http.get("http://www.quickfixengine.org/FIX44.xml").content.decode("utf8")

        with CProfiler() as profile:
            parse(xml)
        write_profiles()
