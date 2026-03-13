from __future__ import annotations

from typing import Final, Set


PER_BAD_TOKENS: Final[Set[str]] = {
    # greetings
    "hallo",
    "hi",
    "hey",
    "servus",
    "moin",
    "grüße",
    "gruß",
    "guten",
    "gutenmorgen",
    "gutenabend",
    "guten tag",

    # email phrases
    "danke",
    "vielen dank",
    "mit",
    "freundlichen",
    "freundliche",
    "beste",
    "lieben",
    "liebe",
    "beste grüße",
    "mit freundlichen grüßen",

    # conversational tokens
    "bitte",
    "sorry",
    "ok",
    "okay",
    "ja",
    "nein",

    # sentence starters
    "mein",
    "meine",
    "unser",
    "unsere",
    "ich",
    "wir",
}