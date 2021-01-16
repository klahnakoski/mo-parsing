#
# greetingInGreek.py
#
# Demonstration of the parsing module, on the prototypical "Hello, World!" example
#
# Copyright 2004-2016, by Paul McGuire
#
from mo_parsing.helpers import *
from mo_parsing.utils import parsing_unicode

# define grammar
alphas = parsing_unicode.Greek.alphas
greet = Word(alphas) + "," + Word(alphas) + "!"

# input string
hello = "Καλημέρα, κόσμε!"

# parse input string

