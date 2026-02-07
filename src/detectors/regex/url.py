import re
from typing import Iterable, Tuple

def finde_url(text: str) -> Iterable[Tuple[int, int, str]]:
    rx = re.compile(r"\bhttps?://[^\s]+|\bwww\.[^\s]+\b", re.IGNORECASE)
    for m in rx.finditer(text):
        yield (m.start(), m.end(), "URL")