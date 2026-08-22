# encoding: utf-8
import json
from collections import OrderedDict

from mo_future import Iterable, text, generator_types
from mo_imports import export

from mo_parsing import exceptions, whitespaces
from mo_parsing.core import ParserElement, _PendingSkip, fuse_row
from mo_parsing.enhancement import Optional, SkipTo, Many, LookBehind, Group
from mo_parsing.exceptions import (
    FAIL,
    ParseException,
    ParseSyntaxException,
    failure,
    failure_at,
)
from mo_parsing.results import ParseResults
from mo_parsing.tokens import Empty
from mo_parsing.utils import (
    BACKREFERENCE,
    empty_tuple,
    is_forward,
    regex_atomic,
    regex_iso,
    regex_range,
    Log,
    append_config,
    regex_caseless,
    regex_compile,
)
from mo_parsing.whitespaces import Whitespace


class ParseExpression(ParserElement):
    """Abstract subclass of ParserElement, for combining and
    post-processing parsed tokens.
    """

    __slots__ = ["exprs"]

    def __init__(self, exprs):
        super(ParseExpression, self).__init__()

        if isinstance(exprs, generator_types):
            exprs = list(exprs)
        elif not isinstance(exprs, ParserElement) and isinstance(exprs, Iterable):
            exprs = list(exprs)
        else:
            exprs = [exprs]

        self.exprs = [whitespaces.CURRENT.normalize(e) for e in exprs]
        for e in self.exprs:
            if is_forward(e):
                e.track(self)

    def expecting(self):
        output = OrderedDict()
        if not self.is_annotated():
            for e in self.exprs:
                expect = e.expecting()
                if not expect:
                    # NOT SURE WHAT THIS IS EXPECTING, BAIL
                    return {}
                for k, ee in expect.items():
                    output.setdefault(k, []).extend(ee)
        else:
            for e in self.exprs:
                expect = e.expecting()
                if not expect:
                    # NOT SURE WHAT THIS IS EXPECTING, BAIL
                    return {}
                for k, _ in expect.items():
                    output[k] = [self]
        return output

    def copy(self):
        output = ParserElement.copy(self)
        output.exprs = self.exprs
        return output

    def append(self, other):
        self.exprs.append(other)
        return self

    def leave_whitespace(self):
        """Extends ``leave_whitespace`` defined in base class, and also invokes ``leave_whitespace`` on
        all contained expressions."""
        with whitespaces.NO_WHITESPACE:
            output = self.copy()
            output.exprs = [e.leave_whitespace() for e in self.exprs]
            return output

    def streamline(self):
        if self.streamlined:
            return self
        self.streamlined = True

        # collapse nested And's of the form And(And(And(a, b), c), d) to And(a, b, c, d)
        # but only if there are no parse actions or resultsNames on the nested And's
        # (likewise for Or's and MatchFirst's)
        if not self.is_annotated() and not self.exprs:
            return Empty(self.parser_name)

        acc = []
        same = True
        clazz = self.__class__
        if clazz == Or:
            clazz = (
                Or,
                MatchFirst,
            )  # TODO: not correct, but allows merging of the two to a single longer list
        for e in self.exprs:
            f = e.streamline()
            same = same and f is e
            if f in acc and clazz in (Or, MatchFirst):
                same = False
                continue
            elif f.is_annotated():
                acc.append(f)
            elif isinstance(f, clazz):
                same = False
                acc.extend(f.exprs)
            else:
                acc.append(f)

        if same:
            return self

        output = self.copy()
        output.exprs = acc
        output.streamlined = True
        return output

    def __regex__(self):
        """
        RETURN TUPLE (operator, pattern) WHERE operator REPRESENTS PRECEDENCE
        """
        raise NotImplementedError

    def __call__(self, name):
        if not name:
            return self
        return ParserElement.__call__(self, name)


def _and_plan(exprs):
    """(expr, is_look_behind, is_syntax_guard, fused) FOR EACH CHILD"""
    return tuple(
        (e, isinstance(e, LookBehind), isinstance(e, And.SyntaxErrorGuard), None)
        for e in exprs
    )


