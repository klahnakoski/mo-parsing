# encoding: utf-8
from contextlib import contextmanager
from copy import copy

DEFAULT_WHITE_CHARS = " \n\t\r"
CURRENT_WHITE_CHARS = copy(DEFAULT_WHITE_CHARS)


def setDefaultWhitespaceChars(chars):
    global CURRENT_WHITE_CHARS

    CURRENT_WHITE_CHARS = copy(chars)


@contextmanager
def default_whitespace(chars):
    """
    Overrides the default whitespace chars

    Example::

        # default whitespace chars are space, <TAB> and newline
        OneOrMore(Word(alphas)).parseString("abc def\nghi jkl")  # -> ['abc', 'def', 'ghi', 'jkl']

        # change to just treat newline as significant
        setDefaultWhitespaceChars(" \t")
        OneOrMore(Word(alphas)).parseString("abc def\nghi jkl")  # -> ['abc', 'def']
    """
    global CURRENT_WHITE_CHARS

    old_value = CURRENT_WHITE_CHARS
    setDefaultWhitespaceChars(chars)
    yield
    CURRENT_WHITE_CHARS = old_value
