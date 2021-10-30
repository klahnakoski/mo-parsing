#
# idlparse.py
#
# an example of using the parsing module to be able to process a subset of the CORBA IDL grammar
#
# Copyright (c) 2003, Paul McGuire
#

from mo_parsing import (
    Literal,
    Word,
    OneOrMore,
    ZeroOrMore,
    Forward,
    Group,
    Optional,
    Keyword,
    Regex,
)
from mo_parsing.whitespaces import Whitespace
from mo_parsing.helpers import restOfLine, cStyleComment, delimited_list, quoted_string
from mo_parsing.utils import alphas, alphanums

bnf = None


def CORBA_IDL_BNF():
    global bnf

    if not bnf:
        with Whitespace() as e:
            singleLineComment = "//" + restOfLine
            e.add_ignore(singleLineComment)
            e.add_ignore(cStyleComment)

            # punctuation
            (
                colon,
                lbrace,
                rbrace,
                lbrack,
                rbrack,
                lparen,
                rparen,
                equals,
                comma,
                dot,
                slash,
                bslash,
                star,
                semi,
                langle,
                rangle,
            ) = map(Literal, r":{}[]()=,./\*;<>")

            # keywords
            (
                any_,
                attribute_,
                boolean_,
                case_,
                char_,
                const_,
                context_,
                default_,
                double_,
                enum_,
                exception_,
                FALSE_,
                fixed_,
                float_,
                inout_,
                interface_,
                in_,
                long_,
                module_,
                Object_,
                octet_,
                oneway_,
                out_,
                raises_,
                readonly_,
                sequence_,
                short_,
                string_,
                struct_,
                switch_,
                TRUE_,
                typedef_,
                unsigned_,
                union_,
                void_,
                wchar_,
                wstring_,
            ) = map(
                Keyword,
                """any attribute boolean case char const context
                default double enum exception FALSE fixed float inout interface in long module
                Object octet oneway out raises readonly sequence short string struct switch
                TRUE typedef unsigned union void wchar wstring""".split(),
            )

            identifier = Word(alphas, alphanums + "_").set_parser_name("identifier")

            real = Regex(r"[+-]?\d+\.\d*([Ee][+-]?\d+)?").set_parser_name("real")
            integer = Regex(r"0x[0-9a-fA-F]+|[+-]?\d+").set_parser_name("int")

            udTypeName = delimited_list(identifier, "::", combine=True).set_parser_name("udType")
            typeName = (
                any_
                | boolean_
                | char_
                | double_
                | fixed_
                | float_
                | long_
                | octet_
                | short_
                | string_
                | wchar_
                | wstring_
                | udTypeName
            ).set_parser_name("type")
            sequenceDef = Forward().set_parser_name("seq")
            sequenceDef << Group(sequence_ + langle + (sequenceDef | typeName) + rangle)
            typeDef = sequenceDef | (typeName + Optional(lbrack + integer + rbrack))
            typedefDef = Group(typedef_ + typeDef + identifier + semi).set_parser_name("typedef")

            moduleDef = Forward()
            constDef = Group(
                const_
                + typeDef
                + identifier
                + equals
                + (real | integer | quoted_string)
                + semi
            )  # | quoted_string )
            exceptionItem = Group(typeDef + identifier + semi)
            exceptionDef = (
                exception_ + identifier + lbrace + ZeroOrMore(exceptionItem) + rbrace + semi
            )
            attributeDef = Optional(readonly_) + attribute_ + typeDef + identifier + semi
            paramlist = delimited_list(
                Group((inout_ | in_ | out_) + typeName + identifier)
            ).set_parser_name("paramlist")
            operationDef = (
                (void_ ^ typeDef)
                + identifier
                + lparen
                + Optional(paramlist)
                + rparen
                + Optional(raises_ + lparen + Group(delimited_list(typeName)) + rparen)
                + semi
            )
            interfaceItem = constDef | exceptionDef | attributeDef | operationDef
            interfaceDef = Group(
                interface_
                + identifier
                + Optional(colon + delimited_list(typeName))
                + lbrace
                + ZeroOrMore(interfaceItem)
                + rbrace
                + semi
            ).set_parser_name("opnDef")
            moduleItem = interfaceDef | exceptionDef | constDef | typedefDef | moduleDef
            moduleDef << module_ + identifier + lbrace + ZeroOrMore(
                moduleItem
            ) + rbrace + semi

            bnf = moduleDef | OneOrMore(moduleItem)


    return bnf
