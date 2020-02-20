# encoding: utf-8
from __future__ import absolute_import, division, unicode_literals

import inspect
import string
import sys
import warnings

from mo_logs import Log

def noop(*args):
    return



try:
    # Python 3
    from itertools import filterfalse
except ImportError:
    from itertools import ifilterfalse as filterfalse

try:
    from _thread import RLock
except ImportError:
    from threading import RLock

try:
    # Python 3
    from collections.abc import Iterable
    from collections.abc import MutableMapping, Mapping
    from collection import deque
except ImportError:
    # Python 2.7
    from collections import Iterable
    from collections import MutableMapping, Mapping, deque

system_version = tuple(sys.version_info)[:3]
PY_3 = system_version[0] == 3
if PY_3:
    _MAX_INT = sys.maxsize
    basestring = str
    unichr = chr
    unicode = str
    _ustr = str

    # build list of single arg builtins, that can be used as parse actions
    singleArgBuiltins = [sum, len, sorted, reversed, list, tuple, set, any, all, min, max]

    builtin_lookup = {"".join.__name__: ("iterable",)}

    def get_function_arguments(func):
        try:
            return func.__code__.co_varnames[:func.__code__.co_argcount]
        except Exception as e:
            return builtin_lookup.get(func.__name__, ("unknown",))

else:
    from __builtin__ import unicode

    _MAX_INT = sys.maxint
    range = xrange
    basestring = basestring
    unichr = unichr


    def _ustr(obj):
        """Drop-in replacement for str(obj) that tries to be Unicode
        friendly. It first tries str(obj). If that fails with
        a UnicodeEncodeError, then it tries unicode(obj). It then
        < returns the unicode object | encodes it with the default
        encoding | ... >.
        """
        if isinstance(obj, unicode):
            return obj

        try:
            # If this works, then _ustr(obj) has the same behaviour as str(obj), so
            # it won't break any existing code.
            return str(obj)

        except UnicodeEncodeError:
            # Else encode it
            from mo_parsing import Regex
            ret = unicode(obj).encode(sys.getdefaultencoding(), 'xmlcharrefreplace')
            xmlcharref = Regex(r'&#\d+;')
            xmlcharref.setParseAction(lambda t: '\\u' + hex(int(t[0][2:-1]))[2:])
            return xmlcharref.transformString(ret)

    # build list of single arg builtins, tolerant of Python version, that can be used as parse actions
    singleArgBuiltins = []
    import __builtin__

    for fname in "sum len sorted reversed list tuple set any all min max".split():
        try:
            singleArgBuiltins.append(getattr(__builtin__, fname))
        except AttributeError:
            continue


    def get_function_arguments(func):
        return func.func_code.co_varnames[:func.func_code.co_argcount]


_generatorType = type((y for y in range(1)))


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


class __compat__(__config_flags):
    """
    A cross-version compatibility configuration for mo_parsing features that will be
    released in a future version. By setting values in this configuration to True,
    those features can be enabled in prior versions for compatibility development
    and testing.

     - collect_all_And_tokens - flag to enable fix for Issue #63 that fixes erroneous grouping
       of results names when an And expression is nested within an Or or MatchFirst;
       maintained for compatibility, but setting to False no longer restores pre-2.3.1
       behavior
    """

    _type_desc = "compatibility"

    collect_all_And_tokens = True

    _all_names = [__ for __ in locals() if not __.startswith("_")]
    _fixed_names = """
        collect_all_And_tokens
        """.split()


class __diag__(__config_flags):
    """
    Diagnostic configuration (all default to False)
     - warn_multiple_tokens_in_named_alternation - flag to enable warnings when a results
       name is defined on a MatchFirst or Or expression with one or more And subexpressions
     - warn_ungrouped_named_tokens_in_collection - flag to enable warnings when a results
       name is defined on a containing expression with ungrouped subexpressions that also
       have results names
     - warn_name_set_on_empty_Forward - flag to enable warnings whan a Forward is defined
       with a results name, but has no contents defined
     - warn_on_multiple_string_args_to_oneof - flag to enable warnings whan oneOf is
       incorrectly called with multiple str arguments
     - enable_debug_on_named_expressions - flag to auto-enable debug on all subsequent
       calls to ParserElement.setName()
    """

    _type_desc = "diagnostic"

    warn_multiple_tokens_in_named_alternation = False
    warn_ungrouped_named_tokens_in_collection = False
    warn_name_set_on_empty_Forward = False
    warn_on_multiple_string_args_to_oneof = False
    enable_debug_on_named_expressions = False

    _all_names = [__ for __ in locals() if not __.startswith("_")]
    _warning_names = [name for name in _all_names if name.startswith("warn")]
    _debug_names = [name for name in _all_names if name.startswith("enable_debug")]

    @classmethod
    def enable_all_warnings(cls):
        for name in cls._warning_names:
            cls.enable(name)


