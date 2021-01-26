# encoding: utf-8
# THIS FILE IS AUTOGENERATED!
from __future__ import unicode_literals
from setuptools import setup
setup(
    author='Various',
    author_email='kyle@lahnakoski.com',
    classifiers=["Development Status :: 4 - Beta","License :: OSI Approved :: MIT License","Programming Language :: Python :: 3.7","Topic :: Software Development :: Libraries","Topic :: Software Development :: Libraries :: Python Modules"],
    description='Another PEG Parsing Tool',
    install_requires=["mo-dots==4.2.20340","mo-future==3.147.20327"],
    license='MIT',
    long_description='# More Parsing!\n\nAn experimental fork of [pyparsing](https://github.com/pyparsing/pyparsing)\n\n\n|Branch      |Status   |\n|------------|---------|\n|master      | [![Build Status](https://travis-ci.org/klahnakoski/mo-parsing.svg?branch=master)](https://travis-ci.org/klahnakoski/mo-parsing) |\n|dev         | [![Build Status](https://travis-ci.org/klahnakoski/mo-parsing.svg?branch=dev)](https://travis-ci.org/klahnakoski/mo-parsing)    |\n\n\n## Summary of Differences\n\nThis has been forked to experiment with faster parsing in the [moz-sql-parser](https://github.com/klahnakoski/moz-sql-parser).\n\nMore features\n\n* Added `Engine`, which controls parsing context and whitespace (a basic lexxer)\n* faster infix operator parsing (main reason for this fork)\n* ParseResults point to ParserElement for reduced size\n* packrat parser is always on\n* less stack used \n* the wildcard ("`*`") could be used to indicate multi-values are expected; this is not allowed: all values are multi-values\n* all actions are in `f(token, index, string)` form, which is opposite of pyparsing\'s `f(string, index token)` form\n\n\nMore focused \n\n* removed all backward-compatibility settings\n* no support for binary serialization (no pickle)\n\nMore functional\n\n* ParseResults are static, can not be changed, parsing functions must emit new objects\n* ParserElements are static: Many are generated during language definition\n\n## Details\n\n### The `Engine`\n\nThe `mo_parsing.engine.CURRENT` is used during parser creation: It is effectively the lexxer with additional features to simplify the language definition.  You declare a standard `Engine` like so:\n\n    with Engine() as engine:\n        # PUT YOUR LANGUAGE DEFINITION HERE\n\nIf you are declaring a large language, and you want to minimize indentation, and you are careful, you may also use this pattern:\n\n    engine = Engine().use()\n    # PUT YOUR LANGUAGE DEFINITION HERE\n    engine.release()\n\nThe engine can be used to set global parsing parameters, like\n\n* `set_whitespace()` - set the ignored characters (like whitespace)\n* `add_ignore()` - include whole patterns that are ignored (like comments)\n* `set_debug_actions()` - insert functions to run for detailed debugging\n* `set_literal()` - Set the definition for what `Literal()` means\n* `set_keyword_chars()` - For default `Keyword()`\n\nThe `engine.CURRENT` is added to every parse element created, and it is used during parsing to packrat the current parsed string. \n\n\n### Navigating ParseResults\n\n`ParseResults` are in the form of an n-ary tree; with the children found in `ParseResults.tokens`.  Each `ParseResult.type` points to the `ParserElement` that made it.  In general, if you want to get fancy with post processing (or in a `parseAction`), you will be required to navigate the raw `tokens` to generate a final result\n\nThere are some convenience methods;  \n* `__iter__()` - allows you to iterate through parse results in **depth first search**. Empty results are skipped, and `Group`ed  results are treated as atoms (which can be further iterated if required) \n* `name` is a convenient property for `ParseResults.type.token_name`\n* `__getitem__()` - allows you to jump into the parse tree to the given `name`. This is blocked by any names found inside `Group`ed results (because groups are considered atoms).      \n\n### addParseAction\n\nParse actions are methods that are run after a ParserElement found a match. \n\n* Parameters must be accepted in `(tokens, index, string)` order (the opposite of pyparsing)\n* Parse actions are wrapped to ensure the output is a legitimate ParseResult\n  * If your parse action returns `None` then the result is the original `tokens`\n  * If your parse action returns an object, or list, or tuple, then it will be packaged in a `ParseResult` with same type as `tokens`.\n  * If your parse action returns a `ParseResult` then it is accepted ***even if is belongs to some other pattern***\n  \n',
    long_description_content_type='text/markdown',
    name='mo-parsing',
    packages=["mo_parsing"],
    url='https://github.com/klahnakoski/mo-parsing',
    version='4.13.21026'
)