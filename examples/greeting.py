# greeting.py
#
# Demonstration of the mo_parsing module, on the prototypical "Hello, World!"
# example
#
# Copyright 2003, 2019 by Paul McGuire
#
from mo_parsing import *

# define grammar
greet = Word(alphas) + "," + Word(alphas) + oneOf("! ? .")

# input string
hello = "Hello, World!"

# parse input string
print(hello, "->", greet.parseString(hello))

# parse a bunch of input strings
greet.runTests(
    """\
    Hello, World!
    Ahoy, Matey!
    Howdy, Pardner!
    Morning, Neighbor!
    """
)
