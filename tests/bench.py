# encoding: utf-8
"""
Parse-speed benchmark.  Numbers are recorded in faster.md.

    python tests/bench.py [--profile] [name ...]

Benchmarks: json, infix, sql (sql needs mo-sql-parsing importable, or checked out
beside this repo).
"""
import cProfile
import os
import pstats
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mo_parsing import (
    Forward,
    Group,
    Keyword,
    LEFT_ASSOC,
    Optional,
    RIGHT_ASSOC,
    Regex,
    Suppress,
    Word,
    delimited_list,
    infix_notation,
    one_of,
)
from mo_parsing.utils import alphanums, alphas, nums
from mo_parsing.whitespaces import Whitespace

ROUNDS = 5
REPEATS = 10


def json_bench():
    with Whitespace():
        value = Forward()
        string = Regex(r'"(?:[^"\\]|\\.)*"')
        number = Regex(r"-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?")
        constant = Keyword("true") | Keyword("false") | Keyword("null")
        member = Group(string("key") + Suppress(":") + value("value"))
        obj = Group(Suppress("{") + Optional(delimited_list(member)) + Suppress("}"))
        array = Group(Suppress("[") + Optional(delimited_list(value)) + Suppress("]"))
        value << (string | number | constant | obj | array)
    doc = (
        '{"glossary": {"title": "example glossary", "GlossDiv": {"title": "S", '
        '"GlossList": [{"ID": "SGML", "SortAs": "SGML", "Primes": [2, 3, 5, 7], '
        '"Avogadro": 6.02E23, "Found": false, "Nothing": null, "Empty": {}, '
        '"Also": [], "GlossDef": "A meta-markup language.", '
        '"SeeAlso": ["GML", "XML", "markup"]}]}}}'
    )
    return value, "[" + ", ".join([doc] * 30) + "]"


def infix_bench():
    with Whitespace():
        operand = Word(nums) | Word(alphas, alphanums)
        expr = infix_notation(
            operand,
            [
                (one_of("- +"), 1, RIGHT_ASSOC),
                (one_of("* /"), 2, LEFT_ASSOC),
                (one_of("+ -"), 2, LEFT_ASSOC),
                (one_of("< > = <= >= !="), 2, LEFT_ASSOC),
                (Keyword("and"), 2, LEFT_ASSOC),
                (Keyword("or"), 2, LEFT_ASSOC),
            ],
        )
    text = " or ".join(
        f"(a{i} + {i} * (b{i} - 3) / c{i} >= {i * 7} and -x{i} < y{i})" for i in range(40)
    )
    return expr, text


def sql_bench():
    sibling = os.path.join(os.path.dirname(sys.path[0]), "mo-sql-parsing")
    if os.path.isdir(sibling):
        sys.path.append(sibling)
    import mo_sql_parsing

    sql = """
    SELECT a.id, b.name, SUM(c.amount) AS total, COUNT(*) cnt
    FROM accounts a
    JOIN customers b ON a.cust_id = b.id
    LEFT JOIN transactions c ON c.acct = a.id AND c.ts > '2020-01-01'
    WHERE a.status IN ('open','pending') AND (b.region = 'EU' OR b.region = 'NA')
      AND NOT EXISTS (SELECT 1 FROM blocked x WHERE x.id = a.id)
    GROUP BY a.id, b.name
    HAVING SUM(c.amount) > 100
    ORDER BY total DESC, b.name
    LIMIT 10
    """

    class Element:
        def finalize(self):
            return self

        def parse(self, text):
            return mo_sql_parsing.parse(text)

    return Element(), sql


BENCHES = {"json": json_bench, "infix": infix_bench, "sql": sql_bench}


def run(name, profile=False):
    try:
        element, text = BENCHES[name]()
    except ImportError as cause:
        print(f"{name:6}  skipped ({cause})")
        return
    parser = element.finalize()
    parser.parse(text)
    best = None
    for _ in range(ROUNDS):
        start = time.perf_counter()
        for _ in range(REPEATS):
            parser.parse(text)
        ms = (time.perf_counter() - start) / REPEATS * 1000
        best = ms if best is None else min(best, ms)
    print(f"{name:6}  {best:8.1f} ms/parse  ({len(text)} chars, best of {ROUNDS} rounds)")
    if profile:
        prof = cProfile.Profile()
        prof.enable()
        for _ in range(5):
            parser.parse(text)
        prof.disable()
        pstats.Stats(prof).sort_stats("tottime").print_stats(20)


if __name__ == "__main__":
    args = sys.argv[1:]
    profile = "--profile" in args
    names = [a for a in args if not a.startswith("--")] or list(BENCHES)
    for name in names:
        run(name, profile)
