# detectors/regex/__init__.py
from typing import Iterable, Tuple, Callable, Dict, List
from core import config

from .contact import finde_contact
from .finance import finde_finance
from .location import finde_location
from .date import finde_date
from .invoice import finde_invoice
from .url import finde_url

_PRODUCES: Dict[str, List[str]] = {
    "finde_contact": ["E_MAIL", "TELEFON"],
    "finde_finance": ["IBAN", "BIC", "USTID", "BETRAG"],
    "finde_location": ["PLZ", "ORT", "STRASSE"],
    "finde_date": ["DATUM"],
    "finde_invoice": ["RECHNUNGS_NUMMER"],
    "finde_url": ["URL"],
}

_FINDERS: Dict[str, Callable[[str], Iterable[Tuple[int, int, str]]]] = {
    "finde_contact": finde_contact,
    "finde_finance": finde_finance,
    "finde_location": finde_location,
    "finde_date": finde_date,
    "finde_invoice": finde_invoice,
    "finde_url": finde_url,
}

def _should_run(finder_name: str, allowed: set[str]) -> bool:
    for t in _PRODUCES.get(finder_name, []):
        if t in allowed:
            return True
    return False

def finde_regex(text: str):
    allowed = set(config.get("regex_labels", [
        "E_MAIL", "TELEFON", "IBAN", "BIC", "URL", "USTID",
        "RECHNUNGS_NUMMER", "PLZ", "DATUM", "BETRAG"
    ]))

    order = ["finde_finance", "finde_invoice", "finde_contact", "finde_url", "finde_location", "finde_date"]

    for name in order:
        if not _should_run(name, allowed):
            continue
        for s, e, label in _FINDERS[name](text):
            if label in allowed:
                yield (s, e, label)