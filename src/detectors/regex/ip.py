import re
from typing import Iterable, Tuple


_OCTET = r"(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)"

_IPV4_RE = re.compile(
    rf"""
    (?<!\d)
    (?:
        {_OCTET}\.{_OCTET}\.{_OCTET}\.{_OCTET}
    )
    (?!\d)
    """,
    re.VERBOSE,
)


def finde_ip(text: str) -> Iterable[Tuple[int, int, str]]:
    """
    Regex-basierte Erkennung von IPv4-Adressen.

    Erkannt werden:
      - IPv4 im Bereich 0.0.0.0 bis 255.255.255.255

    Nicht erkannt (absichtlich hier):
      - IPv6
      - IPs als Teil längerer Token mit zusätzlichen Ziffern drumherum

    Rückgabe:
      (start_index, end_index, "IP_ADRESSE")
    """

    trailing = ".,;:!?)]}\"'"

    for m in _IPV4_RE.finditer(text):
        s, e = m.start(), m.end()

        while e > s and text[e - 1] in trailing:
            e -= 1

        if e <= s:
            continue

        yield (s, e, "IP_ADRESSE")