def _empty_many(expr, seen):
    """CAN expr RETURN AN EMPTY, ZERO-LENGTH Many RESULT? (CONSERVATIVE)"""
    if id(expr) in seen:
        return False
    seen.add(id(expr))
    if expr.parse_action:
        # an action decides the result type
        return True
    if isinstance(expr, Many):
        return expr.parser_config.min_match == 0
    if isinstance(expr, MatchFirst) and expr.transparent:
        return any(_empty_many(e, seen) for e in expr.exprs)
    if is_forward(expr):
        # ForwardResults.type is the child's type, and `<<` may change it later
        return True
    return False


def _white_pattern(whitespace, name):
    """WHITESPACE BETWEEN TWO FUSED CHILDREN, MATCHED GREEDILY AND ATOMICALLY"""
    if whitespace.ignore_list:
        pattern = whitespace.__regex__()[1]
        if BACKREFERENCE.search(pattern):
            return None
        return regex_atomic(pattern, name)
    if not whitespace.white_chars:
        return ""
    chars = regex_range(whitespace.white_chars)
    # a star over one character class can not give back what the lookahead forbids
    return f"{chars}*(?!{chars})"


def _fuse_run(run, whitespace):
    """ONE PATTERN FOR A RUN OF ADJACENT CHILDREN, OR None"""
    parts = []
    for i, (row, pattern, tokens, length) in enumerate(run):
        if i:
            white = _white_pattern(whitespace, f"w{i}")
            if white is None:
                return None
            parts.append(white)
        if length is None:
            parts.append(regex_atomic(pattern, f"f{i}"))
        else:
            # a fixed-length match has nothing to give back
            parts.append(f"(?P<f{i}>{pattern})")
    try:
        regex = regex_compile("".join(parts))
    except Exception:
        # a child pattern refuses to be embedded (own group names, inline flags)
        return None
    return (
        regex,
        tuple(
            (row[0], regex.groupindex[f"f{i}"], tokens)
            for i, (row, _, tokens, _) in enumerate(run)
        ),
    )


def _fused_plan(plan, whitespace):
    """REPLACE RUNS OF >=2 ADJACENT REGEX-ABLE CHILDREN WITH ONE PATTERN"""
    acc = []
    run = []

    def flush():
        if len(run) < 2:
            acc.extend(r[0] for r in run)
        else:
            fused = _fuse_run(run, whitespace)
            if fused is None:
                acc.extend(r[0] for r in run)
            else:
                acc.append((None, False, False, fused))
        run.clear()

    for row in plan:
        expr, is_look_behind, is_syntax_guard, _ = row
        fusable = None if is_look_behind or is_syntax_guard else fuse_row(expr)
        if fusable is None:
            flush()
            acc.append(row)
        else:
            run.append((row,) + fusable)
    flush()

    if len(acc) == len(plan):
        return plan
    return tuple(acc)


