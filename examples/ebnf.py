# This module tries to implement ISO 14977 standard with mo_parsing.
# mo_parsing version 1.1 or greater is required.

# ISO 14977 standardize The Extended Backus-Naur Form(EBNF) syntax.
# You can read a final draft version here:
# https://www.cl.cam.ac.uk/~mgk25/iso-ebnf.html
#
# Submitted 2004 by Seo Sanghyeon
#
from mo_parsing import (
    Word,
    Suppress,
    Forward,
    CharsNotIn,
    Optional,
    ZeroOrMore,
    Literal,
    OneOrMore,
    And,
    NotAny,
    Or,
    Group,
)
from mo_parsing.whitespaces import Whitespace
from mo_parsing.helpers import delimited_list
from mo_parsing.utils import alphas, alphanums, nums

whitespace = Whitespace().use()
ebnfComment = (
        "(*" + ZeroOrMore(CharsNotIn("*") | ("*" + ~Literal(")"))) + "*)"
).set_parser_name("ebnfComment")
whitespace.add_ignore(ebnfComment)


def do_integer(toks):
    return int(toks[0])


def do_meta_identifier(toks):
    global forward_count
    name = toks[0]
    if name in symbol_table:
        return symbol_table[name]
    else:
        forward_count += 1
        symbol_table[name] = Forward().set_parser_name(name)
        return symbol_table[name]


def do_terminal_string(toks):
    return Literal(toks[0])


def do_optional_sequence(toks):
    return Optional(toks[0])


def do_repeated_sequence(toks):
    return ZeroOrMore(toks[0])


def do_grouped_sequence(toks):
    return Group(toks[0])


def do_syntactic_primary(toks):
    return toks[0]


def do_syntactic_factor(toks):
    if toks.length() == 2:
        # integer * syntactic_primary
        return And([toks[1]] * toks[0])
    else:
        # syntactic_primary
        return [toks[0]]


def do_syntactic_term(toks):
    if toks.length() == 2:
        # syntactic_factor - syntactic_factor
        return NotAny(toks[1]) + toks[0]
    else:
        # syntactic_factor
        return [toks[0]]


def do_single_definition(toks):
    toks = toks
    if toks.length() > 1:
        # syntactic_term , syntactic_term , ...
        return And(toks)
    else:
        # syntactic_term
        return [toks[0]]


def do_definitions_list(toks):
    toks = toks
    if toks.length() > 1:
        # single_definition | single_definition | ...
        return Or(toks)
    else:
        # single_definition
        return [toks[0]]


forward_count = 0


def do_syntax_rule(toks):
    global forward_count
    # meta_identifier = definitions_list ;
    assert toks[0].expr == None, "Duplicate definition"
    forward_count -= 1
    toks[0] << toks[1]
    return [toks[0]]


symbol_table = {}


def do_syntax():
    # syntax_rule syntax_rule ...
    return symbol_table


integer = Word(nums).add_parse_action(do_integer).set_parser_name("integer")
meta_identifier = (
    Word(alphas, alphanums + "_")
    .add_parse_action(do_meta_identifier)
    .set_parser_name("meta identifier")
)
terminal_string = (
    (
        Suppress("'") + CharsNotIn("'") + Suppress("'")
        ^ Suppress('"') + CharsNotIn('"') + Suppress('"')
    )
    .add_parse_action(do_terminal_string)
    .set_parser_name("terminal string")
)
definitions_list = Forward()
optional_sequence = (
    (Suppress("[") + definitions_list + Suppress("]"))
    .add_parse_action(do_optional_sequence)
    .set_parser_name("optional sequence")
)
repeated_sequence = (
    (Suppress("{") + definitions_list + Suppress("}"))
    .add_parse_action(do_repeated_sequence)
    .set_parser_name("repeated sequence")
)
grouped_sequence = (
    (Suppress("(") + definitions_list + Suppress(")"))
    .add_parse_action(do_grouped_sequence)
    .set_parser_name("grouped sequence")
)
syntactic_primary = (
    (
        optional_sequence
        ^ repeated_sequence
        ^ grouped_sequence
        ^ meta_identifier
        ^ terminal_string
    )
    .add_parse_action(do_syntactic_primary)
    .set_parser_name("syntatic primary")
)
syntactic_factor = (
    (Optional(integer + Suppress("*")) + syntactic_primary)
    .add_parse_action(do_syntactic_factor)
    .set_parser_name("syntatic factor")
)
syntactic_term = (
    (syntactic_factor + Optional(Suppress("-") + syntactic_factor))
    .add_parse_action(do_syntactic_term)
    .set_parser_name("syntatic term")
)
single_definition = (
    delimited_list(syntactic_term, ",")
    .add_parse_action(do_single_definition)
    .set_parser_name("single definition")
)
definitions_list << delimited_list(single_definition, "|").add_parse_action(
    do_definitions_list
).set_parser_name("definitions list")
syntax_rule = (
    (meta_identifier + Suppress("=") + definitions_list + Suppress(";"))
    .add_parse_action(do_syntax_rule)
    .set_parser_name("syntax rule")
)
syntax = OneOrMore(syntax_rule).add_parse_action(do_syntax)


def parse(ebnf, given_table={}):
    global forward_count
    with Whitespace():
        symbol_table.clear()
        symbol_table.update(given_table)
        forward_count = 0
        table = syntax.parse_string(ebnf)[0]
        assert forward_count == 0, "Missing definition"
        for name in table:
            expr = table[name]
            expr.set_parser_name(name)
        return table

whitespace.release()
