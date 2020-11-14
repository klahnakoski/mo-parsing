# encoding: utf-8

from mo_parsing.utils import Log
from mo_parsing.cache import packrat_cache
from mo_parsing.core import ParserElement
from mo_parsing.exceptions import ParseException

try:
    from jx_python import jx
    from mo_files import File
    from mo_future import text, process_time
    from mo_times import Date
    from pyLibrary import convert
except Exception as casue:
    Log.note("please pip install jx-python and pyLibrary")


class Profiler(object):
    def __init__(self, file):
        """
        USE with Profiler("myfile.tab"): TO ENABLE PER-PARSER PROFILING
        :param file:
        """
        self.file = File(file).set_extension("tab")
        self.previous_parse = None

    def __enter__(self):
        timing.clear()
        self.previous_parse = ParserElement._parse
        ParserElement._parse = _profile_parse

    def __exit__(self, exc_type, exc_val, exc_tb):
        ParserElement._parse = self.previous_parse
        profile = jx.sort(
            [
                {
                    "parser": text(parser),
                    "cache_hits": cache,
                    "matches": match,
                    "failures": fail,
                    "call_count": match + fail + cache,
                    "total_parse": parse,
                    "total_overhead": all - parse,
                    "per_parse": parse / (match + fail),
                    "per_overhead": (all - parse) / (match + fail + cache),
                }
                for parser, (cache, match, fail, parse, all) in timing.items()
            ],
            {"total_parse": "desc"},
        )
        self.file.add_suffix(
            Date.now().format("%Y%m%d_%H%M%S")
        ).write(convert.list2tab(profile))


timing = {}


def _profile_parse(self, string, start, doActions=True):
    all_start = process_time()
    try:
        lookup = (self, string, start, doActions)
        value = packrat_cache.get(lookup)
        if value is not None:
            match = 0
            if isinstance(value, Exception):
                raise value
            return value

        try:
            try:
                preloc = self.engine.skip(string, start)
                parse_start = process_time()
                tokens = self.parseImpl(string, preloc, doActions)
                parse_end = process_time()
                match = 1
            except Exception as cause:
                parse_end = process_time()
                match = 2
                self.parser_config.failAction and self.parser_config.failAction(
                    self, start, string, cause
                )
                raise

            if self.parseAction and (doActions or self.parser_config.callDuringTry):
                for fn in self.parseAction:
                    tokens = fn(tokens, start, string)
        except ParseException as cause:
            packrat_cache.set(lookup, cause)
            raise

        packrat_cache.set(lookup, tokens)
        return tokens
    finally:
        timing_entry = timing.get(self)
        if timing_entry is None:
            timing_entry = timing[self] = [0, 0, 0, 0, 0]
        timing_entry[match] += 1  # cache
        timing_entry[3] += parse_end - parse_start  # parse time
        timing_entry[4] += process_time() - all_start  # all time