class And(ParseExpression):
    """
    Requires all given `ParseExpression` s to be found in the given order.
    Expressions may be separated by whitespace.
    May be constructed using the ``'+'`` operator.
    May also be constructed using the ``'-'`` operator, which will
    suppress backtracking.
    """

    __slots__ = ["plan", "plain_plan"]
    Config = append_config(ParseExpression, "whitespace")

    class SyntaxErrorGuard(Empty):
        def __init__(self, *args, **kwargs):
            with Whitespace(""):
                super(And.SyntaxErrorGuard, self).__init__(*args, **kwargs)
                self.parser_name = "-"

    def __init__(self, exprs, whitespace=None):
        if exprs and Ellipsis in exprs:
            tmp = []
            for i, expr in enumerate(exprs):
                if expr is Ellipsis:
                    if i < len(exprs) - 1:
                        skipto_arg = (Empty() + exprs[i + 1]).exprs[-1]
                        tmp.append(SkipTo(skipto_arg)("_skipped"))
                    else:
                        raise Exception(
                            "cannot construct And with sequence ending in ..."
                        )
                else:
                    tmp.append(expr)
            exprs[:] = tmp
        super(And, self).__init__(exprs)
        self.set_config(whitespace=whitespace or whitespaces.CURRENT)
        self.plan = self.plain_plan = _and_plan(self.exprs)

    def copy(self):
        output = ParseExpression.copy(self)
        output.plan = self.plan
        output.plain_plan = self.plain_plan
        return output

    def leave_whitespace(self):
        output = ParseExpression.leave_whitespace(self)
        output.set_plan(output.exprs)
        return output

    def set_plan(self, exprs):
        """DECIDE THE PER-CHILD PARSE PLAN, FUSING WHOLE RUNS OF CHILDREN"""
        self.plain_plan = _and_plan(exprs)
        self.plan = _fused_plan(self.plain_plan, self.parser_config.whitespace)

    def streamline(self):
        if self.streamlined:
            return self
        if not self.exprs:
            return Empty(self.parser_name)
        if len(self.exprs) == 1 and not self.is_annotated():
            return self.exprs[0].streamline()

        # collapse any _PendingSkip's
        same = True
        exprs = self.exprs
        if any(
            isinstance(e, ParseExpression)
            and e.exprs
            and isinstance(e.exprs[-1], _PendingSkip)
            for e in exprs[:-1]
        ):
            same = False
            for i, e in enumerate(exprs[:-1]):
                if (
                    isinstance(e, ParseExpression)
                    and e.exprs
                    and isinstance(e.exprs[-1], _PendingSkip)
                ):
                    ee = e.exprs[-1] + exprs[i + 1]
                    e.exprs[-1] = ee
                    e.streamlined = False
                    exprs[i + 1] = None

        # streamline INDIVIDUAL EXPRESSIONS
        acc = []
        for e in exprs:
            if e is None:
                continue
            f = e.streamline()
            same = same and f is e
            if f.is_annotated():
                acc.append(f)
            elif (
                isinstance(f, And)
                and f.parser_config.whitespace is self.parser_config.whitespace
            ):
                same = False
                acc.extend(f.exprs)
            else:
                acc.append(f)

        if same:
            self.streamlined = True
            self.set_plan(self.exprs)
            return self

        output = self.copy()
        output.exprs = acc
        output.set_plan(acc)
        output.streamlined = True
        return output

    def expecting(self):
        """
        RETURN A DICTIONARY OF ORDERED {regex: [patterns, ...]}
        WHERE
           regex IS a LIST OF (SEQUENCE OF NON-OVERLAPPING PATTERNS)
           patterns IS A LIST OF ParserElement
        :return:
        """
        if not self.exprs:
            return {}

        acc = OrderedDict()
        for e in self.exprs:
            expect = e.expecting()
            if not expect:
                return {}
            for k in expect.keys():
                acc[k] = [self]
            if e.min_length():
                break
        return acc

    def _min_length(self):
        return sum(e.min_length() for e in self.exprs)

    @property
    def whitespace(self):
        return self.parser_config.whitespace

    def parse_impl(self, string, start, do_actions=True):
        # pass False as last arg to _parse for first element, since we already
        # pre-parsed the string as part of our And pre-parsing
        encountered_syntax_error = False
        end = index = start
        acc = []
        failures = []
        skip = self.parser_config.whitespace.skip
        if exceptions.DIAGNOSTICS:
            plan = self.plain_plan
        else:
            plan = self.plan
        for expr, is_look_behind, is_syntax_guard, fused in plan:
            if end > index:
                if is_look_behind:
                    index = end
                else:
                    index = skip(string, end)
            if is_syntax_guard:
                encountered_syntax_error = True
                continue
            if fused is not None:
                regex, members = fused
                found = regex.match(string, index)
                if not found:
                    return FAIL
                for child, group, tokens in members:
                    s, e = found.span(group)
                    acc.append(ParseResults(
                        child,
                        s,
                        e,
                        [string[s:e]] if tokens is None else list(tokens),
                        [],
                    ))
                end = found.end()
                continue
            result = expr._parse(string, index, do_actions)
            if result.failed:
                failures.append(result)
                if encountered_syntax_error:
                    return failure_at(result, failures, ParseSyntaxException)
                else:
                    return failure_at(result, failures)
            failures.extend(result.failures)
            if (
                index == result.end
                and isinstance(result.type, Many)
                and result.type.parser_config.min_match == 0
                and not result
            ):
                continue
            acc.append(result)
            end = result.end

        return ParseResults(self, start, end, acc, failures)

    def _compile(self):
        skip = self.parser_config.whitespace.skip
        rows = []
        for expr, is_look_behind, is_syntax_guard, fused in self.plan:
            if is_syntax_guard:
                # the guard only picks the failure type, which fast mode drops
                continue
            if fused is not None:
                rows.append((None, False, fused[0], fused[1], False))
            else:
                rows.append((
                    expr.compile(),
                    is_look_behind,
                    None,
                    None,
                    _empty_many(expr, set()),
                ))
        rows = tuple(rows)

        if all(not lb and rx is None and not ck for _, lb, rx, _, ck in rows):
            children = tuple(row[0] for row in rows)

            def parse_children(string, start):
                end = index = start
                acc = []
                for child in children:
                    if end > index:
                        index = skip(string, end)
                    result = child(string, index)
                    if result.failed:
                        return FAIL
                    acc.append(result)
                    end = result.end
                return ParseResults(self, start, end, acc, [])

            return parse_children

        def parse(string, start):
            end = index = start
            acc = []
            for child, is_look_behind, regex, members, check_empty in rows:
                if end > index:
                    index = end if is_look_behind else skip(string, end)
                if regex is not None:
                    found = regex.match(string, index)
                    if not found:
                        return FAIL
                    for member, group, tokens in members:
                        s, e = found.span(group)
                        acc.append(ParseResults(
                            member,
                            s,
                            e,
                            [string[s:e]] if tokens is None else list(tokens),
                            [],
                        ))
                    end = found.end()
                    continue
                result = child(string, index)
                if result.failed:
                    return FAIL
                if (
                    check_empty
                    and index == result.end
                    and isinstance(result.type, Many)
                    and result.type.parser_config.min_match == 0
                    and not result
                ):
                    continue
                acc.append(result)
                end = result.end
            return ParseResults(self, start, end, acc, [])

        return parse

    def __add__(self, other):
        if other is Ellipsis:
            return _PendingSkip(self)

        return And(
            [self, whitespaces.CURRENT.normalize(other)], whitespaces.CURRENT
        ).streamline()

    def check_recursion(self, seen=empty_tuple):
        subRecCheckList = seen + (self,)
        for e in self.exprs:
            e.check_recursion(subRecCheckList)
            if e.min_length():
                return

    def reverse(self):
        return And(
            [e.reverse() for e in self.exprs[::-1]], self.parser_config.whitespace
        )

    def __regex__(self):
        if self.whitespace is whitespaces.NO_WHITESPACE:
            return "+", "".join(regex_iso(*e.__regex__(), "+") for e in self.exprs)

        return (
            "+",
            regex_iso(*self.whitespace.__regex__(), "+").join(
                regex_iso(*e.__regex__(), "+") for e in self.exprs
            ),
        )

    def __str__(self):
        if self.parser_name:
            return self.parser_name

        subs = [text(e) for e in self.exprs]
        if all(len(s) == 1 for s in subs):
            return "".join(subs)
        else:
            return " + ".join(
                "{" + text(e) + "}" if isinstance(e, MatchFirst) else text(e)
                for e in self.exprs
            )


