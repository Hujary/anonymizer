from __future__ import annotations

import math
import re
import hashlib
from typing import Dict, Tuple


TYP_RE = re.compile(r"^\[([A-ZÄÖÜa-zäöü_]+)(?:_[^\]]+)?\]$")


def typ_of(key: str) -> str:
    m = TYP_RE.match(key.strip())
    return m.group(1).upper() if m else "MISC"


def gen_token(typ: str, value: str) -> str:
    h = hashlib.sha1((typ + "::" + (value or "")).encode("utf-8")).hexdigest()[:8]
    return f"[{typ}_{h}]"


TYPE_LABELS_DE: Dict[str, str] = {
    "E_MAIL": "E-Mail",
    "TELEFON": "Telefon",
    "IBAN": "IBAN",
    "BIC": "BIC",
    "URL": "URL",
    "USTID": "USt-IdNr.",
    "RECHNUNGS_NUMMER": "Rechnungsnummer",
    "PLZ": "PLZ",
    "DATUM": "Datum",
    "PER": "Person",
    "ORG": "Organisation",
    "LOC": "Ort",
    "MISC": "Sonstiges",
}

TYPE_LABELS_EN: Dict[str, str] = {
    "E_MAIL": "E-mail",
    "TELEFON": "Phone",
    "IBAN": "IBAN",
    "BIC": "BIC",
    "URL": "URL",
    "USTID": "VAT ID",
    "RECHNUNGS_NUMMER": "Invoice No.",
    "PLZ": "ZIP",
    "DATUM": "Date",
    "PER": "Person",
    "ORG": "Organization",
    "LOC": "Location",
    "MISC": "Other",
}


def type_label(lang: str, typ: str) -> str:
    if lang == "de":
        return TYPE_LABELS_DE.get(typ, typ.title())
    return TYPE_LABELS_EN.get(typ, typ.title())


GROUP_ORDER = [
    "E_MAIL",
    "TELEFON",
    "IBAN",
    "BIC",
    "URL",
    "USTID",
    "RECHNUNGS_NUMMER",
    "PLZ",
    "DATUM",
    "PER",
    "ORG",
    "LOC",
    "MISC",
]


def group_sort_key(typ: str) -> Tuple[int, str]:
    try:
        return (GROUP_ORDER.index(typ), typ)
    except ValueError:
        return (len(GROUP_ORDER), typ)


def estimate_wrapped_lines(text: str, chars_per_line: int) -> int:
    if chars_per_line <= 0:
        chars_per_line = 80
    total_lines = 0
    for raw in (text.splitlines() or [""]):
        if raw.strip() == "":
            total_lines += 1
            continue
        line_len = 0
        lines_here = 1
        for word in raw.split(" "):
            w = len(word)
            if line_len == 0:
                line_len = w
            elif line_len + 1 + w <= chars_per_line:
                line_len += 1 + w
            else:
                lines_here += 1
                line_len = w
        total_lines += lines_here
    return total_lines


def current_chars_per_line(window_width: int) -> int:
    ww = max(320, window_width or 1200)
    side_padding = 24 * 2
    editors_gap = 16
    col_inner_padding = 24
    usable_px = max(300, ww - side_padding - editors_gap)
    col_px = usable_px / 2
    avg_char_px = 7.2
    return max(20, int((col_px - col_inner_padding) / avg_char_px))


def synced_textfield_height(
    left_text: str,
    right_text: str,
    window_width: int,
    min_lines: int = 18,
    extra_factor: float = 1.15,
) -> int:
    cpl = current_chars_per_line(window_width)
    left_needed = estimate_wrapped_lines(left_text or "", cpl)
    right_needed = estimate_wrapped_lines(right_text or "", cpl)
    h = max(min_lines, left_needed, right_needed)
    return int(math.ceil(h * extra_factor))