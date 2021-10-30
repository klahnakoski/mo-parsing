# partial_gene_match.py
#
#  Example showing how to use the CloseMatch class, to find strings in a gene with up to 'n' mismatches
#
from urllib.request import urlopen

from mo_parsing import *
from mo_parsing.helpers import *

# read in a bunch of genomic data
data_url = "http://toxodb.org/common/downloads/release-6.0/Tgondii/TgondiiApicoplastORFsNAs_ToxoDB-6.0.fasta"
with urlopen(data_url) as datafile:
    fastasrc = datafile.read().decode()

# define parser to extract gene definitions
"""
Sample header:
>NC_001799-6-2978-2778 | organism=Toxoplasma_gondii_RH | location=NC_001799:2778-2978(-) | length=201
"""
integer = integer
genebit = Group(
    ">"
    + Word(alphanums.upper() + "-_")("gene_id")
    + "|"
    + Word(printables)("organism")
    + "|"
    + Word(printables)("location")
    + "|"
    + "length="
    + integer("gene_len")
    + LineEnd()
    + Word("ACGTN")[1, ...].add_parse_action("".join)("gene")
)

# read gene data from .fasta file - takes just a few seconds
# An important aspect of this parsing process is the reassembly of all the separate lines of the
# gene into a single scannable string. Just searching the raw .fasta file could overlook matches
# if the match is broken up across separate lines. The parse action in the genebit parser does
# this reassembly work.
genedata = genebit[1, ...].parse_string(fastasrc)

# using the genedata extracted above, look for close matches of a gene sequence
searchseq = CloseMatch("TTAAATCTAGAAGAT", 3)

for g in genedata:
    show_header = True
    # scan for close matches, list out found strings, and mark mismatch locations
    for t, startLoc, endLoc in searchseq.scan_string(g.gene, overlap=True):
        if show_header:
            # only need to show the header once


            show_header = False

        matched = t[0]
        mismatches = t["mismatches"]


        if mismatches:
            print(
                "      ",
                "".join(
                    "*" if i in mismatches else " "
                    for i, c in enumerate(searchseq.match)
                ),
            )
        else:
            pass



