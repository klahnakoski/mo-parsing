#
# idlparse.py
#
# an example of using the parsing module to be able to process a subset of the CORBA IDL grammar
#
# Copyright (c) 2003, Paul McGuire
#

from examples.idlParse import CORBA_IDL_BNF
from mo_parsing import ParseException

testnum = 1


def test(strng):
    global testnum

    try:
        bnf = CORBA_IDL_BNF()
        tokens = bnf.parse_string(strng)
        imgname = "idlParse%02d.bmp" % testnum
        testnum += 1
    except ParseException as err:
        pass

test(
    """
    /*
     * a block comment *
     */
    typedef string[10] tenStrings;
    typedef sequence<string> stringSeq;
    typedef sequence< sequence<string> > stringSeqSeq;

    interface QoSAdmin {
        stringSeq method1( in string arg1, inout long arg2 );
        stringSeqSeq method2( in string arg1, inout long arg2, inout long arg3);
        string method3();
      };
    """
)
test(
    """
    /*
     * a block comment *
     */
    typedef string[10] tenStrings;
    typedef
        /** ** *** **** *
         * a block comment *
         */
        sequence<string> /*comment inside an And */ stringSeq;
    /* */  /**/ /***/ /****/
    typedef sequence< sequence<string> > stringSeqSeq;

    interface QoSAdmin {
        stringSeq method1( in string arg1, inout long arg2 );
        stringSeqSeq method2( in string arg1, inout long arg2, inout long arg3);
        string method3();
      };
    """
)
test(
    r"""
      const string test="Test String\n";
      const long  a = 0;
      const long  b = -100;
      const float c = 3.14159;
      const long  d = 0x007f7f7f;
      exception TestException
        {
        string msg;
        sequence<string> dataStrings;
        };

      interface TestInterface
        {
        void method1( in string arg1, inout long arg2 );
        };
    """
)
test(
    """
    module Test1
      {
      exception TestException
        {
        string msg;
        ];

      interface TestInterface
        {
        void method1( in string arg1, inout long arg2 )
          raises ( TestException );
        };
      };
    """
)
test(
    """
    module Test1
      {
      exception TestException
        {
        string msg;
        };

      };
    """
)