alphas = string.ascii_uppercase + string.ascii_lowercase
nums = "0123456789"
hexnums = nums + "ABCDEFabcdef"
alphanums = alphas + nums
_bslash = chr(92)
printables = "".join(c for c in string.printable if c not in string.whitespace)




def col (loc, strg):
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
    return 1 if 0 < loc < len(s) and s[loc-1] == '\n' else loc - s.rfind("\n", 0, loc)

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
        return strg[lastCR + 1:nextCR]
    else:
        return strg[lastCR + 1:]


'decorator to trim function calls to match the arity of the target'
def _trim_arity(func):
    if func in singleArgBuiltins:
        return lambda s, l, t: func(t)

    try:
        if isinstance(func, type):
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
        func = func.__call__
        spec = inspect.getfullargspec(func)
        self_arg = 1 if spec.args and spec.args[0] == "self" else 0
        if spec.varargs:
            start = 0
        else:
            start = 3 + self_arg - len(spec.args)


    def wrapper(*args):
        try:
            ret = func(*args[start:])
            return ret
        except Exception as e:
            if isinstance(e, TypeError) and spec.args[0] == "self" and "required positional argument" in e.args[0]:
                Log.error("Did you provide a `self` argument to a static function?", cause=e)
            # Log.warning("function failure", cause=e)
            from mo_parsing.exceptions import ParseException
            f = ParseException("function failed")
            f.__cause__ = e
            raise f

    # copy func name to wrapper for sensible debug output
    try:
        func_name = getattr(func, '__name__',
                            getattr(func, '__class__').__name__)
    except Exception:
        func_name = str(func)
    wrapper.__name__ = func_name

    return wrapper


def _xml_escape(data):
    """Escape &, <, >, ", ', etc. in a string of data."""

    # ampersand must be replaced first
    from_symbols = '&><"\''
    to_symbols = ('&' + s + ';' for s in "amp gt lt quot apos".split())
    for from_, to_ in zip(from_symbols, to_symbols):
        data = data.replace(from_, to_)
    return data

def _defaultStartDebugAction(instring, loc, expr):
    print("Match " + _ustr(expr) + " at loc " + _ustr(loc) + "(%d,%d)" % (lineno(loc, instring), col(loc, instring)))

def _defaultSuccessDebugAction(instring, startloc, endloc, expr, toks):
    print("Matched " + _ustr(expr) + " -> " + str(toks))

def _defaultExceptionDebugAction(instring, loc, expr, exc):
    print("Exception raised:" + _ustr(exc))

