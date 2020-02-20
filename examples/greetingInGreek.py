#
# greetingInGreek.py
#
# Demonstration of the parsing module, on the prototypical "Hello, World!" example
#
# Copyright 2004-2016, by Paul McGuire
#
from mo_parsing import Word, mo_parsing_unicode as ppu

# define grammar
alphas = ppu.Greek.alphas
greet = Word(alphas) + "," + Word(alphas) + "!"

# input string
hello = "Καλημέρα, κόσμε!"

# parse input string
print(greet.parseString(hello))