class Or(ParseExpression):
    """
    Requires that at least one `ParseExpression` is found. If
    two expressions match, the expression that matches the longest
    string will be used. May be constructed using the ``'^'``
    operator.
    """

    __slots__ = ["alternate"]

    def __init__(self, exprs):
        ParseExpression.__init__(self, exprs)
        self.alternate = self.exprs

    def copy(self):
        output = ParseExpression.copy(self)
        output.alternate = self.alternate
        return output

    def _min_length(self):
        return min(e.min_length() for e in self.exprs)

    def streamline(self):
        if self.streamlined:
            return self

        output = ParseExpression.streamline(self)

        if not isinstance(output, ParseExpression):
            return output
        if not output.is_annotated():
            if len(output.exprs) == 0:
                output = Empty()
            if len(output.exprs) == 1:
                output = output.exprs[0]
                if not isinstance(output, ParseExpression):
                    return output

        output.alternate = faster(output.exprs)

        output.streamlined = True
        output.check_recursion()
        return output

    @property
    def whitespace(self):
        return [e.whitespace for e in self.exprs]

    def parse_impl(self, string, start, do_actions=True):
        failures = []
        # THE LONGEST MATCH WINS; TIES GO TO THE FIRST ALTERNATIVE
        best = None

        for e in self.alternate:
            if isinstance(e, Fast):
                for ee in e.get_short_list(string, start):
                    result = ee._parse(string, start, do_actions)
                    if result.failed:
                        failures.append(result)
                    elif best is None or result.end > best.end:
                        best = result
            else:
                result = e._parse(string, start, do_actions)
                if result.failed:
                    failures.append(result)
                elif best is None or result.end > best.end:
                    best = result

        if best is None:
            return failure(
                self,
                start,
                string,
                msg="no defined alternatives to match",
                cause=failures,
            )

        failures.extend(best.failures)
        return ParseResults(self, best.start, best.end, [best], failures)

    def _compile(self):
        rows = tuple(
            (None,) + e.compile_lookup()
            if isinstance(e, Fast)
            else (e.compile(), None, None)
            for e in self.alternate
        )

        def parse(string, start):
            # THE LONGEST MATCH WINS; TIES GO TO THE FIRST ALTERNATIVE
            best = None
            for child, regex, lookup in rows:
                if child is None:
                    found = regex.match(string, start)
                    if not found:
                        continue
                    for shortlisted in lookup.get(found.group(0).lower(), ()):
                        result = shortlisted(string, start)
                        if not result.failed and (
                            best is None or result.end > best.end
                        ):
                            best = result
                    continue
                result = child(string, start)
                if not result.failed and (best is None or result.end > best.end):
                    best = result

            if best is None:
                return FAIL
            return ParseResults(self, best.start, best.end, [best], [])

        return parse

    def check_recursion(self, seen=empty_tuple):
        seen_more = seen + (self,)
        for e in self.exprs:
            e.check_recursion(seen_more)

    def __regex__(self):
        return (
            "|",
            "|".join(
                regex_iso(*e.__regex__(), "|")
                for e in self.exprs
                if not isinstance(e, Empty)
            ),
        )

    def __str__(self):
        if self.parser_name:
            return self.parser_name

        return "{" + " ^ ".join(text(e) for e in self.exprs) + "}"


