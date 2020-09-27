# mo-parsing

An experimental fork of [pyparsing](https://github.com/pyparsing/pyparsing)

## Summary of Differences

This has been forked to experiment with faster parsing in the moz-sql-parser.

More features

* Added `Engine`, which controls parsing context and whitespace (think lexxer)
* faster infix parsing (main reason for this fork)
* ParseResults point to ParserElement for reduced size
* packrat parser is always on
* less stack used 
* the wildcard ("*") could be used to indicate multi-values are expected; this is not allowed: all values are multi-values
* all actions are in `f(token, index, string)` form, which is opposite of pyparsing's flexible `f(string, index token)` form


More focused 

* removed all backward-compatibility settings
* no support for binary serialization (no pickle)
* ParseActions must adhere to a strict interface

More functional

* tokens are static, can not be changed, parsing functions must emit new objects
* ParserElements are static: Many are generated during language definition


## Installation

Not in pypi yet

## Details

### The `Engine`

The `mo_parsing.engine.CURRENT` is used during parser creation: It is effectively the lexxer with additional features to simplify the language definition.  You declare a standard `Engine` like so:

    with Engine() as engine:
        # PUT YOUR LANGUAGE DEFINITION HERE

If you are declaring a large language, and you want to minimize indentation, and you are careful, you may also use this pattern:

    engine = Engine().use()
    # PUT YOUR LANGUAGE DEFINITION HERE
    engine.release()

The engine can be used to set global parsing parameters, like

* `set_whitespace()` - set the ignored characters (like whitespace)
* `add_ignore()` - include whole patterns that are ignored (like commnets)
* `set_debug_actions()` - insert functions to run for detailed debuigging
* `set_literal()` - Set the definition for what `Literal()` means
* `set_keyword_chars()` - For default `Keyword()`

The `engine.CURRENT` is added to every parse element created, and it is used during parsing to packrat the current parsed string.    

