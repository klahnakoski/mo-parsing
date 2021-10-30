from examples.verilogParse import Verilog_BNF
from mo_parsing import ParseException


def test(strng):
    try:
        tokens = Verilog_BNF().parse_string(strng)
    except ParseException as err:
        raise err

    return tokens


toptest = """
    module TOP( in, out );
    input [7:0] in;
    output [5:0] out;
    COUNT_BITS8 count_bits( .IN( in ), .C( out ) );
    endmodule"""

