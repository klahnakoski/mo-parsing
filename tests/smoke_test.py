# encoding: utf-8
from time import time

start = time()
from mo_parsing import *
end = time()

print(f"import time = {str(round(end-start, 2))} seconds")

from mo_parsing.whitespaces import Whitespace

with Whitespace():
    Regex("[^\\]]")


integer = Word("0123456789") / (lambda t: int(t[0]))
result = integer.parseString("42")
assert (result[0] == 42)
