from typing import Callable, Dict, Iterable, List, Tuple

from core import config

from .contact import finde_contact
from .date import finde_date
from .finance import finde_finance
from .ip import finde_ip
from .location import finde_location
from .url import finde_url


_PRODUCES: Dict[str, List[str]] = {
    "finde_contact": ["E_MAIL", "TELEFON"],
    "finde_finance": ["IBAN"],
    "finde_location": ["PLZ", "STRASSE"],
    "finde_date": ["DATUM"],
    "finde_url": ["URL"],
    "finde_ip": ["IP_ADRESSE"],
}

_FINDERS: Dict[str, Callable[[str], Iterable[Tuple[int, int, str]]]] = {
    "finde_contact": finde_contact,
    "finde_finance": finde_finance,
    "finde_location": finde_location,
    "finde_date": finde_date,
    "finde_url": finde_url,
    "finde_ip": finde_ip,
}


def _should_run(finder_name: str, allowed: set[str]) -> bool:
    for t in _PRODUCES.get(finder_name, []):
        if t in allowed:
            return True
    return False


def finde_regex(text: str):
    allowed = set(config.get("regex_labels", [
        "E_MAIL",
        "TELEFON",
        "IBAN",
        "URL",
        "PLZ",
        "STRASSE",
        "DATUM",
        "IP_ADRESSE",
    ]))

    order = [
        "finde_finance",
        "finde_contact",
        "finde_url",
        "finde_ip",
        "finde_location",
        "finde_date",
    ]

    for name in order:
        if not _should_run(name, allowed):
            continue
        for s, e, label in _FINDERS[name](text):
            if label in allowed:
                yield (s, e, label)