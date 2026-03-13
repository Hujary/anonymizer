from __future__ import annotations

import re


def normalize_whitespace(value: str) -> str:
    return " ".join(value.split())


def normalize_token(value: str) -> str:
    text = value.strip().lower()
    text = re.sub(r"[,\.;:]+$", "", text)
    return text