# encoding: utf-8

from mo_parsing import Word, Group, Forward
from mo_parsing.utils import alphas
from tests.test_simple_unit import PyparsingExpressionTestCase

w = Word(alphas)


class TestStructure(PyparsingExpressionTestCase):
    def test_and(self):
        self.runTest(
            expr=Group((w + w)("name")),
            text="a b",
            expected_list=["a", "b"],
            expected_dict={"name": ["a", "b"]},
        )

    def test_or(self):
        self.runTest(
            expr=Group((w | w)("name")),
            text="c",
            expected_list=["c"],
            expected_dict={"name": "c"},
        )

        self.runTest(
            expr=Group(Group(w | w)("name")),
            text="c",
            expected_list=[["c"]],
            expected_dict={"name": ["c"]},
        )

    def test_group(self):
        self.runTest(
            expr=Group((w + w)("name")),
            text="a b",
            expected_list=["a", "b"],
            expected_dict={"name": ["a", "b"]},
        )

        self.runTest(
            expr=Group(Group(w + w)("name")),
            text="a b",
            expected_list=[["a", "b"]],
            expected_dict={"name": ["a", "b"]},
        )

        self.runTest(
            expr=Group(Group(Group(w + w))("name")),
            text="a b",
            expected_list=[[["a", "b"]]],
            expected_dict={"name": [["a", "b"]]},
        )

    def test_forward(self):
        self.runTest(
            expr=Group(Forward(w + w)("name")),
            text="a b",
            expected_list=["a", "b"],
            expected_dict={"name": ["a", "b"]},
        )

        self.runTest(
            expr=Group(Forward(w | w)("name")),
            text="c",
            expected_list=["c"],
            expected_dict={"name": "c"},
        )

        self.runTest(
            expr=Group(Forward(Forward(w | w))("name")),
            text="c",
            expected_list=["c"],
            expected_dict={"name": "c"},
        )


    def test_forward_actions(self):
        acc = []
        expr = Forward().addParseAction(lambda: acc.append("forward"))
        A = w.addParseAction(lambda: acc.append("A"))
        B = w.addParseAction(lambda: acc.append("B"))

        expr << A | B

        E = expr.finalize()

        acc.clear()
        expr << A
        E.parseString("x")
        self.assertEqual(acc, ["A", "forward"])

        acc.clear()
        expr << B
        E.parseString("x")
        self.assertEqual(acc, ["B", "forward"])

