# greeting.py
#
# Demonstration of the mo_parsing module, on the prototypical "Hello, World!"
# example
#
# Copyright 2003, 2019 by Paul McGuire
#
from mo_parsing.helpers import *
from mo_parsing.infix import one_of
from mo_parsing.utils import *

greet = Word(alphas) + "," + Word(alphas) + one_of("! ? .")

# input string
hello = "Hello, World!"

# parse input string


# parse a bunch of input strings
greet.run_tests(
    """\
    Hello, World!
    Ahoy, Matey!
    Howdy, Pardner!
    Morning, Neighbor!
    """
)
