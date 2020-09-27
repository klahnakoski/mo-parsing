from mo_parsing import *

text = """Lorem ipsum dolor sit amet, consectetur adipisicing
elit, sed do eiusmod tempor incididunt ut labore et dolore magna
aliqua. Ut enim ad minim veniam, quis nostrud exercitation
ullamco laboris nisi ut aliquip ex ea commodo consequat. Duis
aute irure dolor in reprehenderit in voluptate velit esse cillum
dolore eu fugiat nulla pariatur. Excepteur sint occaecat
cupidatat non proident, sunt in culpa qui officia deserunt
mollit anim id est laborum"""

# find all words beginning with a vowel
vowels = "aeiouAEIOU"
initialVowelWord = Word(vowels, alphas)

# Unfortunately, searchString will advance character by character through
# the input text, so it will detect that the initial "Lorem" is not an
# initialVowelWord, but then it will test "orem" and think that it is. So
# we need to add a do-nothing term that will match the words that start with
# consonants, but we will just throw them away when we match them. The key is
# that, in having been matched, the parser will skip over them entirely when
# looking for initialVowelWords.
consonants = "".join(c for c in alphas if c not in vowels)
initialConsWord = Word(consonants, alphas).suppress()

# add parse action to annotate the parsed tokens with their location in the
# input string
def addLocnToTokens(t, l, s):
    t["locn"] = l
    t["word"] = t[0]


initialVowelWord.addParseAction(addLocnToTokens)

for ivowelInfo in (initialConsWord | initialVowelWord).searchString(text):
    if not ivowelInfo:
        continue


# alternative - add an Empty that will save the current location
def location(name):
    return Empty().addParseAction(lambda t, l, s: t.__setitem__(name, l))


locateInitialVowels = location("locn") + initialVowelWord("word")

# search through the input text
for ivowelInfo in (initialConsWord | locateInitialVowels).searchString(text):
    if not ivowelInfo:
        continue
