# encoding: utf-8
# copied from test_unit.py
#
import operator

from mo_parsing import *
from mo_parsing.helpers import *
from mo_parsing.infix import one_of
from mo_parsing.utils import *
from tests.test_simple_unit import PyparsingExpressionTestCase


class TestParsing(PyparsingExpressionTestCase):
    def testInfixNotationGrammarTest1(self):

        integer = Word(nums) / (lambda t: int(t[0]))
        variable = Word(alphas, exact=1)
        operand = integer | variable

        expop = Literal("^")
        signop = one_of("+ -")
        multop = one_of("* /")
        plusop = one_of("+ -")
        factop = Literal("!")

        expr = infix_notation(
            operand,
            [
                (factop, 1, LEFT_ASSOC),
                (expop, 2, RIGHT_ASSOC),
                (signop, 1, RIGHT_ASSOC),
                (multop, 2, LEFT_ASSOC),
                (plusop, 2, LEFT_ASSOC),
            ],
        )

        test = [
            "(9 + 2) * 3",
            "9 + 2 * 3",
            "9 + 2 + 3",
            "(9 + -2) * 3",
            "(9 + --2) * 3",
            "(9 + -2) * 3^2^2",
            "(9! + -2) * 3^2^2",
            "M*X + B",
            "M*(X + B)",
            "1+2*-3^4*5+-+-6",
            "3!!",
        ]
        expected = [
            [[9, "+", 2], "*", 3],
            [9, "+", [2, "*", 3]],
            [[9, "+", 2], "+", 3],
            [[9, "+", ["-", 2]], "*", 3],
            [[9, "+", ["-", ["-", 2]]], "*", 3],
            [[9, "+", ["-", 2]], "*", [3, "^", [2, "^", 2]]],
            [[[9, "!"], "+", ["-", 2]], "*", [3, "^", [2, "^", 2]]],
            [["M", "*", "X"], "+", "B"],
            ["M", "*", ["X", "+", "B"]],
            [
                [1, "+", [[2, "*", ["-", [3, "^", 4]]], "*", 5]],
                "+",
                ["-", ["+", ["-", 6]]],
            ],
            [[3, "!"], "!"],
        ]
        for test_str, exp_list in zip(test, expected):
            result = expr.parse_string(test_str)

            self.assertParseResultsEquals(
                result,
                expected_list=exp_list,
                msg="mismatched results for infixNotation: got %s, expected %s"
                % (result, exp_list),
            )

    def testInfixNotationGrammarTest2(self):

        boolVars = {"True": True, "False": False}

        class BoolOperand:
            reprsymbol = ""

            def __init__(self, t):
                self.args = t[0][0], t[2][0]

            def __str__(self):
                sep = " %s " % self.reprsymbol
                return "(" + sep.join(map(str, self.args)) + ")"

        class BoolAnd(BoolOperand):
            reprsymbol = "&"

            def __bool__(self):
                for a in self.args:
                    if isinstance(a, str):
                        v = boolVars[a]
                    else:
                        v = bool(a)
                    if not v:
                        return False
                return True

        class BoolOr(BoolOperand):
            reprsymbol = "|"

            def __bool__(self):
                for a in self.args:
                    if isinstance(a, str):
                        v = boolVars[a]
                    else:
                        v = bool(a)
                    if v:
                        return True
                return False

        class BoolNot(BoolOperand):
            def __init__(self, t):
                self.arg = t[1][0]

            def __str__(self):
                return "~" + str(self.arg)

            def __bool__(self):
                if isinstance(self.arg, str):
                    v = boolVars[self.arg]
                else:
                    v = bool(self.arg)
                return not v

        boolOperand = Group(one_of("True False") | Word(alphas, max=1))
        bool_expr = infix_notation(
            boolOperand,
            [
                ("not", 1, RIGHT_ASSOC, BoolNot),
                ("and", 2, LEFT_ASSOC, BoolAnd),
                ("or", 2, LEFT_ASSOC, BoolOr),
            ],
        )
        test = [
            "not not p",
            "True and False",
            "p and not q",
            "not(p and q)",
            "q or not p and r",
            "q or not p or not r",
            "q or not (p and r)",
            "p or q or r",
            "p or q or r and False",
            "(p or q or r) and False",
        ]

        boolVars["p"] = True
        boolVars["q"] = False
        boolVars["r"] = True

        for t in test:
            res = bool_expr.parse_string(t)
            value = bool(res[0])
            expected = eval(t, {}, boolVars)
            self.assertEqual(expected, value)

    def testInfixNotationGrammarTest3(self):

        global count
        count = 0

        def evaluate_int(t):
            global count
            value = int(t[0])

            count += 1
            return value

        integer = Word(nums).add_parse_action(evaluate_int)
        variable = Word(alphas, exact=1)
        operand = integer | variable

        expop = Literal("^")
        signop = one_of("+ -")
        multop = one_of("* /")
        plusop = one_of("+ -")
        factop = Literal("!")

        expr = infix_notation(
            operand,
            [
                ("!", 1, LEFT_ASSOC),
                ("^", 2, LEFT_ASSOC),
                (signop, 1, RIGHT_ASSOC),
                (multop, 2, LEFT_ASSOC),
                (plusop, 2, LEFT_ASSOC),
            ],
        )

        test = ["9"]
        for t in test:
            count = 0
            expr.parse_string(t)
            self.assertEqual(count, 1, "count evaluated too many times!")

    def testInfixNotationGrammarTest4(self):

        word = Word(alphas)

        def supLiteral(s):
            """Returns the suppressed literal s"""
            return Literal(s).suppress()

        f = infix_notation(
            word,
            [
                (supLiteral("!"), 1, RIGHT_ASSOC, lambda t, l, s: ["!", t[0]]),
                (one_of("= !="), 2, LEFT_ASSOC,),
                (supLiteral("&"), 2, LEFT_ASSOC, lambda t, l, s: ["&", t]),
                (supLiteral("|"), 2, LEFT_ASSOC, lambda t, l, s: ["|", t]),
            ],
        )

        f = f + StringEnd()

        tests = [
            ("bar = foo", [["bar", "=", "foo"]]),
            (
                "bar = foo & baz = fee",
                [["&", [["bar", "=", "foo"], ["baz", "=", "fee"]]]],
            ),
        ]
        for test, expected in tests:
            results = f.parse_string(test)
            self.assertParseResultsEquals(results, expected_list=expected)

    def testInfixNotationGrammarTest5(self):
        expop = Literal("**")
        signop = one_of("+ -")
        multop = one_of("* /")
        plusop = one_of("+ -")

        class ExprNode:
            def __init__(self, tokens):
                self.tokens = tokens

            def eval(self):
                return None

        class NumberNode(ExprNode):
            def eval(self):
                return self.tokens[0]

        class SignOp(ExprNode):
            def eval(self):
                mult = {"+": 1, "-": -1}[self.tokens[0]]
                return mult * self.tokens[1].eval()

        class BinOp(ExprNode):
            def eval(self):
                ret = self.tokens[0][0].eval()
                for op, operand in zip(self.tokens[1::2], self.tokens[2::2]):
                    ret = self.opn_map[op](ret, operand[0].eval())
                return ret

        class ExpOp(BinOp):
            opn_map = {"**": lambda a, b: b ** a}

        class MultOp(BinOp):
            opn_map = {"*": operator.mul, "/": operator.truediv}

        class AddOp(BinOp):
            opn_map = {"+": operator.add, "-": operator.sub}

        operand = Group(number).add_parse_action(NumberNode)
        expr = infix_notation(
            operand,
            [
                (expop, 2, RIGHT_ASSOC, (lambda pr: pr[::-1], ExpOp)),
                (signop, 1, RIGHT_ASSOC, SignOp),
                (multop, 2, LEFT_ASSOC, MultOp),
                (plusop, 2, LEFT_ASSOC, AddOp),
            ],
        )

        tests = [
            "2+7",
            "2**3",
            "2**3**2",
            "3**9",
            "3**3**2",
        ]

        for t in tests:
            t = t.strip()
            if not t:
                continue

            parsed = expr.parse_string(t)
            eval_value = parsed[0].eval()
            self.assertEqual(
                eval_value,
                eval(t),
                "Error evaluating {!r}, expected {!r}, got {!r}".format(
                    t, eval(t), eval_value
                ),
            )

    def testChainedTernaryOperator(self):

        TERNARY_INFIX = infix_notation(integer, [(("?", ":"), 3, LEFT_ASSOC),])
        self.assertParseResultsEquals(
            TERNARY_INFIX.parse_string("1?1:0?1:0", parse_all=True),
            expected_list=[[1, "?", 1, ":", 0], "?", 1, ":", 0],
        )

        TERNARY_INFIX = infix_notation(integer, [(("?", ":"), 3, RIGHT_ASSOC),])
        self.assertParseResultsEquals(
            TERNARY_INFIX.parse_string("1?1:0?1:0", parse_all=True),
            expected_list=[1, "?", 1, ":", [0, "?", 1, ":", 0]],
        )

    def test_default_operator(self):
        def parser(tokens):
            left, op, right = tokens
            return {str(op): [left, right]}

        def mul(tokens):
            left, right = tokens
            return {"*": [left, right]}

        word = Word(alphas)

        expr = infix_notation(
            word,
            [
                (None, 2, LEFT_ASSOC, mul),
                (Literal("*") | "/", 2, LEFT_ASSOC, parser),
                ("+", 2, LEFT_ASSOC, parser),
            ],
        )

        result = expr.parse_string("a b + c")
        self.assertEqual(result, [{"+": [[{"*": ["a", "b"]}], "c"]}])

        result = expr.parse_string("a * b c")
        self.assertEqual(result, [{"*": ["a", [{"*": ["b", "c"]}]]}])

        result = expr.parse_string("a b c")
        self.assertEqual(result, [{"*": [[{"*": ["a", "b"]}], "c"]}])

        result = expr.parse_string("a / b c")
        self.assertEqual(result, [{"/": ["a", [{"*": ["b", "c"]}]]}])
