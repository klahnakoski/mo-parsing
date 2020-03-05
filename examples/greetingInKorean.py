#
# greetingInKorean.py
#
# Demonstration of the parsing module, on the prototypical "Hello, World!" example
#
# Copyright 2004-2016, by Paul McGuire
#
from mo_parsing import Word, parsing_unicode as ppu, parsing_unicode

koreanChars = parsing_unicode.Korean.alphas
koreanWord = Word(koreanChars, min=2)

# define grammar
greet = koreanWord + "," + koreanWord + "!"

# input string
hello = "안녕, 여러분!"  # "Hello, World!" in Korean

# parse input string

