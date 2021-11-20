#
# ebnftest.py
#
# Test script for ebnf.py
#
# Submitted 2004 by Seo Sanghyeon
#

from examples import ebnf
from mo_parsing import *

grammar = """
syntax = (syntax_rule), {(syntax_rule)};
syntax_rule = meta_identifier, '=', definitions_list, ';';
definitions_list = single_definition, {'|', single_definition};
single_definition = syntactic_term, {',', syntactic_term};
syntactic_term = syntactic_factor,['-', syntactic_factor];
syntactic_factor = [integer, '*'], syntactic_primary;
syntactic_primary = optional_sequence | repeated_sequence |
  grouped_sequence | meta_identifier | terminal_string;
optional_sequence = '[', definitions_list, ']';
repeated_sequence = '{', definitions_list, '}';
grouped_sequence = '(', definitions_list, ')';
(*
terminal_string = "'", character - "'", {character - "'"}, "'" |
  '"', character - '"', {character - '"'}, '"';
 meta_identifier = letter, {letter | digit};
integer = digit, {digit};
*)
"""

table = {}
# ~ table['character'] = Word(printables, exact=1)
# ~ table['letter'] = Word(alphas + '_', exact=1)
# ~ table['digit'] = Word(nums, exact=1)
table["terminal_string"] = sglQuotedString
table["meta_identifier"] = Word(alphas + "_", alphas + "_" + nums)
table["integer"] = Word(nums)

parsers = ebnf.parse(grammar, table)
ebnf_parser = parsers["syntax"]

commentcharcount = 0
commentlocs = set()


def tallyCommentChars(t, l, s):
    global commentcharcount, commentlocs
    # only count this comment if we haven't seen it before
    if l not in commentlocs:
        charCount = len(t[0]) - len(list(filter(str.isspace, t[0])))
        commentcharcount += charCount
        commentlocs.add(l)
    return l, t


# ordinarily, these lines wouldn't be necessary, but we are doing extra stuff with the comment expression
ebnf.ebnfComment = ebnf.ebnfComment.add_parse_action(tallyCommentChars)
ebnf_parser.ignore(ebnf.ebnfComment)

parsed_chars = ebnf_parser.parse_string(grammar)
parsed_char_len = len(parsed_chars)


# ~ grammar_length = len(grammar) - len(filter(str.isspace, grammar))-commentcharcount

# ~ assert parsed_char_len == grammar_length

