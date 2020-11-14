# More Parsing!

An experimental fork of [pyparsing](https://github.com/pyparsing/pyparsing)


|Branch      |Status   |
|------------|---------|
|master      | [![Build Status](https://travis-ci.org/klahnakoski/mo-parsing.svg?branch=master)](https://travis-ci.org/klahnakoski/mo-parsing) |
|dev         | [![Build Status](https://travis-ci.org/klahnakoski/mo-parsing.svg?branch=dev)](https://travis-ci.org/klahnakoski/mo-parsing)    |


## Summary of Differences

This has been forked to experiment with faster parsing in the [moz-sql-parser](https://github.com/klahnakoski/moz-sql-parser).

More features

* Added `Engine`, which controls parsing context and whitespace (a basic lexxer)
* faster infix operator parsing (main reason for this fork)
* ParseResults point to ParserElement for reduced size
* packrat parser is always on
* less stack used 
* the wildcard ("`*`") could be used to indicate multi-values are expected; this is not allowed: all values are multi-values
* all actions are in `f(token, index, string)` form, which is opposite of pyparsing's `f(string, index token)` form


More focused 

* removed all backward-compatibility settings
* no support for binary serialization (no pickle)

More functional

* ParseResults are static, can not be changed, parsing functions must emit new objects
* ParserElements are static: Many are generated during language definition

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
* `add_ignore()` - include whole patterns that are ignored (like comments)
* `set_debug_actions()` - insert functions to run for detailed debugging
* `set_literal()` - Set the definition for what `Literal()` means
* `set_keyword_chars()` - For default `Keyword()`

The `engine.CURRENT` is added to every parse element created, and it is used during parsing to packrat the current parsed string. 


### Navigating ParseResults

`ParseResults` are in the form of an n-ary tree; with the children found in `ParseResults.tokens`.  Each `ParseResult.type` points to the `ParserElement` that made it.  In general, if you want to get fancy with post processing (or in a `parseAction`), you will be required to navigate the raw `tokens` to generate a final result

There are some convenience methods;  
* `__iter__()` - allows you to iterate through parse results in **depth first search**. Empty results are skipped, and `Group`ed  results are treated as atoms (which can be further iterated if required) 
* `name` is a convenient property for `ParseResults.type.token_name`
* `__getitem__()` - allows you to jump into the parse tree to the given `name`. This is blocked by any names found inside `Group`ed results (because groups are considered atoms).      

### addParseAction

Parse actions are methods that are run after a ParserElement found a match. 

* Parameters must be accepted in `(tokens, index, string)` order (the opposite of pyparsing)
* Parse actions are wrapped to ensure the output is a legitimate ParseResult
  * If your parse action returns `None` then the result is the original `tokens`
  * If your parse action returns an object, or list, or tuple, then it will be packaged in a `ParseResult` with same type as `tokens`.
  * If your parse action returns a `ParseResult` then it is accepted ***even if is belongs to some other pattern***
  
