#
# cLibHeader.py
#
# A simple parser to extract API doc info from a C header file
#
# Copyright, 2012 - Paul McGuire
#

from mo_parsing import (
    Word,
    alphas,
    alphanums,
    Combine,
    one_of,
    Optional,
    delimited_list,
    Group,
    Keyword,
)

testdata = """
  int func1(float *vec, int len, double arg1);
  int func2(float **arr, float *vec, int len, double arg1, double arg2);
  """

ident = Word(alphas, alphanums + "_")
vartype = Combine(one_of("float double int char") + Optional(Word("*")))
arglist = delimited_list(Group(vartype("type") + ident("name")))

functionCall = Keyword("int") + ident("name") + "(" + arglist("args") + ")" + ";"

for fn, s, e in functionCall.scan_string(testdata):

    for a in fn.args:

