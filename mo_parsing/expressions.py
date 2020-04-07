# encoding: utf-8
from operator import itemgetter

from mo_future import text
from mo_logs import Log

from mo_parsing.core import ParserElement, _PendingSkip
from mo_parsing.enhancement import OneOrMore, Optional, SkipTo, Suppress, ZeroOrMore
from mo_parsing.exceptions import (
    ParseBaseException,
    ParseException,
    ParseSyntaxException,
)
from mo_parsing.results import ParseResults
from mo_parsing.tokens import Empty
from mo_parsing.utils import Iterable, _generatorType


class ParseExpression(ParserElement):
    """Abstract subclass of ParserElement, for combining and
    post-processing parsed tokens.
    """

    def __init__(self, exprs):
        super(ParseExpression, self).__init__()

        if isinstance(exprs, _generatorType):
            exprs = list(exprs)
        elif not isinstance(exprs, ParserElement) and isinstance(exprs, Iterable):
            exprs = list(exprs)
        else:
            exprs = [exprs]

        self.exprs = [engine.CURRENT.normalize(e) for e in exprs]

    def copy(self):
        output = ParserElement.copy(self)
        if self.engine is engine.CURRENT:
            output.exprs = self.exprs
        else:
            output.exprs = [e.copy() for e in self.exprs]
        return output

    def append(self, other):
        self.exprs.append(other)
        return self

    def leaveWhitespace(self):
        """Extends ``leaveWhitespace`` defined in base class, and also invokes ``leaveWhitespace`` on
           all contained expressions."""
        output = self.copy()
        output.parser_config.skipWhitespace = False
        output.exprs = [e.leaveWhitespace() for e in self.exprs]
        return output

    def __str__(self):
        try:
            return super(ParseExpression, self).__str__()
        except Exception:
            pass

        return "%s:(%s)" % (self.__class__.__name__, text(self.exprs))

    def streamline(self):
        if self.streamlined:
            return self
        self.streamlined = True

        # collapse nested And's of the form And(And(And(a, b), c), d) to And(a, b, c, d)
        # but only if there are no parse actions or resultsNames on the nested And's
        # (likewise for Or's and MatchFirst's)
        acc = []
        for e in self.exprs:
            e.streamline()
            if (
                isinstance(e, self.__class__)
                and not e.parseAction
                and e.token_name is None
            ):
                acc.extend(e.exprs)
            else:
                acc.append(e)
        self.exprs = acc
        return self

    def validate(self, validateTrace=None):
        tmp = (validateTrace if validateTrace is not None else [])[:] + [self]
        for e in self.exprs:
            e.validate(tmp)
        self.checkRecursion([])

    def __call__(self, name):
        if not name:
            return self
        for e in self.exprs:
            if isinstance(e, ParserElement) and e.token_name:
                Log.error("token name is already set in child, use Group() to clarify")

        return ParserElement.__call__(self, name)


