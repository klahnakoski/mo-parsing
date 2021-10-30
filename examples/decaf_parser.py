#
# decaf_parser.py
#
# Rudimentary parser for decaf language, used in Stanford University CS143
# (https://web.stanford.edu/class/archive/cs/cs143/cs143.1128/handouts/030%20Decaf%20Specification.pdf)
#
# To convert this parser into one that gives more of an AST, change all the Group wrappers to add parse
# actions that will result in ASTNode classes, or statement-specific subclasses.
#
# Copyright 2018, Paul McGuire
#
"""
    Program ::= Decl+
    Decl ::= VariableDecl | FunctionDecl  | ClassDecl | InterfaceDecl
    VariableDecl ::= Variable ;
    Variable ::= Type ident
    Type ::= int | double | bool | string | ident | Type []
    FunctionDecl ::= Type ident ( Formals ) StmtBlock | void ident ( Formals ) StmtBlock
    Formals ::= Variable+, |  e
    ClassDecl ::= class ident <extends ident>  <implements ident + ,>  { Field* }
    Field ::= VariableDecl | FunctionDecl
    InterfaceDecl ::= interface ident { Prototype* }
    Prototype ::= Type ident ( Formals ) ; | void ident ( Formals ) ;
    StmtBlock ::= { VariableDecl*  Stmt* }
    Stmt ::=  <Expr> ; | IfStmt  | WhileStmt |  ForStmt | BreakStmt   | ReturnStmt  | PrintStmt  | StmtBlock
    IfStmt ::= if ( Expr ) Stmt <else Stmt>
    WhileStmt ::= while ( Expr ) Stmt
    ForStmt ::= for ( <Expr> ; Expr ; <Expr> ) Stmt
    ReturnStmt ::= return <Expr> ;
    BreakStmt ::= break ;
    PrintStmt ::= Print ( Expr+, ) ;
    Expr ::= LValue = Expr | Constant | LValue | this | Call
            | ( Expr )
            | Expr + Expr | Expr - Expr | Expr * Expr | Expr / Expr |  Expr % Expr | - Expr
            | Expr < Expr | Expr <= Expr | Expr > Expr | Expr >= Expr | Expr == Expr | Expr != Expr
            | Expr && Expr | Expr || Expr | ! Expr
            | ReadInteger ( ) | ReadLine ( ) | new ident | NewArray ( Expr , Typev)
    LValue ::= ident |  Expr  . ident | Expr [ Expr ]
    Call ::= ident  ( Actuals ) |  Expr  .  ident  ( Actuals )
    Actuals ::=  Expr+, | e
    Constant ::= intConstant | doubleConstant | boolConstant |  stringConstant | null
"""
from mo_parsing import *
from mo_parsing import (
    Keyword,
    MatchFirst,
    Suppress,
    Regex,
    alphas,
    alphanums,
    Group,
    ZeroOrMore,
    Forward,
    Optional,
    OneOrMore,
)

# keywords
from mo_parsing.helpers import (
    integer,
    real,
    dblQuotedString,
    delimited_list,
    infixNotation,
    one_of,
    opAssoc,
)

keywords = (
    VOID,
    INT,
    DOUBLE,
    BOOL,
    STRING,
    CLASS,
    INTERFACE,
    NULL,
    THIS,
    EXTENDS,
    IMPLEMENTS,
    FOR,
    WHILE,
    IF,
    ELSE,
    RETURN,
    BREAK,
    NEW,
    NEWARRAY,
    PRINT,
    READINTEGER,
    READLINE,
    TRUE,
    FALSE,
) = map(
    Keyword,
    """void int double bool string class interface null this extends implements or while
               if else return break new NewArray Print ReadInteger ReadLine true false""".split(),
)
keywords = MatchFirst(list(keywords))

LPAR, RPAR, LBRACE, RBRACE, LBRACK, RBRACK, DOT, EQ, COMMA, SEMI = map(
    Suppress, "(){}[].=,;"
)
hexConstant = Regex(r"0[xX][0-9a-fA-F]+").add_parse_action(lambda t: int(t[0][2:], 16))
intConstant = hexConstant | integer
doubleConstant = real
boolConstant = TRUE | FALSE
stringConstant = dblQuotedString
null = NULL
constant = doubleConstant | boolConstant | intConstant | stringConstant | null
ident = ~keywords + Word(alphas, alphanums + "_")
type_ = Group((INT | DOUBLE | BOOL | STRING | ident) + ZeroOrMore("[]"))

variable = type_ + ident
variable_decl = variable + SEMI

