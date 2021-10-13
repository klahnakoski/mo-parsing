# encoding: utf-8
from time import time


start = time()
from mo_parsing import *
end = time()

print(f"import time = {str(round(end-start, 2))} seconds")

from mo_parsing.whitespaces import Whitespace

with Whitespace():
    Regex("[^\\]]")

