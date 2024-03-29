# parse_actions.py
#
#   A sample program a parser to match a date string of the form "YYYY/MM/DD",
# and return it as a datetime, or raise an exception if not a valid date.
#
# Copyright 2012, Paul T. McGuire
#
from datetime import datetime

# define an integer string, and a parse action to convert it
# to an integer at parse time
from mo_parsing import Word, nums, pythonStyleComment, ParseException
from mo_parsing.helpers import iso8601_date, convertToDate

integer = Word(nums).set_parser_name("integer")


def convertToInt(tokens):
    # no need to test for validity - we can't get here
    # unless tokens[0] contains all numeric digits
    return int(tokens[0])


integer.add_parse_action(convertToInt)
# or can be written as one line as
# integer = Word(nums).add_parse_action(lambda t: int(t[0]))

# define a pattern for a year/month/day date
date_expr = integer("year") + "/" + integer("month") + "/" + integer("day")
date_expr.ignore(pythonStyleComment)


def convertToDatetime(s, loc, tokens):
    try:
        # note that the year, month, and day fields were already
        # converted to ints from strings by the parse action defined
        # on the integer expression above
        return datetime(tokens.year, tokens.month, tokens.day).date()
    except Exception as ve:
        errmsg = "'%s/%s/%s' is not a valid date, %s" % (
            tokens.year,
            tokens.month,
            tokens.day,
            ve,
        )
        raise ParseException(errmsg, loc, s) from None


date_expr.add_parse_action(convertToDatetime)


date_expr.run_tests(
    """\
    2000/1/1

    # invalid month
    2000/13/1

    # 1900 was not a leap year
    1900/2/29

    # but 2000 was
    2000/2/29
    """
)


date_expr = iso8601_date.add_parse_action(convertToDate())
date_expr.ignore(pythonStyleComment)

date_expr.run_tests(
    """\
    2000-01-01

    # invalid month
    2000-13-01

    # 1900 was not a leap year
    1900-02-29

    # but 2000 was
    2000-02-29
    """
)