class MatchFirst(ParseExpression):
    """
    Requires that at least one `ParseExpression` is found. If
    two expressions match, the first one listed is the one that will
    match. May be constructed using the `|` operator.
    """

    __slots__ = ["alternate", "transparent"]

    def __init__(self, exprs):
        ParseExpression.__init__(self, exprs)
        self.alternate = self.exprs
        self.transparent = False

    def copy(self):
        output = ParseExpression.copy(self)
        output.alternate = self.alternate
        output.transparent = False
        return output

    def _min_length(self):
        if self.exprs:
            return min(e.min_length() for e in self.exprs)
        else:
            Log.warning("expecting streamline")
            return 0

    @property
    def whitespace(self):
        return [e.whitespace for e in self.exprs]

    def parse_impl(self, string, start, do_actions=True):
        failures = []

        for e in self.alternate:
            result = e._parse(string, start, do_actions)
            if result.failed:
                failures.append(result)
                continue
            if (
                self.transparent
                and not result._type.token_name
                and not isinstance(result.type, Group)
                and not exceptions.DIAGNOSTICS
            ):
                # THE WRAPPER IS ONLY VISIBLE AT THE ROOT OF A LOOKUP
                return result
            failures.extend(result.failures)
            return ParseResults(self, result.start, result.end, [result], failures)

        return failure(self, start, string, cause=failures)

    def _compile(self):
        children = tuple(e.compile() for e in self.alternate)
        if self.transparent:

            def parse_transparent(string, start):
                for child in children:
                    result = child(string, start)
                    if result.failed:
                        continue
                    if not result._type.token_name and not isinstance(
                        result.type, Group
                    ):
                        # THE WRAPPER IS ONLY VISIBLE AT THE ROOT OF A LOOKUP
                        return result
                    return ParseResults(self, result.start, result.end, [result], [])
                return FAIL

            return parse_transparent

        def parse(string, start):
            for child in children:
                result = child(string, start)
                if result.failed:
                    continue
                return ParseResults(self, result.start, result.end, [result], [])
            return FAIL

        return parse

    def streamline(self):
        if self.streamlined:
            return self

        output = ParseExpression.streamline(self)

        if isinstance(output, Empty):
            return output
        if not output.is_annotated():
            if len(output.exprs) == 0:
                return Empty()
            if len(output.exprs) == 1:
                return output.exprs[0]

        output.alternate = faster(output.exprs)
        output.transparent = not output.parse_action and not output.token_name

        output.streamlined = True
        output.check_recursion()
        return output

    def check_recursion(self, seen=empty_tuple):
        seen_more = seen + (self,)
        for e in self.exprs:
            e.check_recursion(seen_more)

    def __or__(self, other):
        if other is Ellipsis:
            return _PendingSkip(Optional(self))

        return MatchFirst([self, whitespaces.CURRENT.normalize(other)]).streamline()

    def __ror__(self, other):
        return whitespaces.CURRENT.normalize(other) | self

    def __regex__(self):
        return (
            "|",
            "|".join(
                regex_iso(*e.__regex__(), "|")
                for e in self.exprs
                if not isinstance(e, Empty)
            ),
        )

    def __str__(self):
        if self.parser_name:
            return self.parser_name

        return " | ".join("{" + text(e) + "}" for e in self.exprs)


