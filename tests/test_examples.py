#
# test_examples.py
#
import unittest
from importlib import import_module

from mo_files import File

from mo_parsing.testing import reset_parsing_context

modules = [f.name for f in File("examples").children]


@unittest.skip
class TestAllExamples(unittest.TestCase):
    pass


def _single_test(name):
    def output(self):
        with reset_parsing_context():
            import_module("examples." + name)

    return output


for f in File("examples").children:
    if f.extension == "py":
        setattr(TestAllExamples, "test_" + f.name, _single_test(f.name))