class And(ParseExpression):
    """
    Requires all given :class:`ParseExpression` s to be found in the given order.
    Expressions may be separated by whitespace.
    May be constructed using the ``'+'`` operator.
    May also be constructed using the ``'-'`` operator, which will
    suppress backtracking.

    Example::

        integer = Word(nums)
        name_expr = OneOrMore(Word(alphas))

        expr = And([integer("id"), name_expr("name"), integer("age")])
        # more easily written as:
        expr = integer("id") + name_expr("name") + integer("age")
    """

    class _ErrorStop(Empty):
        def __init__(self, *args, **kwargs):
            super(And._ErrorStop, self).__init__(*args, **kwargs)
            self.parser_name = "-"
            self.leaveWhitespace()

    def __init__(self, exprs):
        if exprs and Ellipsis in exprs:
            tmp = []
            for i, expr in enumerate(exprs):
                if expr is Ellipsis:
                    if i < len(exprs) - 1:
                        skipto_arg = (Empty() + exprs[i + 1]).exprs[-1]
                        tmp.append(SkipTo(skipto_arg)("_skipped*"))
                    else:
                        raise Exception(
                            "cannot construct And with sequence ending in ..."
                        )
                else:
                    tmp.append(expr)
            exprs[:] = tmp
        super(And, self).__init__(exprs)
        self.parser_config.mayReturnEmpty = all(
            e.parser_config.mayReturnEmpty for e in self.exprs
        )
        self.parser_config.skipWhitespace = self.exprs[0].parser_config.skipWhitespace

    def streamline(self):
        if self.streamlined:
            return self
        ParseExpression.streamline(self)

        # collapse any _PendingSkip's
        if self.exprs:
            if any(
                isinstance(e, ParseExpression)
                and e.exprs
                and isinstance(e.exprs[-1], _PendingSkip)
                for e in self.exprs[:-1]
            ):
                for i, e in enumerate(self.exprs[:-1]):
                    if e is None:
                        continue
                    if (
                        isinstance(e, ParseExpression)
                        and e.exprs
                        and isinstance(e.exprs[-1], _PendingSkip)
                    ):
                        e.exprs[-1] = e.exprs[-1] + self.exprs[i + 1]
                        self.exprs[i + 1] = None
                self.exprs = [e for e in self.exprs if e is not None]

        super(And, self).streamline()
        self.parser_config.mayReturnEmpty = all(
            e.parser_config.mayReturnEmpty for e in self.exprs
        )
        return self

    def parseImpl(self, instring, loc, doActions=True):
        # pass False as last arg to _parse for first element, since we already
        # pre-parsed the string as part of our And pre-parsing
        encountered_error_stop = False
        acc = []
        for e in self.exprs:
            if isinstance(e, And._ErrorStop):
                encountered_error_stop = True
                continue
            if encountered_error_stop:
                try:
                    loc, exprtokens = e._parse(instring, loc, doActions)
                except ParseSyntaxException:
                    raise
                except ParseBaseException as pe:
                    raise ParseSyntaxException(
                        pe.pstr, pe.loc, pe.msg, pe.parserElement
                    )
                except IndexError:
                    raise ParseSyntaxException(
                        instring, len(instring), self
                    )
            else:
                loc, exprtokens = e._parse(instring, loc, doActions)

            if not isinstance(exprtokens, ParseResults):
                Log.error(
                    "expecting {{type}} to emit parseresults", type=e.__class__.__name__
                )
            acc.append(exprtokens)

        return loc, ParseResults(self, acc)

    def __add__(self, other):
        if other is Ellipsis:
            return _PendingSkip(self)

        return And([self, engine.CURRENT.normalize(other)]).streamline()

    def checkRecursion(self, parseElementList):
        subRecCheckList = parseElementList[:] + [self]
        for e in self.exprs:
            e.checkRecursion(subRecCheckList)
            if not e.parser_config.mayReturnEmpty:
                break

    def __str__(self):
        if self.parser_name:
            return self.parser_name

        return "{" + " ".join(text(e) for e in self.exprs) + "}"


class Or(ParseExpression):
    """Requires that at least one :class:`ParseExpression` is found. If
    two expressions match, the expression that matches the longest
    string will be used. May be constructed using the ``'^'``
    operator.

    Example::

        # construct Or using '^' operator

        number = Word(nums) ^ Combine(Word(nums) + '.' + Word(nums))
        print(number.searchString("123 3.1416 789"))

    prints::

        [['123'], ['3.1416'], ['789']]
    """

    def __init__(self, exprs):
        super(Or, self).__init__(exprs)
        if self.exprs:
            self.parser_config.mayReturnEmpty = any(
                e.parser_config.mayReturnEmpty for e in self.exprs
            )
        else:
            self.parser_config.mayReturnEmpty = True

    def parseImpl(self, instring, loc, doActions=True):
        maxExcLoc = -1
        maxException = None
        matches = []
        for e in self.exprs:
            try:
                loc2 = e.tryParse(instring, loc)
            except ParseException as err:
                err.__traceback__ = None
                if err.loc > maxExcLoc:
                    maxException = err
                    maxExcLoc = err.loc
            except IndexError:
                if len(instring) > maxExcLoc:
                    maxException = ParseException(
                        instring, len(instring), self
                    )
                    maxExcLoc = len(instring)
            else:
                # save match among all matches, to retry longest to shortest
                matches.append((loc2, e))

        if matches:
            # re-evaluate all matches in descending order of length of match, in case attached actions
            # might change whether or how much they match of the input.
            matches.sort(key=itemgetter(0), reverse=True)

            if not doActions:
                # no further conditions or parse actions to change the selection of
                # alternative, so the first match will be the best match
                _, best_expr = matches[0]
                loc, best_results = best_expr._parse(instring, loc, doActions)
                return loc, ParseResults(self, [best_results])

            longest = -1, None
            for loc1, expr1 in matches:
                if loc1 <= longest[0]:
                    # already have a longer match than this one will deliver, we are done
                    return longest

                try:
                    loc2, toks = expr1._parse(instring, loc, doActions)
                except ParseException as err:
                    err.__traceback__ = None
                    if err.loc > maxExcLoc:
                        maxException = err
                        maxExcLoc = err.loc
                else:
                    if loc2 >= loc1:
                        return loc2, ParseResults(self, [toks])
                    # didn't match as much as before
                    elif loc2 > longest[0]:
                        longest = loc2, ParseResults(self, [toks])

            if longest != (-1, None):
                return longest

        if maxException is not None:
            maxException.msg = "expecting " + text(self)
            raise maxException
        else:
            raise ParseException(
                instring, loc, "no defined alternatives to match", self
            )

    def __str__(self):
        if self.parser_name:
            return self.parser_name

        return "{" + " ^ ".join(text(e) for e in self.exprs) + "}"

    def checkRecursion(self, parseElementList):
        subRecCheckList = parseElementList[:] + [self]
        for e in self.exprs:
            e.checkRecursion(subRecCheckList)


