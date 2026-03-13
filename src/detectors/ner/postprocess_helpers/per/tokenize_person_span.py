from __future__ import annotations

import re


_PER_TOKEN_RE = re.compile(r"[A-Za-zÄÖÜäöüß]+(?:-[A-Za-zÄÖÜäöüß]+)?")


def tokenize_person_span(value: str) -> list[str]:
    return _PER_TOKEN_RE.findall(value)