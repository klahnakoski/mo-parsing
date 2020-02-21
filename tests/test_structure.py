from unittest import TestCase

from mo_parsing import alphas, Word, Group, Forward
from tests.test_simple_unit import PyparsingExpressionTestCase

w = Word(alphas)


class TestStructure(PyparsingExpressionTestCase):
    def test_and(self):
        self.runTest(
            expr=(w + w)("name"),
            text="a b",
            expected_list=["a", "b"],
            expected_dict={"name": ["a", "b"]},
        )

    def test_or(self):
        self.runTest(
            expr=(w | w)("name"),
            text="c",
            expected_list=["c"],
            expected_dict={"name": "c"},
        )

        self.runTest(
            expr=Group(w | w)("name"),
            text="c",
            expected_list=[["c"]],
            expected_dict={"name": ["c"]},
        )

    def test_group(self):
        self.runTest(
            expr=(w + w)("name"),
            text="a b",
            expected_list=["a", "b"],
            expected_dict={"name": ["a", "b"]},
        )

        self.runTest(
            expr=Group(w + w)("name"),
            text="a b",
            expected_list=[["a", "b"]],
            expected_dict={"name": ["a", "b"]},
        )

        self.runTest(
            expr=Group(Group(w + w))("name"),
            text="a b",
            expected_list=[[["a", "b"]]],
            expected_dict={"name": [["a", "b"]]},
        )

    def test_forward(self):
        self.runTest(
            expr=Forward(w + w)("name"),
            text="a b",
            expected_list=["a", "b"],
            expected_dict={"name": ["a", "b"]},
        )

        self.runTest(
            expr=Forward(w | w)("name"),
            text="c",
            expected_list=["c"],
            expected_dict={"name": "c"},
        )

        self.runTest(
            expr=Forward(Forward(w | w))("name"),
            text="c",
            expected_list=["c"],
            expected_dict={"name": "c"},
        )