class MatchFirst(ParseExpression):
    """Requires that at least one :class:`ParseExpression` is found. If
    two expressions match, the first one listed is the one that will
    match. May be constructed using the ``'|'`` operator.

    Example::

        # construct MatchFirst using '|' operator

        # watch the order of expressions to match
        number = Word(nums) | Combine(Word(nums) + '.' + Word(nums))
        print(number.searchString("123 3.1416 789")) #  Fail! -> [['123'], ['3'], ['1416'], ['789']]

        # put more selective expression first
        number = Combine(Word(nums) + '.' + Word(nums)) | Word(nums)
        print(number.searchString("123 3.1416 789")) #  Better -> [['123'], ['3.1416'], ['789']]
    """

    def __init__(self, exprs):
        super(MatchFirst, self).__init__(exprs)
        if self.exprs:
            self.parser_config.mayReturnEmpty = any(
                e.parser_config.mayReturnEmpty for e in self.exprs
            )
        else:
            self.parser_config.mayReturnEmpty = True

    def parseImpl(self, instring, loc, doActions=True):
        maxExcLoc = -1
        maxException = None
        for e in self.exprs:
            try:
                loc, ret = e._parse(instring, loc, doActions)
                return loc, ParseResults(self, [ret])
            except ParseException as err:
                if err.loc > maxExcLoc:
                    maxException = err
                    maxExcLoc = err.loc
            except IndexError:
                if len(instring) > maxExcLoc:
                    maxException = ParseException(
                        instring, len(instring), self
                    )
                    maxExcLoc = len(instring)

        # only got here if no expression matched, raise exception for match that made it the furthest
        else:
            if maxException is not None:
                maxException.msg = "Expecting "+text(self)
                raise maxException
            else:
                raise ParseException(
                    instring, loc, self
                )

    def __or__(self, other):
        if other is Ellipsis:
            return _PendingSkip(Optional(self))

        return MatchFirst([self, engine.CURRENT.normalize(other)]).streamline()

    def __ror__(self, other):
        return engine.CURRENT.normalize(other) | self

    def __str__(self):
        if self.parser_name:
            return self.parser_name

        return " | ".join("{" + text(e) + "}" for e in self.exprs)

    def checkRecursion(self, parseElementList):
        subRecCheckList = parseElementList[:] + [self]
        for e in self.exprs:
            e.checkRecursion(subRecCheckList)


