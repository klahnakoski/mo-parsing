# encoding: utf-8
# THIS FILE IS AUTOGENERATED!
from __future__ import unicode_literals
from setuptools import setup
setup(
    author='Various',
    author_email='kyle@lahnakoski.com',
    classifiers=["Development Status :: 4 - Beta","License :: OSI Approved :: MIT License","Programming Language :: Python :: 3.7","Topic :: Software Development :: Libraries","Topic :: Software Development :: Libraries :: Python Modules"],
    description='Another PEG Parsing Tool',
    extras_require={"tests":["mo-testing","mo-threads","mo-logs","mo-files"]},
    install_requires=["mo-dots==8.4.21326","mo-future==6.2.21303"],
    license='MIT',
    long_description='# More Parsing!\n\n[![PyPI Latest Release](https://img.shields.io/pypi/v/mo-parsing.svg)](https://pypi.org/project/mo-parsing/)\n[![Build Status](https://app.travis-ci.com/klahnakoski/mo-parsing.svg?branch=master)](https://travis-ci.com/github/klahnakoski/mo-parsing)\n[![Coverage Status](https://coveralls.io/repos/github/klahnakoski/mo-parsing/badge.svg?branch=master)](https://coveralls.io/github/klahnakoski/mo-parsing?branch=master)\n\nA fork of [pyparsing](https://github.com/pyparsing/pyparsing) for faster parsing\n\n\n## Installation\n\nThis is a pypi package\n\n    pip install mo-parsing\n    \n## Usage\n\nThis module allows you to define a PEG parser using predefined patterns and Python operators.  Here is an example \n\n```\n>>> from mo_parsing import Word\n>>> from mo_parsing.utils import alphas\n>>>\n>>> greet = Word(alphas)("greeting") + "," + Word(alphas)("person") + "!"\n>>> result = greet.parse_string("Hello, World!")\n```\n\nThe `result` can be accessed as a nested list\n\n```\n>>> list(result)\n[\'Hello\', \',\', \'World\', \'!\']\n```\n\nThe `result` can also be accessed as a dictionary\n\n```\n>>> dict(result)\n{\'greeting\': \'Hello\', \'person\': \'World\'}\n```\n\nRead the [pyparsing documentation](https://github.com/pyparsing/pyparsing/#readme) for more\n\n### The `Whitespace` Skipper\n\nThe `mo_parsing.whitespaces.CURRENT` is used during parser creation: It is effectively defines what "whitespace" to skip during parsing, with additional features to simplify the language definition.  You declare "standard" `Whitespace` like so:\n\n    with Whitespace() as whitespace:\n        # PUT YOUR LANGUAGE DEFINITION HERE (space, tab and CR are "whitespace")\n\nIf you are declaring a large language, and you want to minimize indentation, and you are careful, you may also use this pattern:\n\n    whitespace = Whitespace().use()\n    # PUT YOUR LANGUAGE DEFINITION HERE\n    whitespace.release()\n\nThe whitespace can be used to set global parsing parameters, like\n\n* `set_whitespace()` - set the ignored characters (default: `"\\t\\n "`)\n* `add_ignore()` - include whole patterns that are ignored (like comments)\n* `set_literal()` - Set the definition for what `Literal()` means\n* `set_keyword_chars()` - For default `Keyword()` (important for defining word boundary)\n\n\n### Navigating ParseResults\n\nThe results of parsing are in `ParseResults` and are in the form of an n-ary tree; with the children found in `ParseResults.tokens`.  Each `ParseResult.type` points to the `ParserElement` that made it.  In general, if you want to get fancy with post processing (or in a `parse_action`), you will be required to navigate the raw `tokens` to generate a final result\n\nThere are some convenience methods;  \n* `__iter__()` - allows you to iterate through parse results in **depth first search**. Empty results are skipped, and `Group`ed results are treated as atoms (which can be further iterated if required) \n* `name` is a convenient property for `ParseResults.type.token_name`\n* `__getitem__()` - allows you to jump into the parse tree to the given `name`. This is blocked by any names found inside `Group`ed results (because groups are considered atoms).      \n\n### Parse Actions\n\nParse actions are methods that are run after a ParserElement found a match. \n\n* Parameters must be accepted in `(tokens, index, string)` order (the opposite of pyparsing)\n* Parse actions are wrapped to ensure the output is a legitimate ParseResult\n  * If your parse action returns `None` then the result is the original `tokens`\n  * If your parse action returns an object, or list, or tuple, then it will be packaged in a `ParseResult` with same type as `tokens`.\n  * If your parse action returns a `ParseResult` then it is accepted ***even if is belongs to some other pattern***\n  \n#### Simple example:\n\n```\ninteger = Word("0123456789").add_parse_action(lambda t, i, s: int(t[0]))\nresult = integer.parse_string("42")\nassert (result[0] == 42)\n```\n\nFor slightly shorter specification, you may use the `/` operator and only parameters you need:\n\n```\ninteger = Word("0123456789") / (lambda t: int(t[0]))\nresult = integer.parse_string("42")\nassert (result[0] == 42)\n```\n\n### Debugging\n\nThe PEG-style of mo-parsing (from pyparsing) makes a very expressible and readable specification, but debugging a parser is still hard.  To look deeper into what the parser is doing use the `Debugger`:\n\n```\nwith Debugger():\n    expr.parse_string("my new language")\n```\n\nThe debugger will print out details of what\'s happening\n\n* Each attempt, and if it matched or failed\n* A small number of bytes to show you the current position\n* location, line and column for more info about the current position\n* whitespace indicating stack depth\n* print out of the ParserElement performing the attempt\n\nThis should help to isolate the exact position your grammar is failing. \n\n### Regular Expressions\n\n`mo-parsing` can parse and generate regular expressions. `ParserElement` has a `__regex__()` function that returns the regular expression for the given grammar; which works up to a limit, and is used internally to accelerate parsing.  The `Regex` class parses regular expressions into a grammar; it is used to optimize parsing, and you may find it useful to decompose regular expressions that look like line noise.\n\n\n\n\n\n\n\n\n\n\n## Differences from PyParsing\n\nThis fork was originally created to support faster parsing for [mo-sql-parsing](https://github.com/klahnakoski/moz-sql-parser).  Since then it has deviated sufficiently to be it\'s own collection of parser specification functions.  Here are the differences:\n\n* Added `Whitespace`, which controls parsing context and whitespace.  It replaces the whitespace modifying methods of pyparsing\n* the wildcard ("`*`") could be used in pyparsing to indicate multi-values are expected; this is not allowed in `mo-parsing`: all values are multi-values\n* ParserElements are static: For example, `expr.add_parse_action(action)` creates a new ParserElement, so must be assigned to variable or it is lost. **This is the biggest source of bugs when converting from pyparsing**\n* removed all backward-compatibility settings\n* no support for binary serialization (no pickle)\n\nFaster Parsing\n\n* faster infix operator parsing (main reason for this fork)\n* ParseResults point to ParserElement for reduced size\n* regex used to reduce the number of failed parse attempts  \n* packrat parser is not need\n* less stack used \n\n\n\n## Contributing\n\nIf you plan to extend or enhance this code, please [see the README in the tests directory](https://github.com/klahnakoski/mo-parsing/blob/dev/tests/README.md)',
    long_description_content_type='text/markdown',
    name='mo-parsing',
    packages=["mo_parsing"],
    url='https://github.com/klahnakoski/mo-parsing',
    version='8.12.21350'
)