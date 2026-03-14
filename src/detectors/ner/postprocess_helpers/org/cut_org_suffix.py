from __future__ import annotations

import re

from .org_blacklists import ORG_LEGAL_SUFFIXES


_SUFFIX_TOKEN_PATTERN = "|".join(
    sorted((re.escape(x) for x in ORG_LEGAL_SUFFIXES), key=len, reverse=True)
)


# -------------------------------------------------------------
# erkennt einzelne oder kombinierte Suffixe
#
# Beispiele:
#
# GmbH
# AG
# GmbH & Co KG
# GmbH & Co. KG
# -------------------------------------------------------------
_ORG_SUFFIX_CHAIN_RE = re.compile(
    rf"""
    (?P<suffix_chain>

        {_SUFFIX_TOKEN_PATTERN}

        (
            \s*&\s*Co\.?\s*
            {_SUFFIX_TOKEN_PATTERN}
        )?
    )

    (?=$|[^A-Za-z])
    """,
    re.IGNORECASE | re.VERBOSE,
)


def cut_span_at_suffix(text: str, start: int, end: int) -> tuple[int, int]:
    """
    Schneidet einen ORG-Span auf das letzte gültige
    Organisationssuffix zurück.

    Wird nur aktiv wenn NER zu viel Text erfasst hat.
    """

    span = text[start:end]

    matches = list(_ORG_SUFFIX_CHAIN_RE.finditer(span))

    if not matches:
        return start, end

    last = matches[-1]

    cut_end = start + last.end("suffix_chain")

    return start, cut_end