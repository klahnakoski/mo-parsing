#
# rosettacode.py
#
# parser for language used by rosettacode.org (http://rosettacode.org/wiki/Compiler/syntax_analyzer)
#
# Copyright Paul McGuire, 2019
#
from mo_parsing import whitespaces
from mo_parsing.helpers import QuotedString, integer, identifier, cppStyleComment
from mo_parsing.infix import one_of, delimited_list

BNF = """
    stmt_list           =   {stmt} ;

    stmt                =   ';'
                          | Identifier '=' expr ';'
                          | 'while' paren_expr stmt
                          | 'if' paren_expr stmt ['else' stmt]
                          | 'print' '(' prt_list ')' ';'
                          | 'putc' paren_expr ';'
                          | '{' stmt_list '}'
                          ;

    paren_expr          =   '(' expr ')' ;

    prt_list            =   string | expr {',' String | expr} ;

    expr                =   and_expr            {'||' and_expr} ;
    and_expr            =   equality_expr       {'&&' equality_expr} ;
    equality_expr       =   relational_expr     [('==' | '!=') relational_expr] ;
    relational_expr     =   addition_expr       [('<' | '<=' | '>' | '>=') addition_expr] ;
    addition_expr       =   multiplication_expr {('+' | '-') multiplication_expr} ;
    multiplication_expr =   primary             {('*' | '/' | '%') primary } ;
    primary             =   Identifier
                          | Integer
                          | '(' expr ')'
                          | ('+' | '-' | '!') primary
                          ;
"""

from mo_parsing import *


whitespaces.CURRENT.add_ignore(cppStyleComment)

LBRACE, RBRACE, LPAR, RPAR, SEMI = map(Suppress, "{}();")
EQ = Literal("=")

keywords = (WHILE, IF, PRINT, PUTC, ELSE) = map(
    Keyword, "while if print putc else".split()
)
any_keyword = MatchFirst(keywords)
identifier = ~any_keyword + identifier
string = QuotedString('"', convert_whitespace_escape=False).set_parser_name("quoted string")
char = Regex(r"'\\?.'")

expr = infix_notation(
    identifier | integer | char,
    [
        (one_of("+ - !"), 1, RIGHT_ASSOC,),
        (one_of("* / %"), 2, LEFT_ASSOC,),
        (one_of("+ -"), 2, LEFT_ASSOC,),
        (one_of("< <= > >="), 2, LEFT_ASSOC,),
        (one_of("== !="), 2, LEFT_ASSOC,),
        (one_of("&&"), 2, LEFT_ASSOC,),
        (one_of("||"), 2, LEFT_ASSOC,),
    ],
)

prt_list = Group(delimited_list(string | expr))
paren_expr = Group(LPAR + expr + RPAR)

stmt = Forward()
assignment_stmt = Group(identifier + EQ + expr + SEMI)
while_stmt = Group(WHILE - paren_expr + stmt)
if_stmt = Group(IF - paren_expr + stmt + Optional(ELSE + stmt))
print_stmt = Group(PRINT - Group(LPAR + prt_list + RPAR) + SEMI)
putc_stmt = Group(PUTC - paren_expr + SEMI)
stmt_list = Group(LBRACE + stmt[...] + RBRACE)
stmt <<= (
    Group(SEMI)
    | assignment_stmt
    | while_stmt
    | if_stmt
    | print_stmt
    | putc_stmt
    | stmt_list
).set_parser_name("statement")

code = stmt[...]


tests = [
    r"""
        count = 1;
        while (count < 10) {
            print("count is: ", count, "\n");
            count = count + 1;
        }
    """,
    r"""
        /*
         Simple prime number generator
         */
        count = 1;
        n = 1;
        limit = 100;
        while (n < limit) {
            k=3;
            p=1;
            n=n+2;
            while ((k*k<=n) && (p)) {
                p=n/k*k!=n;
                k=k+2;
            }
            if (p) {
                print(n, " is prime\n");
                count = count + 1;
            }
        }
        print("Total primes found: ", count, "\n");
    """,
    r"""
        /*
          Hello world
         */
        print("Hello, World!\n");
    """,
    r"""
        /*
          Show Ident and Integers
         */
        phoenix_number = 142857;
        print(phoenix_number, "\n");
    """,
    r"""
        /*** test printing, embedded \n and comments with lots of '*' ***/
        print(42);
        print("\nHello World\nGood Bye\nok\n");
        print("Print a slash n - \\n.\n");
    """,
    r"""
        /* 100 Doors */
        i = 1;
        while (i * i <= 100) {
            print("door ", i * i, " is open\n");
            i = i + 1;
        }
    """,
    r"""
        a = (-1 * ((-1 * (5 * 15)) / 10));
        print(a, "\n");
        b = -a;
        print(b, "\n");
        print(-b, "\n");
        print(-(1), "\n");
    """,
    r"""
        print(---------------------------------+++5, "\n");
        print(((((((((3 + 2) * ((((((2))))))))))))), "\n");

        if (1) { if (1) { if (1) { if (1) { if (1) { print(15, "\n"); } } } } }
    """,
    r"""
        /* Compute the gcd of 1071, 1029:  21 */

        a = 1071;
        b = 1029;

        while (b != 0) {
            new_a = b;
            b     = a % b;
            a     = new_a;
        }
        print(a);
    """,
    r"""
        /* 12 factorial is 479001600 */

        n = 12;
        result = 1;
        i = 1;
        while (i <= n) {
            result = result * i;
            i = i + 1;
        }
        print(result);
    """,
    r"""
        /* fibonacci of 44 is 701408733 */

        n = 44;
        i = 1;
        a = 0;
        b = 1;
        while (i < n) {
            w = a + b;
            a = b;
            b = w;
            i = i + 1;
        }
        print(w, "\n");
    """,
    r"""
        /* FizzBuzz */
        i = 1;
        while (i <= 100) {
            if (!(i % 15))
                print("FizzBuzz");
            else if (!(i % 3))
                print("Fizz");
            else if (!(i % 5))
                print("Buzz");
            else
                print(i);

            print("\n");
            i = i + 1;
        }
    """,
    r"""
        /* 99 bottles */
        bottles = 99;
        while (bottles > 0) {
            print(bottles, " bottles of beer on the wall\n");
            print(bottles, " bottles of beer\n");
            print("Take one down, pass it around\n");
            bottles = bottles - 1;
            print(bottles, " bottles of beer on the wall\n\n");
        }
    """,
    r"""
         {
        /*
         This is an integer ascii Mandelbrot generator
         */
            left_edge   = -420;
            right_edge  =  300;
            top_edge    =  300;
            bottom_edge = -300;
            x_step      =    7;
            y_step      =   15;

            max_iter    =  200;

            y0 = top_edge;
            while (y0 > bottom_edge) {
                x0 = left_edge;
                while (x0 < right_edge) {
                    y = 0;
                    x = 0;
                    the_char = ' ';
                    i = 0;
                    while (i < max_iter) {
                        x_x = (x * x) / 200;
                        y_y = (y * y) / 200;
                        if (x_x + y_y > 800 ) {
                            the_char = '0' + i;
                            if (i > 9) {
                                the_char = '@';
                            }
                            i = max_iter;
                        }
                        y = x * y / 100 + y0;
                        x = x_x - y_y + x0;
                        i = i + 1;
                    }
                    putc(the_char);
                    x0 = x0 + x_step;
                }
                putc('\n');
                y0 = y0 - y_step;
            }
        }
    """,
]

for test in tests:
    results = code.parse_string(test)

