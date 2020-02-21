# encoding: utf-8
from collections import MutableMapping
from copy import copy

from mo_logs import Log

from mo_parsing.utils import PY_3, _ustr, __compat__

Suppress, ParserElement, Forward, Group, Dict, Token = [None] * 6

_get = object.__getattribute__


def get_name(tok):
    try:
        if isinstance(tok, Forward):
            return tok.type_for_result.expr.resultsName
        if isinstance(tok, ParseResults):
            return _get(tok, "type_for_result").resultsName
        return None
    except Exception as e:
        raise e


class ParseResults(object):
    """Structured parse results, to provide multiple means of access to
    the parsed data:

       - as a list (``len(results)``)
       - by list index (``results[0], results[1]``, etc.)
       - by attribute (``results.<resultsName>`` - see :class:`ParserElement.setResultsName`)

    Example::(pars

        integer = Word(nums)
        date_str = (integer.setResultsName("year") + '/'
                        + integer.setResultsName("month") + '/'
                        + integer.setResultsName("day"))
        # equivalent form:
        # date_str = integer("year") + '/' + integer("month") + '/' + integer("day")

        # parseString returns a ParseResults object
        result = date_str.parseString("1999/12/31")

        def test(s, fn=repr):
            print("%s -> %s" % (s, fn(eval(s))))
        test("list(result)")
        test("result[0]")
        test("result['month']")
        test("result.day")
        test("'month' in result")
        test("'minutes' in result")
        test("result", str)

    prints::

        list(result) -> ['1999', '/', '12', '/', '31']
        result[0] -> '1999'
        result['month'] -> '12'
        result.day -> '31'
        'month' in result -> True
        'minutes' in result -> False
        result -> ['1999', '/', '12', '/', '31']
        - day: 31
        - month: 12
        - year: 1999
    """

    __slots__ = ["tokens_for_result", "type_for_result", "replaced_tokens"]

    @property
    def name_for_result(self):
        return get_name(self)

    # Performance tuning: we construct a *lot* of these, so keep this
    # constructor as small and fast as possible
    def __init__(self, result_type, toklist=None):
        if not isinstance(result_type, ParserElement):
            Log.error("not expected")
        if isinstance(result_type, Forward):
            Log.error("not expected")
        if isinstance(toklist, ParseResults) or not isinstance(toklist, (list, tuple)):
            Log.error("no longer accepted")

        self.tokens_for_result = toklist
        self.type_for_result = result_type
        self.replaced_tokens = None

    def _get_item_by_name(self, i):
        # return open list of (modal, value) pairs
        # modal==True means only the last value is relevant
        if not __compat__.collect_all_And_tokens:
            # pre 2.3
            if self.name_for_result == i:
                yield self.type_for_result.parser_config.modalResults, list(self)
            else:
                for tok in self.tokens_for_result:
                    if get_name(tok) == i:
                        yield tok.type_for_result.parser_config.modalResults, list(self)
        else:
            name = get_name(self)
            if name == i:
                if isinstance(self.type_for_result, Group):
                    yield self.type_for_result.parser_config.modalResults, self
                elif len(self.tokens_for_result) == 1:
                    yield self.type_for_result.parser_config.modalResults, self.tokens_for_result[
                        0
                    ]
                else:
                    yield self.type_for_result.parser_config.modalResults, self
            elif not name:
                for tok in self.tokens_for_result:
                    if isinstance(tok, ParseResults):
                        for f in tok._get_item_by_name(i):
                            yield f

    def __getitem__(self, i):
        if not __compat__.collect_all_And_tokens:
            # pre 2.3
            if isinstance(i, int):
                if isinstance(self.type_for_result, Group):
                    return self.tokens_for_result[0][i]
                else:
                    for ii, v in enumerate(self):
                        if i == ii:
                            return v
            elif self.name_for_result == i:
                mv = tuple(zip(*self._get_item_by_name(i)))
                if not mv:
                    return ""  # TODO:  Make this None?
                modals, values = mv
                if any(modals) != all(modals):
                    Log.error("complicated modal rules")
                elif modals[0]:
                    return values[-1]
                else:
                    return ParseResults(self.type_for_result, values)
            else:
                for tok in self.tokens_for_result:
                    if get_name(tok) == i:
                        return tok[0]
        else:
            if isinstance(i, int):
                if self.replaced_tokens is not None:
                    return self.replaced_tokens[i]

                if i < 0:
                    i = len(self) + i
                for ii, v in enumerate(self):
                    if i == ii:
                        return v
            elif isinstance(i, slice):
                if self.replaced_tokens is not None:
                    return self.replaced_tokens[i]
                return list(iter(self))[i]
            else:
                mv = tuple(zip(*self._get_item_by_name(i)))
                if not mv:
                    return ""  # TODO:  Make this None?
                modals, values = mv
                if any(modals) != all(modals):
                    Log.error("complicated modal rules")
                elif modals[0]:
                    return values[-1]
                else:
                    return ParseResults(self.type_for_result, values)
        # Log.error("No name by {{name|quote}}", name=i)

    def __setitem__(self, k, v):
        if isinstance(k, slice):
            if k.start is None and k.stop is None and k.step is None:
                self.replaced_tokens = v
            else:
                Log.error("do not know how to handle")
            return
        elif isinstance(k, int):
            if self.replaced_tokens is None:
                self.replaced_tokens = list(self)
            self.replaced_tokens[k] = v
            # for i, t in enumerate(self.tokens_for_result):
            #     if isinstance(t, ParseResults):
            #         ii = len(t)
            #         if k < ii:
            #             t[k] = v
            #             return
            #         else:
            #             k -= ii
            #     else:
            #         if k == 0:
            #             self.tokens_for_result[i] = v
            #             return
            #         else:
            #             k -= 1
            #
            # Log.error("index {{index}} beyond existing tokens", index=k)
        else:
            for i, vv in enumerate(self.tokens_for_result):
                if get_name(vv) == k:
                    self.tokens_for_result[i] = v
                    break
            else:
                self.tokens_for_result.append(Annotation(k, [v]))

    def __contains__(self, k):
        return any(get_name(r) == k for r in self.tokens_for_result)

    def __len__(self):
        if isinstance(self.type_for_result, Group):
            return len(self.tokens_for_result[0])
        else:
            return sum(1 for t in self)

    def __bool__(self):
        return not not self.tokens_for_result

    __nonzero__ = __bool__

    def __iter__(self):
        if self.replaced_tokens is not None:
            for t in self.replaced_tokens:
                yield t
            return
        if isinstance(self, Annotation):
            return
            # yield self
        elif isinstance(self.type_for_result, Suppress):
            return
        else:
            for r in self.tokens_for_result:
                if isinstance(r, ParseResults):
                    if isinstance(r, Annotation):
                        return
                    elif isinstance(r.type_for_result, Group):
                        yield r
                    # elif get_name(r):
                    #     yield r
                    elif not isinstance(r.type_for_result, Group):
                        for mm in r:
                            yield mm
                else:
                    yield r

    def _del_item_by_index(self, index):
        for i, t in enumerate(self.tokens_for_result):
            if isinstance(t.type_for_result, (Group, Token)):
                if index < 1:
                    del self.tokens_for_result[i]
                    name = get_name(t)
                    if name:
                        if not isinstance(t.type_for_result, Annotation):
                            self.tokens_for_result.append(
                                Annotation(name, t.tokens_for_result)
                            )
                    return
                else:
                    index -= 1
                continue
            elif isinstance(t, Annotation):
                return
            elif index < len(t):
                t._del_item_by_index(index)
                return
            else:
                index -= len(t)

    def __delitem__(self, key):
        if isinstance(key, (int, slice)):
            if self.replaced_tokens is None:
                self.replaced_tokens = list(self)
            del self.replaced_tokens[key]
        else:
            if key == self.name_for_result:
                new_type = copy(self.type_for_result)
                new_type.resultsName = None
                self.type_for_result = new_type
                return
            for i, t in enumerate(self.tokens_for_result):
                name = get_name(t)
                if name == key:
                    new_type = copy(t.type_for_result)
                    new_type.resultsName = None
                    t.type_for_result = new_type
                    return
                elif not isinstance(t, ParseResults):
                    pass
                elif isinstance(t.type_for_result, (Group, Token)):
                    pass
                else:
                    del t[key]

    def __reversed__(self):
        return reversed(self.tokens_for_result)

    def iterkeys(self):
        for k, _ in self.iteritems():
            yield k

    def itervalues(self):
        for _, v in self.iteritems():
            yield v

    def iteritems(self):
        output = {}
        for r in self.tokens_for_result:
            if isinstance(r, ParseResults):
                name = get_name(r)
                if name:
                    add(output, name, [r])
                if isinstance(r.type_for_result, Group):
                    continue
                for k, v in r.iteritems():
                    add(output, k, [v])
        for k, v in output.items():
            yield k, v

    if PY_3:
        keys = iterkeys
        """Returns an iterator of all named result keys."""

        values = itervalues
        """Returns an iterator of all named result values."""

        items = iteritems
        """Returns an iterator of all named result key-value tuples."""

    else:

        def keys(self):
            """Returns all named result keys (as a list in Python 2.x, as an iterator in Python 3.x)."""
            return list(self.iterkeys())

        def values(self):
            """Returns all named result values (as a list in Python 2.x, as an iterator in Python 3.x)."""
            return list(self.itervalues())

        def items(self):
            """Returns all named result key-values (as a list of tuples in Python 2.x, as an iterator in Python 3.x)."""
            return list(self.iteritems())

    def haskeys(self):
        """Since keys() returns an iterator, this method is helpful in bypassing
           code that looks for the existence of any defined results names."""
        return any(get_name(r) for r in self.tokens_for_result)

    def pop(self, index=-1, default=None):
        """
        Removes and returns item at specified index (default= ``last``).
        Supports both ``list`` and ``dict`` semantics for ``pop()``. If
        passed no argument or an integer argument, it will use ``list``
        semantics and pop tokens from the list of parsed tokens. If passed
        a non-integer argument (most likely a string), it will use ``dict``
        semantics and pop the corresponding value from any defined results
        names. A second default return value argument is supported, just as in
        ``dict.pop()``.

        Example::

            def remove_first(tokens):
                tokens.pop(0)
            print(OneOrMore(Word(nums)).parseString("0 123 321")) # -> ['0', '123', '321']
            print(OneOrMore(Word(nums)).addParseAction(remove_first).parseString("0 123 321")) # -> ['123', '321']

            label = Word(alphas)
            patt = label("LABEL") + OneOrMore(Word(nums))
            print(patt.parseString("AAB 123 321"))

            # Use pop() in a parse action to remove named result (note that corresponding value is not
            # removed from list form of results)
            def remove_LABEL(tokens):
                tokens.pop("LABEL")
                return tokens
            patt.addParseAction(remove_LABEL)
            print(patt.parseString("AAB 123 321"))

        prints::

            ['AAB', '123', '321']
            - LABEL: AAB

            ['AAB', '123', '321']
        """
        ret = self[index]
        del self[index]
        return ret if ret else default

    def get(self, key, defaultValue=None):
        """
        Returns named result matching the given key, or if there is no
        such name, then returns the given ``defaultValue`` or ``None`` if no
        ``defaultValue`` is specified.

        Similar to ``dict.get()``.

        Example::

            integer = Word(nums)
            date_str = integer("year") + '/' + integer("month") + '/' + integer("day")

            result = date_str.parseString("1999/12/31")
            print(result.get("year")) # -> '1999'
            print(result.get("hour", "not specified")) # -> 'not specified'
            print(result.get("hour")) # -> None
        """
        if key in self:
            return self[key]
        else:
            return defaultValue

    def insert(self, index, insStr):
        """
        Inserts new element at location index in the list of parsed tokens.

        Similar to ``list.insert()``.

        Example::

            print(OneOrMore(Word(nums)).parseString("0 123 321")) # -> ['0', '123', '321']

            # use a parse action to insert the parse location in the front of the parsed results
            def insert_locn(locn, tokens):
                tokens.insert(0, locn)
            print(OneOrMore(Word(nums)).addParseAction(insert_locn).parseString("0 123 321")) # -> [0, '0', '123', '321']
        """
        if self.replaced_tokens is None:
            self.replaced_tokens = list(self)
        self.replaced_tokens.insert(index, insStr)

    def append(self, item):
        """
        Add single element to end of ParseResults list of elements.

        Example::

            print(OneOrMore(Word(nums)).parseString("0 123 321")) # -> ['0', '123', '321']

            # use a parse action to compute the sum of the parsed integers, and add it to the end
            def append_sum(tokens):
                tokens.append(sum(map(int, tokens)))
            print(OneOrMore(Word(nums)).addParseAction(append_sum).parseString("0 123 321")) # -> ['0', '123', '321', 444]
        """
        if self.replaced_tokens is None:
            self.replaced_tokens = list(self)
        self.replaced_tokens.append(item)

    def extend(self, itemseq):
        """
        Add sequence of elements to end of ParseResults list of elements.

        Example::

            patt = OneOrMore(Word(alphas))

            # use a parse action to append the reverse of the matched strings, to make a palindrome
            def make_palindrome(tokens):
                tokens.extend(reversed([t[::-1] for t in tokens]))
                return ''.join(tokens)
            print(patt.addParseAction(make_palindrome).parseString("lskdj sdlkjf lksd")) # -> 'lskdjsdlkjflksddsklfjkldsjdksl'
        """
        if self.replaced_tokens is None:
            self.replaced_tokens = list(self)
        if isinstance(itemseq, ParseResults):
            self.__iadd__(itemseq)
        else:
            self.replaced_tokens.extend(itemseq)

    def clear(self):
        """
        Clear all elements and results names.
        """
        self.replaced_tokens = []

    def __contains__(self, item):
        return bool(self[item])

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            return ""

    def __add__(self, other):
        return ParseResults(
            Group(None), self.tokens_for_result + other.tokens_for_result
        )

    def __radd__(self, other):
        if not other:
            return self
        Log.error("not expected")
        ret = copy(self)
        ret += other
        return ret

    def __iadd__(self, other):
        if self.replaced_tokens is None:
            self.replaced_tokens = list(self)
        self.replaced_tokens.append(other)
        return self

    def __repr__(self):
        try:
            return repr(self.tokens_for_result)
        except Exception as e:
            Log.warning("problem", cause=e)
            return "[]"

    def __str__(self):
        # if len(self.tokens_for_result) == 1:
        #     return str(self.tokens_for_result[0])

        return (
            "["
            + ", ".join(
                _ustr(v) if isinstance(v, ParseResults) else repr(v)
                for v in self.tokens_for_result
            )
            + "]"
        )

    def _asStringList(self):
        for t in self:
            if isinstance(t, ParseResults):
                for s in t._asStringList():
                    yield s
            else:
                yield t

    def asString(self, sep=""):
        return sep.join(self._asStringList())

    def asList(self):
        """
        Returns the parse results as a nested list of matching tokens, all converted to strings.

        Example::

            patt = OneOrMore(Word(alphas))
            result = patt.parseString("sldkj lsdkj sldkj")
            # even though the result prints in string-like form, it is actually a mo_parsing ParseResults
            print(type(result), result) # -> <class 'mo_parsing.ParseResults'> ['sldkj', 'lsdkj', 'sldkj']

            # Use asList() to create an actual list
            result_list = result.asList()
            print(type(result_list), result_list) # -> <class 'list'> ['sldkj', 'lsdkj', 'sldkj']
        """

        def internal(obj, depth):
            # RETURN AN OPEN LIST
            if depth > 60:
                Log.warning("deep!")

            if isinstance(obj, Annotation):
                return []
            elif isinstance(obj, ParseResults):
                if obj.replaced_tokens:
                    return [
                        simpler(internal(o, depth + 1)) for o in obj.replaced_tokens
                    ]
                output = []
                for t in obj.tokens_for_result:
                    inner = internal(t, depth + 1)
                    output.extend(inner)
                if isinstance(obj.type_for_result, Group):
                    return [output]
                else:
                    return output
            else:
                return [obj]

        output = internal(self, 0)
        # if isinstance(self.type_for_result, Group):
        #     return simpler(output)
        # else:
        return output

    def asDict(self):
        """
        Returns the named parse results as a nested dictionary.

        Example::

            integer = Word(nums)
            date_str = integer("year") + '/' + integer("month") + '/' + integer("day")

            result = date_str.parseString('12/31/1999')
            print(type(result), repr(result)) # -> <class 'mo_parsing.ParseResults'> (['12', '/', '31', '/', '1999'], {'day': [('1999', 4)], 'year': [('12', 0)], 'month': [('31', 2)]})

            result_dict = result.asDict()
            print(type(result_dict), repr(result_dict)) # -> <class 'dict'> {'day': '1999', 'year': '12', 'month': '31'}

            # even though a ParseResults supports dict-like access, sometime you just need to have a dict
            import json
            print(json.dumps(result)) # -> Exception: TypeError: ... is not JSON serializable
            print(json.dumps(result.asDict())) # -> {"month": "31", "day": "1999", "year": "12"}
        """

        def pack(objs):
            # return an open dict, if possible
            # otherwise return an open list
            open_list = []
            open_dict = {}
            for obj in objs:
                if isinstance(obj, ParseResults):
                    name = get_name(obj)
                    if name:
                        # add(open_dict, name, pack(obj.tokens_for_result))
                        od, ol = pack(obj.tokens_for_result)
                        if isinstance(obj.type_for_result, Group):
                            item = {
                                k: s
                                for k, v in od.items()
                                for s in [simpler(v)]
                                if s is not None
                            } or ol
                            add(open_dict, name, [ol])
                            open_list.append(item)
                        else:
                            add(open_dict, name, ol)
                            for k, v in od.items():
                                add(open_dict, k, v)
                    elif isinstance(obj.type_for_result, Group):
                        od, ol = pack(obj.tokens_for_result)
                        item = {
                            k: s
                            for k, v in od.items()
                            for s in [simpler(v)]
                            if s is not None
                        } or ol
                        open_list.append(item)
                    elif isinstance(obj.type_for_result, Suppress):
                        pass
                    else:
                        od, ol = pack(obj.tokens_for_result)
                        open_list.extend(ol)
                        for k, v in od.items():
                            add(open_dict, k, v)
                else:
                    open_list.append(obj)

            return open_dict, open_list

        od, ol = pack([self])
        if od:
            item = {k: simpler(v) for k, v in od.items()}
            return item
        elif isinstance(self.type_for_result, Group) or get_name(self):
            return ol[0]
        else:
            return ol

    def __copy__(self):
        """
        Returns a new copy of a :class:`ParseResults` object.
        """
        ret = ParseResults(self.type_for_result, list(self.tokens_for_result))
        return ret


    def __lookup(self, sub):
        for name, value in self.tokens_for_result:
            if sub is value:
                return name
        return None

    def getName(self):
        r"""
        Returns the results name for this token expression. Useful when several
        different expressions might match at a particular location.

        Example::

            integer = Word(nums)
            ssn_expr = Regex(r"\d\d\d-\d\d-\d\d\d\d")
            house_number_expr = Suppress('#') + Word(nums, alphanums)
            user_data = (Group(house_number_expr)("house_number")
                        | Group(ssn_expr)("ssn")
                        | Group(integer)("age"))
            user_info = OneOrMore(user_data)

            result = user_info.parseString("22 111-22-3333 #221B")
            for item in result:
                print(item.getName(), ':', item[0])

        prints::

            age : 22
            ssn : 111-22-3333
            house_number : 221B
        """
        if get_name(self):
            return get_name(self)
        elif len(self.tokens_for_result) == 1:
            return get_name(self.tokens_for_result[0])
        else:
            return None

    def __getnewargs__(self):
        old_parser = self.type_for_result
        parser_type = globals().get(old_parser.__class__.__name__, ParserElement)
        new_parser = parser_type(None)
        new_parser.resultsName = old_parser.resultsName
        return new_parser, self.tokens_for_result

    def __dir__(self):
        return dir(type(self)) + list(self.keys())


def simpler(v):
    # convert an open list to object it represents
    if isinstance(v, list):
        if len(v) == 0:
            return None
        elif len(v) == 1:
            return v[0]
    return v


def add(obj, key, value):
    if not isinstance(value, list):
        Log.error("not allowed")

    old_v = obj.get(key)
    if old_v is None:
        obj[key] = value
    else:
        old_v.extend(value)


class Annotation(ParseResults):
    # Append one of these to the parse results to
    # add key: value pair not found in the original text

    __slots__ = []

    def __init__(self, name, value):
        if not isinstance(value, list):
            Log.error("expecting a list")
        ParseResults.__init__(self, Suppress(None)(name), value)
        if len(value) > 1:
            self.type_for_result.parser_config.modalResults = False
        else:
            self.type_for_result.parser_config.modalResults = True

    def __repr__(self):
        return "{" + get_name(self) + ": ...}"


MutableMapping.register(ParseResults)