def faster(exprs):
    """
    BUILD A LOOKUP ARRAY TO MATCH ANY OF THE GIVEN exprs
    PERFORMS A REGEX, AND USES THE lower() CHARACTERS TO JUMP TO A SHORTLIST OF exprs THAT CAN MATCH
    :param exprs:
    :return: LESS EXPRESSIONS
    """

    if len(exprs) == 1:
        return exprs

    alternating = []
    # SOME NUMBER OF CONSTANT PATTERNS
    acc = []
    out = []
    has_expecting = True
    for o in exprs:
        p = o.expecting()
        if has_expecting:
            if p:
                acc.append(p)
                out.append(o)
            else:
                try:
                    e = Fast(acc)
                    alternating.append(e)
                except Exception as c:
                    alternating.extend(out)
                acc = []
                out = []
                alternating.append(o)
                has_expecting = False
        elif p:
            acc = [p]
            out = [o]
            has_expecting = True
        else:
            alternating.append(o)

    if has_expecting:
        try:
            e = Fast(acc)
            alternating.append(e)
        except Exception as cause:
            alternating.extend(out)
    return alternating


def _distinct(a, b):
    """
    ASSUME a != b
    RETURN MINIMUM length SO THAT a[:length] != b[:length]
    """
    ii = 1
    for aa, bb in zip(a, b):
        if aa != bb:
            return ii
        ii += 1
    return ii


