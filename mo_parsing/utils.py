# encoding: utf-8
from __future__ import absolute_import, division, unicode_literals

import inspect
import string
import sys
import warnings
from itertools import filterfalse

from mo_future import text, unichr
from mo_logs import Log, Except

_MAX_INT = sys.maxsize
empty_list = []
empty_tuple = tuple()

# build list of single arg builtins, that can be used as parse actions
singleArgBuiltins = [
    sum,
    len,
    sorted,
    reversed,
    list,
    tuple,
    set,
    any,
    all,
    min,
    max,
]

builtin_lookup = {"".join.__name__: ("iterable",)}


def get_function_arguments(func):
    try:
        return func.__code__.co_varnames[: func.__code__.co_argcount]
    except Exception as e:
        return builtin_lookup.get(func.__name__, ("unknown",))




class __config_flags:
    """Internal class for defining compatibility and debugging flags"""

    _all_names = []
    _fixed_names = []
    _type_desc = "configuration"

    @classmethod
    def _set(cls, dname, value):
        if dname in cls._fixed_names:
            warnings.warn(
                "{}.{} {} is {} and cannot be overridden".format(
                    cls.__name__,
                    dname,
                    cls._type_desc,
                    str(getattr(cls, dname)).upper(),
                )
            )
            return
        if dname in cls._all_names:
            setattr(cls, dname, value)
        else:
            raise ValueError("no such {} {!r}".format(cls._type_desc, dname))

    enable = classmethod(lambda cls, name: cls._set(name, True))
    disable = classmethod(lambda cls, name: cls._set(name, False))



alphas = string.ascii_uppercase + string.ascii_lowercase
nums = "0123456789"
hexnums = nums + "ABCDEFabcdef"
alphanums = alphas + nums
_bslash = chr(92)
printables = "".join(c for c in string.printable if c not in string.whitespace)


def col(loc, strg):
    """Returns current column within a string, counting newlines as line separators.
   The first column is number 1.

   Note: the default parsing behavior is to expand tabs in the input string
   before starting the parsing process.  See
   :class:`ParserElement.parseString` for more
   information on parsing strings containing ``<TAB>`` s, and suggested
   methods to maintain a consistent view of the parsed string, the parse
   location, and line and column positions within the parsed string.
   """
    s = strg
    return 1 if 0 < loc < len(s) and s[loc - 1] == "\n" else loc - s.rfind("\n", 0, loc)


def lineno(loc, strg):
    """Returns current line number within a string, counting newlines as line separators.
    The first line is number 1.

    Note - the default parsing behavior is to expand tabs in the input string
    before starting the parsing process.  See :class:`ParserElement.parseString`
    for more information on parsing strings containing ``<TAB>`` s, and
    suggested methods to maintain a consistent view of the parsed string, the
    parse location, and line and column positions within the parsed string.
    """
    return strg.count("\n", 0, loc) + 1


def line(loc, strg):
    """Returns the line of text containing loc within a string, counting newlines as line separators.
       """
    lastCR = strg.rfind("\n", 0, loc)
    nextCR = strg.find("\n", loc)
    if nextCR >= 0:
        return strg[lastCR + 1 : nextCR]
    else:
        return strg[lastCR + 1 :]


"decorator to trim function calls to match the arity of the target"


def wrap_parse_action(func):
    from mo_parsing.exceptions import ParseException
    from mo_parsing.results import ParseResults
    from mo_parsing.enhancement import Group

    if func in singleArgBuiltins:
        return lambda s, l, t: func(t)

    try:
        if func.__class__.__name__ == "staticmethod":
            func = func.__func__
            spec = inspect.getfullargspec(func)

            self_arg = 1 if spec.args and spec.args[0] in ("self", "cls") else 0
            if spec.varargs:
                start = 0
            else:
                start = 3 + self_arg - len(spec.args)
        elif isinstance(func, type):
            # use __init__., assume the self is already bound
            spec = inspect.getfullargspec(func.__init__)
            if spec.varargs:
                start = 0
            else:
                start = 4 - len(spec.args)
        else:
            spec = inspect.getfullargspec(func)

            self_arg = 1 if spec.args and spec.args[0] in ("self", "cls") else 0
            if spec.varargs:
                start = 0
            else:
                start = 3 + self_arg - len(spec.args)
    except Exception as e:
        e = Except.wrap(e)
        func = func.__call__
        spec = inspect.getfullargspec(func)
        self_arg = 1 if spec.args and spec.args[0] == "self" else 0
        if spec.varargs:
            start = 0
        else:
            start = 3 + self_arg - len(spec.args)

    def wrapper(*args):
        try:
            s, i, token = args
            original_type = token.type_for_result
            result = func(*args[start:])
            if result is None:
                return token
            elif isinstance(result, (list, tuple)):
                return ParseResults(original_type, result)
            elif isinstance(result, ParseResults):
                return result
            elif original_type.__class__.__name__ == "Forward":
                return ParseResults(original_type.expr, [result])
            elif isinstance(original_type, Group):
                return ParseResults(original_type.expr, [result])
            else:
                return ParseResults(original_type, [result])
        except Exception as cause:
            if (
                isinstance(cause, TypeError)
                and spec.args[0] == "self"
                and "required positional argument" in cause.args[0]
            ):
                Log.error(
                    "Did you provide a `self` argument to a static function?", cause=cause
                )

            f = ParseException(*args)
            f.__cause__ = cause
            raise f

    # copy func name to wrapper for sensible debug output
    try:
        func_name = getattr(func, "__name__", getattr(func, "__class__").__name__)
    except Exception:
        func_name = str(func)
    wrapper.__name__ = func_name

    return wrapper


