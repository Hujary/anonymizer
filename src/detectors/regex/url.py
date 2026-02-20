import re
from typing import Iterable, Tuple


def finde_url(text: str) -> Iterable[Tuple[int, int, str]]:
    """
    Regex-basierte Erkennung einfacher URL-Formate.

    Erkannt werden:
      - http://...
      - https://...
      - www....
      - FQDN / Hostnames mit Punkt (z. B. server.domain.de, erp-test01.techsolutions.local)

    Nicht erkannt (absichtlich hier):
      - IP-Adressen

    Rückgabe:
      (start_index, end_index, "URL")
    """

    rx = re.compile(
        r"""
        # ----------------------------
        # 1) http(s)://...
        # ----------------------------
        \bhttps?://[^\s<>"']+
        |
        # ----------------------------
        # 2) www....
        # ----------------------------
        \bwww\.[^\s<>"']+
        |
        # ----------------------------
        # 3) FQDN / Hostname
        #    - mind. 2 Labels
        #    - letztes Label (TLD) >= 2 Buchstaben ODER 'local'
        #    - verhindert Kurzformen wie B.Sc / M.A / u.a / v3.4
        # ----------------------------
        \b
        (?:
            # Erstes/Host-Label: mindestens 2 Zeichen ODER enthält Ziffer/Hyphen (für vpn01, erp-test01)
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
                [a-z]{2,}     # echte TLDs wie de, com, io, ...
                |
                local         # interne FQDNs
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