class Fast(ParserElement):
    __slots__ = ["lookup", "regex", "expecting_message"]

    def __init__(self, maps):
        ParserElement.__init__(self)

        all_keys = set()
        lookup = OrderedDict()
        for m in maps:
            for k, ee in m.items():
                k = k.lower()
                all_keys.add(k)
                lookup.setdefault(k, []).extend(ee)

        # patterns must be mutually exclusive to work
        items = list(lookup.items())
        if len(maps) - max(len(v) for k, v in items) <= 1:
            Log.error("not useful")

        compact = []
        for k, e in items:
            min_k = k
            # FIND SHORTEST PREFIX
            for kk, ee in items:
                if ee and min_k.startswith(kk):
                    min_k = kk
            # COLLECT
            acc = []
            for kk, ee in items:
                if kk.startswith(min_k):
                    acc.extend(ee)
                    ee.clear()
            if acc:
                compact.append((min_k, acc))
        if len(maps) - max(len(v) for k, v in compact) <= 1:
            Log.error("not useful")

        # patterns can be shortened so far as they remain exclusive
        shorter = [
            (k[:min_length], e)
            for k, e in sorted(compact, key=lambda p: p[0])
            for min_length in [max(_distinct(k, kk) for kk, _ in compact if kk != k)]
        ]

        self.lookup = {k: e for k, e in shorter}
        self.regex = regex_compile("|".join(regex_caseless(k) for k, _ in shorter))
        self.expecting_message = "expecting one of " + json.dumps(sorted(all_keys))

    def get_short_list(self, string, start):
        """
        USE THE LOOKUP FEATURE TO FIND THE FEW ParserElements THAT CAN MATCH
        """
        found = self.regex.match(string, start)
        if found:
            index = found.group(0).lower()
            return self.lookup[index]
        return []

    def parse_impl(self, string, start, do_actions=True):
        found = self.regex.match(string, start)
        if found:
            index = found.group(0).lower()
            if index not in self.lookup:
                return failure(self, start, string, self.expecting_message)
            exprs = self.lookup[index]

            causes = []
            for e in exprs:
                result = e._parse(string, start, do_actions)
                if not result.failed:
                    return result
                causes.append(result)

            return failure(self, start, string, cause=causes)
        else:
            return failure(self, start, string, self.expecting_message)

    def compile_lookup(self):
        """RETURN (regex, {first characters: compiled shortlist})"""
        return (
            self.regex,
            {k: tuple(e.compile() for e in exprs) for k, exprs in self.lookup.items()},
        )

    def _compile(self):
        regex, lookup = self.compile_lookup()

        def parse(string, start):
            found = regex.match(string, start)
            if not found:
                return FAIL
            for child in lookup.get(found.group(0).lower(), ()):
                result = child(string, start)
                if not result.failed:
                    return result
            return FAIL

        return parse


