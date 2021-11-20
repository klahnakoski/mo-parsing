# rangeCheck.py
#
#   A sample program showing how parse actions can convert parsed
# strings into a data type or object, and to validate the parsed value.
#
# Updated to use new add_condition method and expr() copy.
#
# Copyright 2011,2015 Paul T. McGuire
#

from datetime import datetime

from mo_parsing import Word, nums, Suppress, Optional


def ranged_value(expr, minval=None, maxval=None):
    # have to specify at least one range boundary
    if minval is None and maxval is None:
        raise ValueError("minval or maxval must be specified")

    # set range testing function and error message depending on
    # whether either or both min and max values are given
    inRangeCondition = {
        (True, False): lambda t, l, s: t[0] <= maxval,
        (False, True): lambda t, l, s: minval <= t[0],
        (False, False): lambda t, l, s: minval <= t[0] <= maxval,
    }[minval is None, maxval is None]
    outOfRangeMessage = {
        (True, False): "value is greater than %s" % maxval,
        (False, True): "value is less than %s" % minval,
        (False, False): "value is not in the range ({} to {})".format(minval, maxval),
    }[minval is None, maxval is None]

    return expr().add_condition(inRangeCondition, message=outOfRangeMessage)


# define the expressions for a date of the form YYYY/MM/DD or YYYY/MM (assumes YYYY/MM/01)
integer = Word(nums).set_parser_name("integer")
integer.add_parse_action(lambda t: int(t[0]))

month = ranged_value(integer, 1, 12)
day = ranged_value(integer, 1, 31)
year = ranged_value(integer, 2000, None)

SLASH = Suppress("/")
date_expr = year("year") + SLASH + month("month") + Optional(SLASH + day("day"))
date_expr.set_parser_name("date")

# convert date fields to datetime (also validates dates as truly valid dates)
date_expr.add_parse_action(lambda t: datetime(t.year, t.month, t.day or 1).date())

# add range checking on dates
mindate = datetime(2002, 1, 1).date()
maxdate = datetime.now().date()
date_expr = ranged_value(date_expr, mindate, maxdate)


date_expr.run_tests(
    """
    2011/5/8
    2001/1/1
    2004/2/29
    2004/2
    1999/12/31"""
)
