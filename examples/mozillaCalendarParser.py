from mo_parsing import (
    Optional,
    oneOf,
    Literal,
    Word,
    printables,
    Group,
    OneOrMore,
    ZeroOrMore,
)

"""
A simple parser for calendar (*.ics) files,
as exported by the Mozilla calendar.

Any suggestions and comments welcome.

Version:   0.1
Copyright: Petri Savolainen <firstname.lastname@iki.fi>
License:   Free for any use
"""


# TERMINALS

BEGIN = Literal("BEGIN:").suppress()
END = Literal("END:").suppress()
valstr = printables + "\xe4\xf6\xe5\xd6\xc4\xc5 "

EQ = Literal("=").suppress()
SEMI = Literal(";").suppress()
COLON = Literal(":").suppress()

EVENT = Literal("VEVENT").suppress()
CALENDAR = Literal("VCALENDAR").suppress()
ALARM = Literal("VALARM").suppress()

# TOKENS

CALPROP = oneOf("VERSION PRODID METHOD")
ALMPROP = oneOf("TRIGGER")
EVTPROP = oneOf(
    "X-MOZILLA-RECUR-DEFAULT-INTERVAL \
                     X-MOZILLA-RECUR-DEFAULT-UNITS \
                     UID DTSTAMP LAST-MODIFIED X RRULE EXDATE"
)

propval = Word(valstr)
typeval = Word(valstr)
typename = oneOf("VALUE MEMBER FREQ UNTIL INTERVAL")

proptype = Group(SEMI + typename + EQ + typeval).suppress()

calprop = Group(CALPROP + ZeroOrMore(proptype) + COLON + propval)
almprop = Group(ALMPROP + ZeroOrMore(proptype) + COLON + propval)
evtprop = (
    Group(EVTPROP + ZeroOrMore(proptype) + COLON + propval).suppress()
    | "CATEGORIES" + COLON + propval.set_token_name("categories")
    | "CLASS" + COLON + propval.set_token_name("class")
    | "DESCRIPTION" + COLON + propval.set_token_name("description")
    | "DTSTART" + proptype + COLON + propval.set_token_name("begin")
    | "DTEND" + proptype + COLON + propval.set_token_name("end")
    | "LOCATION" + COLON + propval.set_token_name("location")
    | "PRIORITY" + COLON + propval.set_token_name("priority")
    | "STATUS" + COLON + propval.set_token_name("status")
    | "SUMMARY" + COLON + propval.set_token_name("summary")
    | "URL" + COLON + propval.set_token_name("url")
)
calprops = Group(OneOrMore(calprop)).suppress()
evtprops = Group(OneOrMore(evtprop))
almprops = Group(OneOrMore(almprop)).suppress()

alarm = BEGIN + ALARM + almprops + END + ALARM
event = BEGIN + EVENT + evtprops + Optional(alarm) + END + EVENT
events = Group(OneOrMore(event))
calendar = BEGIN + CALENDAR + calprops + ZeroOrMore(event) + END + CALENDAR
calendars = OneOrMore(calendar)


# PARSE ACTIONS


def gotEvent(s, loc, toks):
    for event in toks:



event.addParseAction(gotEvent)


# MAIN PROGRAM

calendars.parseFile("examples/mozilla.ics")