class MatchAll(ParseExpression):
    """
    Requires all given `ParseExpression` s to be found, but in
    any order. Expressions may be separated by whitespace.

    May be constructed using the ``'&'`` operator.
    """

    __slots__ = []
    Config = append_config(ParseExpression, "min_match", "max_match", "whitespace")

    def __init__(self, exprs):
        """
        :param exprs: The expressions to be matched
        :param mins: list of integers indincating any minimums
        """
        ParseExpression.__init__(self, exprs)
        self.set_config(
            whitespace=whitespaces.CURRENT,
            min_match=[
                e.parser_config.min_match if isinstance(e, Many) else 1 for e in exprs
            ],
            max_match=[
                e.parser_config.max_match if isinstance(e, Many) else 1 for e in exprs
            ],
        )

    def streamline(self):
        if self.streamlined:
            return self
        output = ParseExpression.streamline(self)
        output.set_config(
            min_match=[
                e.parser_config.min_match if isinstance(e, Many) else 1
                for e in output.exprs
            ],
            max_match=[
                e.parser_config.max_match if isinstance(e, Many) else 1
                for e in output.exprs
            ],
        )
        return output

    def _min_length(self):
        # TODO: MAY BE TOO CONSERVATIVE, WE MAY BE ABLE TO PROVE self CAN CONSUME A CHARACTER
        return min(e.min_length() for e in self.exprs)

    @property
    def whitespace(self):
        return [e.whitespace for e in self.exprs]

    def parse_impl(self, string, start, do_actions=True):
        end = start
        match_order = []
        todo = list(zip(
            self.exprs, self.parser_config.min_match, self.parser_config.max_match
        ))
        count = [0] * len(self.exprs)
        failures = []
        while todo:
            for i, (c, (e, mi, ma)) in enumerate(zip(count, todo)):
                result = e._parse(string, end)
                if result.failed:
                    failures.append(result)
                    continue
                failures.extend(result.failures)
                loc = result.end
                if loc == end:
                    continue
                end = self.parser_config.whitespace.skip(string, loc)
                c2 = count[i] = c + 1
                if c2 >= ma:
                    del todo[i]
                    del count[i]
                match_order.append(e)
                break
            else:
                break

        for c, (e, mi, ma) in zip(count, todo):
            if c < mi:
                if not exceptions.DIAGNOSTICS:
                    return FAIL
                return failure(
                    self,
                    start,
                    string,
                    "Missing minimum (%i) more required elements (%s)" % (mi, e),
                    cause=failures,
                )

        found = set(id(m) for m in match_order)
        missing = [
            e
            for e, mi in zip(self.exprs, self.parser_config.min_match)
            if id(e) not in found and mi > 0
        ]
        if missing:
            if not exceptions.DIAGNOSTICS:
                return FAIL
            missing = ", ".join(text(e) for e in missing)
            return failure(
                self,
                start,
                string,
                f"Missing one or more required elements ({missing})",
                failures,
            )

        # add any unmatched Optionals, in case they have default values defined
        match_order += [e for e in self.exprs if id(e) not in found]

        if not match_order:
            return ParseResults(self, start, start, [], failures)

        # TODO: CAN WE AVOID THIS RE-PARSE?
        results = []
        end = start
        for e in match_order:
            result = e._parse(string, end, do_actions)
            if result.failed:
                return result
            end = self.parser_config.whitespace.skip(string, result.end)
            results.append(result)

        return ParseResults(self, results[0].start, results[-1].end, results, failures)

    def _compile(self):
        plan = tuple(
            (e, e.compile(), mi, ma)
            for e, mi, ma in zip(
                self.exprs, self.parser_config.min_match, self.parser_config.max_match
            )
        )
        skip = self.parser_config.whitespace.skip

        def parse(string, start):
            end = start
            match_order = []
            todo = list(plan)
            count = [0] * len(plan)
            while todo:
                for i, (c, (e, child, mi, ma)) in enumerate(zip(count, todo)):
                    result = child(string, end)
                    if result.failed:
                        continue
                    loc = result.end
                    if loc == end:
                        continue
                    end = skip(string, loc)
                    c2 = count[i] = c + 1
                    if c2 >= ma:
                        del todo[i]
                        del count[i]
                    match_order.append((e, child))
                    break
                else:
                    break

            for c, (e, child, mi, ma) in zip(count, todo):
                if c < mi:
                    return FAIL

            found = set(id(m) for m, _ in match_order)
            if any(id(e) not in found and mi > 0 for e, _, mi, _ in plan):
                return FAIL

            # add any unmatched Optionals, in case they have default values defined
            match_order += [(e, child) for e, child, _, _ in plan if id(e) not in found]

            if not match_order:
                return ParseResults(self, start, start, [], [])

            # TODO: CAN WE AVOID THIS RE-PARSE?
            results = []
            end = start
            for e, child in match_order:
                result = child(string, end)
                if result.failed:
                    return result
                end = skip(string, result.end)
                results.append(result)

            return ParseResults(self, results[0].start, results[-1].end, results, [])

        return parse

    def __str__(self):
        if self.parser_name:
            return self.parser_name

        return "{" + " & ".join(text(e) for e in self.exprs) + "}"


export("mo_parsing.core", And)
export("mo_parsing.core", Or)
export("mo_parsing.core", MatchAll)
export("mo_parsing.core", MatchFirst)
export("mo_parsing.exceptions", MatchFirst)
