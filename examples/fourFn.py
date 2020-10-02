# fourFn.py
#
# Demonstration of the mo_parsing module, implementing a simple 4-function expression parser,
# with support for scientific notation, and symbols for e and pi.
# Extended to add exponentiation and simple built-in functions.
# Extended test cases, simplified pushFirst method.
# Removed unnecessary expr.suppress() call (thanks Nathaniel Peterson!), and added Group
# Changed fnumber to use a Regex, which is now the preferred method
# Reformatted to latest pypyparsing features, support multiple and variable args to functions
#
# Copyright 2003-2019 by Paul McGuire
#
import math
import operator

from mo_parsing import *

exprStack = []


def push_first(toks):
    exprStack.append(toks[0])


def push_unary_minus(toks):
    for t in toks:
        if t == "-":
            exprStack.append("unary -")
        else:
            break


"""
expop   :: '^'
multop  :: '*' | '/'
addop   :: '+' | '-'
integer :: ['+' | '-'] '0'..'9'+
atom    :: PI | E | real | fn '(' expr ')' | '(' expr ')'
factor  :: atom [ expop factor ]*
term    :: factor [ multop factor ]*
expr    :: term [ addop term ]*
"""

# use CaselessKeyword for e and pi, to avoid accidentally matching
# functions that start with 'e' or 'pi' (such as 'exp'); Keyword
# and CaselessKeyword only match whole words
e = CaselessKeyword("E")
pi = CaselessKeyword("PI")
# fnumber = Combine(Word("+-"+nums, nums) +
#                    Optional("." + Optional(Word(nums))) +
#                    Optional(e + Word("+-"+nums, nums)))
# or use provided number, but convert back to str:
# fnumber = number().addParseAction(lambda t: str(t[0]))
fnumber = Regex(r"[+-]?\d+(?:\.\d*)?(?:[eE][+-]?\d+)?")
ident = Word(alphas, alphanums + "_$")

plus, minus, mult, div = map(Literal, "+-*/")
lpar, rpar = map(Suppress, "()")
addop = plus | minus
multop = mult | div
expop = Literal("^")

expr = Forward()
expr_list = delimitedList(Group(expr))
# add parse action that replaces the function identifier with a (name, number of args) tuple
fn_call = (ident + lpar - Group(expr_list) + rpar).addParseAction(
    lambda t: ((t[0], t[1].length()),)
)
atom = (
    addop[...]
    + (
        (fn_call | pi | e | fnumber | ident).addParseAction(push_first)
        | Group(lpar + expr + rpar)
    )
).addParseAction(push_unary_minus)

# by defining exponentiation as "atom [ ^ factor ]..." instead of "atom [ ^ atom ]...", we get right-to-left
# exponents, instead of left-to-right that is, 2^3^2 = 2^(3^2), not (2^3)^2.
factor = Forward()
factor <<= atom + (expop + factor).addParseAction(push_first)[...]
term = factor + (multop + factor).addParseAction(push_first)[...]
expr <<= term + (addop + term).addParseAction(push_first)[...]
bnf = expr

# map operator symbols to corresponding arithmetic operations
epsilon = 1e-12
opn = {
    "+": operator.add,
    "-": operator.sub,
    "*": operator.mul,
    "/": operator.truediv,
    "^": operator.pow,
}

fn = {
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "exp": math.exp,
    "abs": abs,
    "trunc": lambda a: int(a),
    "round": round,
    "sgn": lambda a: -1 if a < -epsilon else 1 if a > epsilon else 0,
}


def evaluate_stack(s):
    op, num_args = s.pop(), 0
    if isinstance(op, tuple):
        op, num_args = op
    if op == "unary -":
        return -evaluate_stack(s)
    if op in opn:
        # note: operands are pushed onto the stack in reverse order
        op2 = evaluate_stack(s)
        op1 = evaluate_stack(s)
        return opn[op](op1, op2)
    elif op == "PI":
        return math.pi  # 3.1415926535
    elif op == "E":
        return math.e  # 2.718281828
    elif op in fn:
        # note: args are pushed onto the stack in reverse order
        args = tuple(reversed([evaluate_stack(s) for _ in range(num_args)]))
        return fn[op](*args)
    elif op[0].isalpha():
        raise Exception("invalid identifier '%s'" % op)
    else:
        # try to evaluate as int first, then as float if int fails
        try:
            return int(op)
        except ValueError:
            return float(op)
