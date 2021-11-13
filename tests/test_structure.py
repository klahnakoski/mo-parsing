# encoding: utf-8

from mo_parsing import Word, Group, Forward
from mo_parsing.infix import delimited_list
from mo_parsing.utils import alphas, nums
from tests.test_simple_unit import PyparsingExpressionTestCase

w = Word(alphas)


class TestStructure(PyparsingExpressionTestCase):
    def test_and(self):
        self.run_test(
            expr=Group((w + w)("name")),
            text="a b",
            expected_list=["a", "b"],
            expected_dict={"name": ["a", "b"]},
        )

    def test_or(self):
        self.run_test(
            expr=Group((w | w)("name")),
            text="c",
            expected_list=["c"],
            expected_dict={"name": "c"},
        )

        self.run_test(
            expr=Group(Group(w | w)("name")),
            text="c",
            expected_list=[["c"]],
            expected_dict={"name": ["c"]},
        )

    def test_group(self):
        self.run_test(
            expr=Group((w + w)("name")),
            text="a b",
            expected_list=["a", "b"],
            expected_dict={"name": ["a", "b"]},
        )

        self.run_test(
            expr=Group(Group(w + w)("name")),
            text="a b",
            expected_list=[["a", "b"]],
            expected_dict={"name": ["a", "b"]},
        )

        self.run_test(
            expr=Group(Group(Group(w + w))("name")),
            text="a b",
            expected_list=[[["a", "b"]]],
            expected_dict={"name": [["a", "b"]]},
        )

    def test_forward(self):
        self.run_test(
            expr=Group(Forward(w + w)("name")),
            text="a b",
            expected_list=["a", "b"],
            expected_dict={"name": ["a", "b"]},
        )

        self.run_test(
            expr=Group(Forward(w | w)("name")),
            text="c",
            expected_list=["c"],
            expected_dict={"name": "c"},
        )

        self.run_test(
            expr=Group(Forward(Forward(w | w))("name")),
            text="c",
            expected_list=["c"],
            expected_dict={"name": "c"},
        )

    def test_forward_actions(self):
        acc = []
        expr = Forward().add_parse_action(lambda: acc.append("forward"))
        A = w.add_parse_action(lambda: acc.append("A"))
        B = w.add_parse_action(lambda: acc.append("B"))

        expr << A | B

        E = expr.finalize()

        acc.clear()
        expr << A
        E.parse_string("x")
        self.assertEqual(acc, ["A", "forward"])

        acc.clear()
        expr << B
        E.parse_string("x")
        self.assertEqual(acc, ["B", "forward"])

    def test_forawrd_whitespace(self):
        c = Forward()
        c << (("(" + c + ")") | Group(Word(alphas) | Word(nums)))
        c = c.finalize()
        result = c.parse_string("(this)")
        self.assertEqual(result, ["(", ["this"], ")"])
