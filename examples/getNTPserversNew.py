# getNTPserversNew.py
#
# Demonstration of the parsing module, implementing a HTML page scanner,
# to extract a list of NTP time servers from the NIST web site.
#
# Copyright 2004-2010, by Paul McGuire
# September, 2010 - updated to more current use of .set_token_name, new NIST URL
#
from urllib.request import urlopen

from mo_parsing import *
from mo_parsing.helpers import ipv4_address

integer = Word(nums)
ipAddress = ipv4_address()
hostname = delimited_list(Word(alphas, alphanums + "-_"), ".", combine=True)
tdStart, tdEnd = makeHTMLTags("td")
timeServerPattern = (
    tdStart
    + hostname("hostname")
    + tdEnd
    + tdStart
    + ipAddress("ipAddr")
    + tdEnd
    + tdStart
    + tdStart.tag_body("loc")
    + tdEnd
)

# get list of time servers
nistTimeServerURL = "https://tf.nist.gov/tf-cgi/servers.cgi#"
with urlopen(nistTimeServerURL) as serverListPage:
    serverListHTML = serverListPage.read().decode("UTF-8")

addrs = {}
for srvr, startloc, endloc in timeServerPattern.scan_string(serverListHTML):

    addrs[srvr.ipAddr] = srvr.end
