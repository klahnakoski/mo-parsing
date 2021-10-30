# listAllMatches.py
#
# Sample program showing how/when to use listAllMatches to get all matching tokens in a results name.
#
# copyright 2006, Paul McGuire
#

from mo_parsing import one_of, OneOrMore, printables, StringEnd

test = "The quick brown fox named 'Aloysius' lives at 123 Main Street (and jumps over lazy dogs in his spare time)."
nonAlphas = [c for c in printables if not c.isalpha()]





vowels = one_of(list("aeiouy"), caseless=True)("vowels")
cons = one_of(list("bcdfghjklmnpqrstvwxz"), caseless=True)("cons")
other = one_of(nonAlphas)("others")
letters = OneOrMore(cons | vowels | other) + StringEnd()

results = letters.parse_string(test)







vowels = one_of(list("aeiouy"), caseless=True)("vowels*")
cons = one_of(list("bcdfghjklmnpqrstvwxz"), caseless=True)("cons*")
other = one_of(nonAlphas)("others*")

letters = OneOrMore(cons | vowels | other)

results = letters.parse_string(test, parse_all=True)