def _xml_escape(data):
    """Escape &, <, >, ", ', etc. in a string of data."""

    # ampersand must be replaced first
    from_symbols = "&><\"'"
    to_symbols = ("&" + s + ";" for s in "amp gt lt quot apos".split())
    for from_, to_ in zip(from_symbols, to_symbols):
        data = data.replace(from_, to_)
    return data



def traceParseAction(f):
    """Decorator for debugging parse actions.

    When the parse action is called, this decorator will print
    ``">> entering method-name(line:<current_source_line>, <parse_location>, <matched_tokens>)"``.
    When the parse action completes, the decorator will print
    ``"<<"`` followed by the returned value, or any exception that the parse action raised.

    Example::

        wd = Word(alphas)

        @traceParseAction
        def remove_duplicate_chars(tokens):
            return ''.join(sorted(set(''.join(tokens))))

        wds = OneOrMore(wd).addParseAction(remove_duplicate_chars)
        print(wds.parseString("slkdjs sld sldd sdlf sdljf"))

    prints::

        >>entering remove_duplicate_chars(line: 'slkdjs sld sldd sdlf sdljf', 0, (['slkdjs', 'sld', 'sldd', 'sdlf', 'sdljf'], {}))
        <<leaving remove_duplicate_chars (ret: 'dfjkls')
        ['dfjkls']
    """
    f = wrap_parse_action(f)

    def z(*paArgs):
        thisFunc = f.__name__
        s, l, t = paArgs[-3:]
        if len(paArgs) > 3:
            thisFunc = paArgs[0].__class__.__name__ + "." + thisFunc
        sys.stderr.write(
            ">>entering %s(line: '%s', %d, %r)\n" % (thisFunc, line(l, s), l, t)
        )
        try:
            ret = f(*paArgs)
        except Exception as exc:
            sys.stderr.write("<<leaving %s (exception: %s)\n" % (thisFunc, exc))
            raise
        sys.stderr.write("<<leaving %s (ret: %r)\n" % (thisFunc, ret))
        return ret

    try:
        z.__name__ = f.__name__
    except AttributeError:
        pass
    return z


class _lazyclassproperty(object):
    def __init__(self, fn):
        self.fn = fn
        self.__doc__ = fn.__doc__
        self.__name__ = fn.__name__

    def __get__(self, obj, cls):
        if cls is None:
            cls = type(obj)
        if not hasattr(cls, "_intern") or any(
            cls._intern is getattr(superclass, "_intern", [])
            for superclass in cls.__mro__[1:]
        ):
            cls._intern = {}
        attrname = self.fn.__name__
        if attrname not in cls._intern:
            cls._intern[attrname] = self.fn(cls)
        return cls._intern[attrname]


class unicode_set(object):
    """
    A set of Unicode characters, for language-specific strings for
    ``alphas``, ``nums``, ``alphanums``, and ``printables``.
    A unicode_set is defined by a list of ranges in the Unicode character
    set, in a class attribute ``_ranges``, such as::

        _ranges = [(0x0020, 0x007e), (0x00a0, 0x00ff),]

    A unicode set can also be defined using multiple inheritance of other unicode sets::

        class CJK(Chinese, Japanese, Korean):
            pass
    """

    _ranges = []

    @classmethod
    def _get_chars_for_ranges(cls):
        ret = []
        for cc in cls.__mro__:
            if cc is unicode_set:
                break
            for rr in cc._ranges:
                ret.extend(range(rr[0], rr[-1] + 1))
        return [unichr(c) for c in sorted(set(ret))]

    @_lazyclassproperty
    def printables(cls):
        "all non-whitespace characters in this range"
        return "".join(filterfalse(text.isspace, cls._get_chars_for_ranges()))

    @_lazyclassproperty
    def alphas(cls):
        "all alphabetic characters in this range"
        return "".join(filter(text.isalpha, cls._get_chars_for_ranges()))

    @_lazyclassproperty
    def nums(cls):
        "all numeric digit characters in this range"
        return "".join(filter(text.isdigit, cls._get_chars_for_ranges()))

    @_lazyclassproperty
    def alphanums(cls):
        "all alphanumeric characters in this range"
        return cls.alphas + cls.nums