class Each(ParseExpression):
    """Requires all given :class:`ParseExpression` s to be found, but in
    any order. Expressions may be separated by whitespace.

    May be constructed using the ``'&'`` operator.

    Example::

        color = oneOf("RED ORANGE YELLOW GREEN BLUE PURPLE BLACK WHITE BROWN")
        shape_type = oneOf("SQUARE CIRCLE TRIANGLE STAR HEXAGON OCTAGON")
        integer = Word(nums)
        shape_attr = "shape:" + shape_type("shape")
        posn_attr = "posn:" + Group(integer("x") + ',' + integer("y"))("posn")
        color_attr = "color:" + color("color")
        size_attr = "size:" + integer("size")

        # use Each (using operator '&') to accept attributes in any order
        # (shape and posn are required, color and size are optional)
        shape_spec = shape_attr & posn_attr & Optional(color_attr) & Optional(size_attr)

        test.runTests(shape_spec, '''
            shape: SQUARE color: BLACK posn: 100, 120
            shape: CIRCLE size: 50 color: BLUE posn: 50,80
            color:GREEN size:20 shape:TRIANGLE posn:20,40
            '''
            )

    prints::

        shape: SQUARE color: BLACK posn: 100, 120
        ['shape:', 'SQUARE', 'color:', 'BLACK', 'posn:', ['100', ',', '120']]
        - color: BLACK
        - posn: ['100', ',', '120']
          - x: 100
          - y: 120
        - shape: SQUARE


        shape: CIRCLE size: 50 color: BLUE posn: 50,80
        ['shape:', 'CIRCLE', 'size:', '50', 'color:', 'BLUE', 'posn:', ['50', ',', '80']]
        - color: BLUE
        - posn: ['50', ',', '80']
          - x: 50
          - y: 80
        - shape: CIRCLE
        - size: 50


        color: GREEN size: 20 shape: TRIANGLE posn: 20,40
        ['color:', 'GREEN', 'size:', '20', 'shape:', 'TRIANGLE', 'posn:', ['20', ',', '40']]
        - color: GREEN
        - posn: ['20', ',', '40']
          - x: 20
          - y: 40
        - shape: TRIANGLE
        - size: 20
    """

    def __init__(self, exprs):
        super(Each, self).__init__(exprs)
        self.parser_config.mayReturnEmpty = all(
            e.parser_config.mayReturnEmpty for e in self.exprs
        )
        self.parser_config.skipWhitespace = True
        self.initExprGroups = True

    def streamline(self):
        if self.streamlined:
            return self

        super(Each, self).streamline()
        self.parser_config.mayReturnEmpty = all(
            e.parser_config.mayReturnEmpty for e in self.exprs
        )
        return self

    def parseImpl(self, instring, loc, doActions=True):
        if self.initExprGroups:
            self.opt1map = dict(
                (id(e.expr), e) for e in self.exprs if isinstance(e, Optional)
            )
            opt1 = [e.expr for e in self.exprs if isinstance(e, Optional)]
            opt2 = [
                e
                for e in self.exprs
                if e.parser_config.mayReturnEmpty and not isinstance(e, Optional)
            ]
            self.optionals = opt1 + opt2
            self.multioptionals = [
                e.expr for e in self.exprs if isinstance(e, ZeroOrMore)
            ]
            self.multirequired = [
                e.expr for e in self.exprs if isinstance(e, OneOrMore)
            ]
            self.required = [
                e
                for e in self.exprs
                if not isinstance(e, (Optional, ZeroOrMore, OneOrMore))
            ]
            self.required += self.multirequired
            self.initExprGroups = False
        tmpLoc = loc
        tmpReqd = self.required[:]
        tmpOpt = self.optionals[:]
        matchOrder = []

        keepMatching = True
        while keepMatching:
            tmpExprs = tmpReqd + tmpOpt + self.multioptionals + self.multirequired
            failed = []
            for e in tmpExprs:
                try:
                    tmpLoc = e.tryParse(instring, tmpLoc)
                except ParseException:
                    failed.append(e)
                else:
                    matchOrder.append(self.opt1map.get(id(e), e))
                    if e in tmpReqd:
                        tmpReqd.remove(e)
                    elif e in tmpOpt:
                        tmpOpt.remove(e)
            if len(failed) == len(tmpExprs):
                keepMatching = False

        if tmpReqd:
            missing = ", ".join(text(e) for e in tmpReqd)
            raise ParseException(
                instring, loc, "Missing one or more required elements (%s)" % missing
            )

        # add any unmatched Optionals, in case they have default values defined
        matchOrder += [
            e for e in self.exprs if isinstance(e, Optional) and e.expr in tmpOpt
        ]

        resultlist = []
        for e in matchOrder:
            loc, results = e._parse(instring, loc, doActions)
            resultlist.append(results)

        finalResults = ParseResults(self, resultlist)
        return loc, finalResults

    def __str__(self):
        if self.parser_name:
            return self.parser_name

        return "{" + " & ".join(text(e) for e in self.exprs) + "}"

    def checkRecursion(self, parseElementList):
        subRecCheckList = parseElementList[:] + [self]
        for e in self.exprs:
            e.checkRecursion(subRecCheckList)


# export
from mo_parsing import core, engine

core.And = And
core.Or = Or
core.Each = Each
core.MatchFirst = MatchFirst

from mo_parsing import helpers

helpers.MatchFirst = MatchFirst
helpers.And = And
