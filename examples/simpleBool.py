#
# simpleBool.py
#
# Example of defining a boolean logic parser using
# the operatorGrammar helper method in mo_parsing.
#
# In this example, parse actions associated with each
# operator expression will "compile" the expression
# into BoolXXX class instances, which can then
# later be evaluated for their boolean value.
#
# Copyright 2006, by Paul McGuire
# Updated 2013-Sep-14 - improved Python 2/3 cross-compatibility
#
from mo_parsing import infix_notation, RIGHT_ASSOC, LEFT_ASSOC
from mo_parsing.helpers import *


# define classes to be built at parse time, as each matching
# expression type is parsed
class BoolOperand:
    def __init__(self, t):
        self.label = t[0]
        self.value = eval(t[0])

    def __bool__(self):
        return self.value

    def __str__(self):
        return self.label

    __repr__ = __str__


class BoolBinOp:
    def __init__(self, t):
        self.args = t[0][0::2]

    def __str__(self):
        sep = " %s " % self.reprsymbol
        return "(" + sep.join(map(str, self.args)) + ")"

    def __bool__(self):
        return self.evalop(bool(a) for a in self.args)

    __nonzero__ = __bool__


class BoolAnd(BoolBinOp):
    reprsymbol = "&"
    evalop = all


class BoolOr(BoolBinOp):
    reprsymbol = "|"
    evalop = any


class BoolNot:
    def __init__(self, t):
        self.arg = t[0][1]

    def __bool__(self):
        v = bool(self.arg)
        return not v

    def __str__(self):
        return "~" + str(self.arg)

    __repr__ = __str__


TRUE = Keyword("True")
FALSE = Keyword("False")
boolOperand = TRUE | FALSE | Word(alphas, max=1)
boolOperand.add_parse_action(BoolOperand)

# define expression, based on expression operand and
# list of operations in precedence order
bool_expr = infix_notation(
    boolOperand,
    [
        ("not", 1, RIGHT_ASSOC, BoolNot),
        ("and", 2, LEFT_ASSOC, BoolAnd),
        ("or", 2, LEFT_ASSOC, BoolOr),
    ],
)


p = True
q = False
r = True
tests = [
    ("p", True),
    ("q", False),
    ("p and q", False),
    ("p and not q", True),
    ("not not p", True),
    ("not(p and q)", True),
    ("q or not p and r", False),
    ("q or not p or not r", False),
    ("q or not (p and r)", False),
    ("p or q or r", True),
    ("p or q or r and False", True),
    ("(p or q or r) and False", False),
]




for t, expected in tests:
    res = bool_expr.parse_string(t)[0]
    success = "PASS" if bool(res) == expected else "FAIL"

