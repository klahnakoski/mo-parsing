#
# test_examples.py
#
import unittest
from importlib import import_module

from mo_files import File

from mo_parsing.engine import Engine

modules = [f.name for f in File("examples").children]


@unittest.skip("not running examples right now")
class TestAllExamples(unittest.TestCase):
    pass


def _single_test(name):
    def output(self):
        with Engine():
            import_module("examples." + name)

    return output


for f in File("examples").children:
    if f.extension == "py":
        setattr(TestAllExamples, "test_" + f.name, _single_test(f.name))
