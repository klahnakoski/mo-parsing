# encoding: utf-8
from mo_parsing import Regex
from mo_parsing.engine import Engine

with Engine():
    Regex("[^\\]]")