# listAllMatches.py
#
# Sample program showing how/when to use listAllMatches to get all matching tokens in a results name.
#
# copyright 2006, Paul McGuire
#

from mo_parsing import oneOf, OneOrMore, printables, StringEnd

test = "The quick brown fox named 'Aloysius' lives at 123 Main Street (and jumps over lazy dogs in his spare time)."
nonAlphas = [c for c in printables if not c.isalpha()]





vowels = oneOf(list("aeiouy"), caseless=True)("vowels")
cons = oneOf(list("bcdfghjklmnpqrstvwxz"), caseless=True)("cons")
other = oneOf(nonAlphas)("others")
letters = OneOrMore(cons | vowels | other) + StringEnd()

results = letters.parseString(test)







vowels = oneOf(list("aeiouy"), caseless=True)("vowels*")
cons = oneOf(list("bcdfghjklmnpqrstvwxz"), caseless=True)("cons*")
other = oneOf(nonAlphas)("others*")

letters = OneOrMore(cons | vowels | other)

results = letters.parseString(test, parseAll=True)