def nullDebugAction(*args):
    """'Do-nothing' debug action, to suppress debugging output during parsing."""
    pass

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

        wds = OneOrMore(wd).setParseAction(remove_duplicate_chars)
        print(wds.parseString("slkdjs sld sldd sdlf sdljf"))

    prints::

        >>entering remove_duplicate_chars(line: 'slkdjs sld sldd sdlf sdljf', 0, (['slkdjs', 'sld', 'sldd', 'sdlf', 'sdljf'], {}))
        <<leaving remove_duplicate_chars (ret: 'dfjkls')
        ['dfjkls']
    """
    f = _trim_arity(f)
    def z(*paArgs):
        thisFunc = f.__name__
        s, l, t = paArgs[-3:]
        if len(paArgs) > 3:
            thisFunc = paArgs[0].__class__.__name__ + '.' + thisFunc
        sys.stderr.write(">>entering %s(line: '%s', %d, %r)\n" % (thisFunc, line(l, s), l, t))
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
        if not hasattr(cls, '_intern') or any(cls._intern is getattr(superclass, '_intern', [])
                                              for superclass in cls.__mro__[1:]):
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
        return u''.join(filterfalse(unicode.isspace, cls._get_chars_for_ranges()))

    @_lazyclassproperty
    def alphas(cls):
        "all alphabetic characters in this range"
        return u''.join(filter(unicode.isalpha, cls._get_chars_for_ranges()))

    @_lazyclassproperty
    def nums(cls):
        "all numeric digit characters in this range"
        return u''.join(filter(unicode.isdigit, cls._get_chars_for_ranges()))

    @_lazyclassproperty
    def alphanums(cls):
        "all alphanumeric characters in this range"
        return cls.alphas + cls.nums


class mo_parsing_unicode(unicode_set):
    """
    A namespace class for defining common language unicode_sets.
    """
    _ranges = [(32, sys.maxunicode)]

    class Latin1(unicode_set):
        "Unicode set for Latin-1 Unicode Character Range"
        _ranges = [(0x0020, 0x007e), (0x00a0, 0x00ff),]

    class LatinA(unicode_set):
        "Unicode set for Latin-A Unicode Character Range"
        _ranges = [(0x0100, 0x017f),]

    class LatinB(unicode_set):
        "Unicode set for Latin-B Unicode Character Range"
        _ranges = [(0x0180, 0x024f),]

    class Greek(unicode_set):
        "Unicode set for Greek Unicode Character Ranges"
        _ranges = [
            (0x0370, 0x03ff), (0x1f00, 0x1f15), (0x1f18, 0x1f1d), (0x1f20, 0x1f45), (0x1f48, 0x1f4d),
            (0x1f50, 0x1f57), (0x1f59,), (0x1f5b,), (0x1f5d,), (0x1f5f, 0x1f7d), (0x1f80, 0x1fb4), (0x1fb6, 0x1fc4),
            (0x1fc6, 0x1fd3), (0x1fd6, 0x1fdb), (0x1fdd, 0x1fef), (0x1ff2, 0x1ff4), (0x1ff6, 0x1ffe),
        ]

    class Cyrillic(unicode_set):
        "Unicode set for Cyrillic Unicode Character Range"
        _ranges = [(0x0400, 0x04ff)]

    class Chinese(unicode_set):
        "Unicode set for Chinese Unicode Character Range"
        _ranges = [(0x4e00, 0x9fff), (0x3000, 0x303f),]

    class Japanese(unicode_set):
        "Unicode set for Japanese Unicode Character Range, combining Kanji, Hiragana, and Katakana ranges"
        _ranges = []

        class Kanji(unicode_set):
            "Unicode set for Kanji Unicode Character Range"
            _ranges = [(0x4E00, 0x9Fbf), (0x3000, 0x303f),]

        class Hiragana(unicode_set):
            "Unicode set for Hiragana Unicode Character Range"
            _ranges = [(0x3040, 0x309f),]

        class Katakana(unicode_set):
            "Unicode set for Katakana  Unicode Character Range"
            _ranges = [(0x30a0, 0x30ff),]

    class Korean(unicode_set):
        "Unicode set for Korean Unicode Character Range"
        _ranges = [(0xac00, 0xd7af), (0x1100, 0x11ff), (0x3130, 0x318f), (0xa960, 0xa97f), (0xd7b0, 0xd7ff), (0x3000, 0x303f),]

    class CJK(Chinese, Japanese, Korean):
        "Unicode set for combined Chinese, Japanese, and Korean (CJK) Unicode Character Range"
        pass

    class Thai(unicode_set):
        "Unicode set for Thai Unicode Character Range"
        _ranges = [(0x0e01, 0x0e3a), (0x0e3f, 0x0e5b),]

    class Arabic(unicode_set):
        "Unicode set for Arabic Unicode Character Range"
        _ranges = [(0x0600, 0x061b), (0x061e, 0x06ff), (0x0700, 0x077f),]

    class Hebrew(unicode_set):
        "Unicode set for Hebrew Unicode Character Range"
        _ranges = [(0x0590, 0x05ff),]

    class Devanagari(unicode_set):
        "Unicode set for Devanagari Unicode Character Range"
        _ranges = [(0x0900, 0x097f), (0xa8e0, 0xa8ff)]

mo_parsing_unicode.Japanese._ranges = (mo_parsing_unicode.Japanese.Kanji._ranges
                                      + mo_parsing_unicode.Japanese.Hiragana._ranges
                                      + mo_parsing_unicode.Japanese.Katakana._ranges)

# define ranges in language character sets
if PY_3:
    setattr(mo_parsing_unicode, u"العربية", mo_parsing_unicode.Arabic)
    setattr(mo_parsing_unicode, u"中文", mo_parsing_unicode.Chinese)
    setattr(mo_parsing_unicode, u"кириллица", mo_parsing_unicode.Cyrillic)
    setattr(mo_parsing_unicode, u"Ελληνικά", mo_parsing_unicode.Greek)
    setattr(mo_parsing_unicode, u"עִברִית", mo_parsing_unicode.Hebrew)
    setattr(mo_parsing_unicode, u"日本語", mo_parsing_unicode.Japanese)
    setattr(mo_parsing_unicode.Japanese, u"漢字", mo_parsing_unicode.Japanese.Kanji)
    setattr(mo_parsing_unicode.Japanese, u"カタカナ", mo_parsing_unicode.Japanese.Katakana)
    setattr(mo_parsing_unicode.Japanese, u"ひらがな", mo_parsing_unicode.Japanese.Hiragana)
    setattr(mo_parsing_unicode, u"한국어", mo_parsing_unicode.Korean)
    setattr(mo_parsing_unicode, u"ไทย", mo_parsing_unicode.Thai)
    setattr(mo_parsing_unicode, u"देवनागरी", mo_parsing_unicode.Devanagari)

