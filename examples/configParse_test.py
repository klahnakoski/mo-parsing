#
# configparse.py
#
# an example of using the parsing module to be able to process a .INI configuration file
#
# Copyright (c) 2003, Paul McGuire
#
import pprint

from examples.configParse import inifile_BNF


def test(strng):

    iniFile = open(strng)
    iniData = "".join(iniFile.readlines())
    bnf = inifile_BNF()
    tokens = bnf.parse_string(iniData)


    iniFile.close()

    return tokens


ini = test("examples/Setup.ini")



