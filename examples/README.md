# Examples

> Note: This is a fork of pyparsing's exmaples directory; most examples do not work becasue of differences in the parser.  The main difference being ParseResults attribute access (`tokens.html`) is not allow in mo-parsing, use property access (`tokens['html']`) instead.  Also, `setParseAction()` returns a copy of the ParserElement: Instead of `p.add_parse_action(action)` use `p-p.adddParseAction(action)` 

The examples can be run two different ways

### Directly

Most examples are simple Python programs that define a grammar and parse some strings. They will throw an exception and error-out if parsing failed. You can run them directly. 

    python examples/antler_grammar.py

> Be sure you are in the `pyparsing` project directory, not the `example` directory

### Test Suite

The test suite can run the examples for you 
