import re
from typing import Iterable, Tuple


def finde_url(text: str) -> Iterable[Tuple[int, int, str]]:
    rx = re.compile(
        r"""
        \bhttps?://[^\s<>"']+
        |
        \bwww\.[^\s<>"']+
        |
        \b
        (?:
            (?:
                [a-z0-9][a-z0-9-]{0,61}[a-z0-9]
                |
                [a-z]+(?:-[a-z0-9]+)+
                |
                [a-z]+[0-9]+[a-z0-9-]*
            )
            (?:\.
                [a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?
            )+
            \.
            (?:
                [a-z]{2,}
                |
                local
            )
        )
        """,
        re.IGNORECASE | re.VERBOSE,
    )

    trailing = ".,;:!?)]}\"'"

    for m in rx.finditer(text):
        s, e = m.start(), m.end()

        while e > s and text[e - 1] in trailing:
            e -= 1

        if e <= s:
            continue

        yield (s, e, "URL")