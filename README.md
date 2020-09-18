# mo-parsing

An experimental fork of [pyparsing](https://github.com/pyparsing/pyparsing)

## Details

This has been forked to experiment with faster parsing in the moz-sql-parser.

More features

* Added `Engine`, which controls parsing context and whitespace (think lexxer)
* faster infix parsing (main reason for this fork)
* ParseResults point to ParserElement for reduced size
* packrat parser is always on
* less stack used 


Less Cruft

* removed all backward-compatibility settings
* no support for binary serialization (no pickel)
* tokens are static, can not be changed, parsing functions must emit new objects
* ParserElements are static: Many are generated during language definition
* ParseActions must adhere to a strict interface


## Installation