class parsing_unicode(unicode_set):
    """
    A namespace class for defining common language unicode_sets.
    """

    _ranges = [(32, sys.maxunicode)]

    class Latin1(unicode_set):
        "Unicode set for Latin-1 Unicode Character Range"
        _ranges = [
            (0x0020, 0x007E),
            (0x00A0, 0x00FF),
        ]

    class LatinA(unicode_set):
        "Unicode set for Latin-A Unicode Character Range"
        _ranges = [
            (0x0100, 0x017F),
        ]

    class LatinB(unicode_set):
        "Unicode set for Latin-B Unicode Character Range"
        _ranges = [
            (0x0180, 0x024F),
        ]

    class Greek(unicode_set):
        "Unicode set for Greek Unicode Character Ranges"
        _ranges = [
            (0x0370, 0x03FF),
            (0x1F00, 0x1F15),
            (0x1F18, 0x1F1D),
            (0x1F20, 0x1F45),
            (0x1F48, 0x1F4D),
            (0x1F50, 0x1F57),
            (0x1F59,),
            (0x1F5B,),
            (0x1F5D,),
            (0x1F5F, 0x1F7D),
            (0x1F80, 0x1FB4),
            (0x1FB6, 0x1FC4),
            (0x1FC6, 0x1FD3),
            (0x1FD6, 0x1FDB),
            (0x1FDD, 0x1FEF),
            (0x1FF2, 0x1FF4),
            (0x1FF6, 0x1FFE),
        ]

    class Cyrillic(unicode_set):
        "Unicode set for Cyrillic Unicode Character Range"
        _ranges = [(0x0400, 0x04FF)]

    class Chinese(unicode_set):
        "Unicode set for Chinese Unicode Character Range"
        _ranges = [
            (0x4E00, 0x9FFF),
            (0x3000, 0x303F),
        ]

    class Japanese(unicode_set):
        "Unicode set for Japanese Unicode Character Range, combining Kanji, Hiragana, and Katakana ranges"
        _ranges = []

        class Kanji(unicode_set):
            "Unicode set for Kanji Unicode Character Range"
            _ranges = [
                (0x4E00, 0x9FBF),
                (0x3000, 0x303F),
            ]

        class Hiragana(unicode_set):
            "Unicode set for Hiragana Unicode Character Range"
            _ranges = [
                (0x3040, 0x309F),
            ]

        class Katakana(unicode_set):
            "Unicode set for Katakana  Unicode Character Range"
            _ranges = [
                (0x30A0, 0x30FF),
            ]

    class Korean(unicode_set):
        "Unicode set for Korean Unicode Character Range"
        _ranges = [
            (0xAC00, 0xD7AF),
            (0x1100, 0x11FF),
            (0x3130, 0x318F),
            (0xA960, 0xA97F),
            (0xD7B0, 0xD7FF),
            (0x3000, 0x303F),
        ]

    class CJK(Chinese, Japanese, Korean):
        "Unicode set for combined Chinese, Japanese, and Korean (CJK) Unicode Character Range"
        pass

    class Thai(unicode_set):
        "Unicode set for Thai Unicode Character Range"
        _ranges = [
            (0x0E01, 0x0E3A),
            (0x0E3F, 0x0E5B),
        ]

    class Arabic(unicode_set):
        "Unicode set for Arabic Unicode Character Range"
        _ranges = [
            (0x0600, 0x061B),
            (0x061E, 0x06FF),
            (0x0700, 0x077F),
        ]

    class Hebrew(unicode_set):
        "Unicode set for Hebrew Unicode Character Range"
        _ranges = [
            (0x0590, 0x05FF),
        ]

    class Devanagari(unicode_set):
        "Unicode set for Devanagari Unicode Character Range"
        _ranges = [(0x0900, 0x097F), (0xA8E0, 0xA8FF)]


parsing_unicode.Japanese._ranges = (
    parsing_unicode.Japanese.Kanji._ranges
    + parsing_unicode.Japanese.Hiragana._ranges
    + parsing_unicode.Japanese.Katakana._ranges
)

# define ranges in language character sets
setattr(parsing_unicode, "العربية", parsing_unicode.Arabic)
setattr(parsing_unicode, "中文", parsing_unicode.Chinese)
setattr(parsing_unicode, "кириллица", parsing_unicode.Cyrillic)
setattr(parsing_unicode, "Ελληνικά", parsing_unicode.Greek)
setattr(parsing_unicode, "עִברִית", parsing_unicode.Hebrew)
setattr(parsing_unicode, "日本語", parsing_unicode.Japanese)
setattr(parsing_unicode.Japanese, "漢字", parsing_unicode.Japanese.Kanji)
setattr(parsing_unicode.Japanese, "カタカナ", parsing_unicode.Japanese.Katakana)
setattr(parsing_unicode.Japanese, "ひらがな", parsing_unicode.Japanese.Hiragana)
setattr(parsing_unicode, "한국어", parsing_unicode.Korean)
setattr(parsing_unicode, "ไทย", parsing_unicode.Thai)
setattr(parsing_unicode, "देवनागरी", parsing_unicode.Devanagari)