expr = Forward()
expr_parens = Group(LPAR + expr + RPAR)
actuals = Optional(delimited_list(expr))
call = Group(
    ident("call_ident") + LPAR + actuals("call_args") + RPAR
    | (expr_parens + ZeroOrMore(DOT + ident))("call_ident_expr")
    + LPAR
    + actuals("call_args")
    + RPAR
)
lvalue = (
    (ident | expr_parens)
    + ZeroOrMore(DOT + (ident | expr_parens))
    + ZeroOrMore(LBRACK + expr + RBRACK)
)
assignment = Group(lvalue("lhs") + EQ + expr("rhs"))
read_integer = Group(READINTEGER + LPAR + RPAR)
read_line = Group(READLINE + LPAR + RPAR)
new_statement = Group(NEW + ident)
new_array = Group(NEWARRAY + LPAR + expr + COMMA + type_ + RPAR)
rvalue = constant | call | read_integer | read_line | new_statement | new_array | ident
arith_expr = infixNotation(
    rvalue,
    [
        ("-", 1, RIGHT_ASSOC,),
        (one_of("* / %"), 2, LEFT_ASSOC,),
        (one_of("+ -"), 2, LEFT_ASSOC,),
    ],
)
comparison_expr = infixNotation(
    arith_expr,
    [
        ("!", 1, RIGHT_ASSOC,),
        (one_of("< > <= >="), 2, LEFT_ASSOC,),
        (one_of("== !="), 2, LEFT_ASSOC,),
        (one_of("&&"), 2, LEFT_ASSOC,),
        (one_of("||"), 2, LEFT_ASSOC,),
    ],
)
expr <<= (
    assignment
    | call
    | THIS
    | comparison_expr
    | arith_expr
    | lvalue
    | constant
    | read_integer
    | read_line
    | new_statement
    | new_array
)

stmt = Forward()
print_stmt = Group(
    PRINT("statement")
    + LPAR
    + Group(Optional(delimited_list(expr)))("args")
    + RPAR
    + SEMI
)
break_stmt = Group(BREAK("statement") + SEMI)
return_stmt = Group(RETURN("statement") + expr + SEMI)
for_stmt = Group(
    FOR("statement")
    + LPAR
    + Optional(expr)
    + SEMI
    + expr
    + SEMI
    + Optional(expr)
    + RPAR
    + stmt
)
while_stmt = Group(WHILE("statement") + LPAR + expr + RPAR + stmt)
if_stmt = Group(
    IF("statement")
    + LPAR
    + Group(expr)("condition")
    + RPAR
    + Group(stmt)("then_statement")
    + Group(Optional(ELSE + stmt))("else_statement")
)
stmt_block = Group(LBRACE + ZeroOrMore(variable_decl) + ZeroOrMore(stmt) + RBRACE)
stmt <<= (
    if_stmt
    | while_stmt
    | for_stmt
    | break_stmt
    | return_stmt
    | print_stmt
    | stmt_block
    | Group(expr + SEMI)
)

formals = Optional(delimited_list(variable))
prototype = Group(
    (type_ | VOID)("return_type")
    + ident("function_name")
    + LPAR
    + formals("args")
    + RPAR
    + SEMI
)("prototype")
function_decl = Group(
    (type_ | VOID)("return_type")
    + ident("function_name")
    + LPAR
    + formals("args")
    + RPAR
    + stmt_block("body")
)("function_decl")

interface_decl = Group(
    INTERFACE
    + ident("interface_name")
    + LBRACE
    + ZeroOrMore(prototype)("prototypes")
    + RBRACE
)("interface")
field = variable_decl | function_decl
class_decl = Group(
    CLASS
    + ident("class_name")
    + Optional(EXTENDS + ident)("extends")
    + Optional(IMPLEMENTS + delimited_list(ident))("implements")
    + LBRACE
    + ZeroOrMore(field)("fields")
    + RBRACE
)("class_decl")

decl = variable_decl | function_decl | class_decl | interface_decl | prototype
program = OneOrMore(Group(decl))
decaf_parser = program

stmt.run_tests(
    """\
    sin(30);
    a = 1;
    b = 1 + 1;
    b = 1 != 2 && false;
    print("A");
    a.b = 100;
    a.b = 100.0;
    a[100] = b;
    a[0][0] = 2;
    a = 0x1234;
"""
)

test_program = """
    void getenv(string var);
    int main(string[] args) {
        if (a > 100) {
            Print(a, " is too big");
        } else if (a < 100) {
            Print(a, " is too small");
        } else {
            Print(a, "just right!");
        }
    }
"""

