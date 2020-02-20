# mo-parsing

A serious fork of [pyparsing](https://github.com/pyparsing/pyparsing)

## Details

This has been forked to support faster parsing in the moz-sql-parser.

* no support for binary serialization (pickel)
* ParseResults point to ParserElement for reduced size
* packrat parser is always on
* tokens are static, can not be changed, parsing functions must emit new objects
* parsing functions must adhere to a strict interface
* less stack depth