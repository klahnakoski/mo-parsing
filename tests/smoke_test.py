# encoding: utf-8
from time import time

from mo_dots import NullType

from mo_parsing import Log

start = time()
from mo_parsing import *

end = time()

print(f"import time = {str(round(end-start, 2))} seconds")

from mo_parsing.whitespaces import Whitespace

with Whitespace():
    Regex("[^\\]]")


integer = Word("0123456789") / (lambda t: int(t[0]))
result = integer.parse_string("42")
assert result[0] == 42

try:
    Log.error("this is a problem")
except ParseException as cause:
    assert isinstance(cause.expr, NullType)
