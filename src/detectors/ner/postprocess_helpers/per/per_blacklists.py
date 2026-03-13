from __future__ import annotations

from typing import Final, Set


PER_BAD_TOKENS: Final[Set[str]] = {
    # greetings / sign-offs
    "hallo",
    "hi",
    "hey",
    "servus",
    "moin",
    "gruß",
    "grüße",
    "danke",
    "bitte",
    "sorry",

    # politeness / mail phrases
    "mit",
    "freundlichen",
    "freundliche",
    "beste",
    "lieben",
    "liebe",
    "vielen",
    "dank",

    # conversational fillers
    "ok",
    "okay",
    "ja",
    "nein",

    # pronouns / generic starters
    "ich",
    "wir",
    "mein",
    "meine",
    "unser",
    "unsere",
    "dein",
    "deine",
    "sein",
    "seine",
    "ihr",
    "ihre",

    # generic document / support / workflow terms
    "betreff",
    "ticket",
    "ticket-id",
    "id",
    "kunde",
    "firma",
    "produkt",
    "zeitpunkt",
    "fehler",
    "fehlerbeschreibung",
    "benutzer",
    "passwort",
    "benutzername",
    "meldung",
    "sitzung",
    "prüfung",
    "mitarbeiter",
    "anfrage",
    "vorgang",
    "anliegen",
    "status",

    # generic system / ui terms
    "login",
    "logout",
    "anmelden",
    "dashboard",
    "portal",
    "system",
    "plattform",
    "backend",
    "frontend",
    "support",
    "service",

    # time / date context words
    "uhr",
    "heute",
    "morgen",
    "gestern",
}