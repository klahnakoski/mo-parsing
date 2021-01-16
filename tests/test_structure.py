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
