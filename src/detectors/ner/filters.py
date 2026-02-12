###     Strikter NER-Postfilter (Qualitätssicherung + Normalisierung + Post-Boost)
### __________________________________________________________________________
#
#  - Entfernt typische spaCy-Fehlklassifikationen (Grußwörter, Rollen, Metabegriffe)
#  - Erzwingt harte Regeln für ORG (Rechtsform-Hinweis oder starke Großschreibung)
#  - Normalisiert PER-Treffer auf echte Namenssegmente
#  - Normalisiert ORG-Treffer auf minimales "Name + Rechtsform" Segment (verhindert Satz-ORGs)
#  - Post-Boost: ORG-Erweiterung wenn NER nur Rechtsform liefert ("GmbH" -> "AlphaTech GmbH")
#  - Ergänzt @Mentions ("@Tobias") als PER via Postprocessing (Offsets bleiben korrekt)
#  - Verhindert numerische / triviale / zu kurze Entitäten
#  - Label-Whitelist wird dynamisch aus der App-Config geladen


from __future__ import annotations

import re
from typing import List, Iterable, Set, Optional

from core.typen import Treffer
from core import config


COMMON_GREETING_WORDS = {
    "hallo", "hi", "hey", "danke", "vielen", "gruß", "grüße",
    "mit", "freundlichen", "beste", "liebe", "servus", "moin",
}


ORG_HINTS = {
    " gmbh", " ag", " kg", " ug", " gbr", " mbh",
    " kgaa", " e.v", " ev", " verein", " eg",
}


ORG_STOPWORDS = {
    "ordner", "team", "teams", "postfach", "inbox",
    "gruppe", "folder", "verzeichnis", "kanal",
    "channel", "chat", "projekt", "abteilung",
    "bereich", "rolle", "rollen", "konto",
    "account", "sammlung", "collection", "upload",
}


PER_BAD_TOKENS = {
    "Hallo", "Hi", "Hey", "Danke", "Mit",
    "Freundlichen", "Beste", "Liebe",
    "Servus", "Moin", "Team", "Upload",
    "HR", "Budgetfreigabe",
}


PER_HINTS_STATIC = {"Tom", "Max", "Anna", "Julia"}
PER_HINTS_CONFIG = set(config.get("ner_person_hints", []))
PER_HINTS: Set[str] = {h.strip() for h in (PER_HINTS_STATIC | PER_HINTS_CONFIG) if h.strip()}


NAME_TOKEN_RE = re.compile(r"[A-ZÄÖÜ][a-zäöüß]+(?:-[A-ZÄÖÜ][a-zäöüß]+)?")


_AT_MENTION_RE = re.compile(
    r"(?<!\w)@(?P<name>[A-Za-zÄÖÜäöüß][A-Za-zÄÖÜäöüß\-]{1,})(?=[\s:,.!?]|$)"
)


_ORG_LEGALFORM_RE = re.compile(
    r"\b(?:gmbh|ag|kg|ug|gbr|mbh|kgaa|eg|verein|e\.?\s*v\.?)\b",
    re.IGNORECASE,
)

_ORG_NAME_TOKEN_RE = re.compile(r"[A-Za-zÄÖÜäöüß0-9][A-Za-zÄÖÜäöüß0-9&\.\-+]{0,}")
_ORG_CONNECTOR_RE = re.compile(r"^(?:&|und|\+|-)$", re.IGNORECASE)

_ORG_CONTEXT_BREAKS = {
    "da", "sie", "aktuell", "an", "der", "die", "das", "den", "des",
    "für", "unseren", "unsere", "unser", "kunden", "kundin", "kunde",
    "arbeitet", "arbeite", "arbeitest", "arbeiten", "habe", "haben", "hat",
    "damit", "dass", "ob", "bitte", "schau", "ruf", "kurz",
}


def _is_numeric_or_short(span: str) -> bool:
    s = span.strip()
    if not s:
        return True
    if re.fullmatch(r"[0-9\-\s/.()+]{1,}", s):
        return True
    if len(s) <= 2:
        return True
    return False


def _normalize_person_hit(text: str, hit: Treffer) -> Treffer | None:
    span_full = text[hit.start:hit.ende]

    for chunk in re.split(r"[\n,;|]+", span_full):
        chunk = chunk.strip()
        if not chunk:
            continue

        tokens: List[tuple[str, int, int]] = []
        for m in re.finditer(r"\b\w[\w\-ÄÖÜäöüß]*\b", chunk):
            tok = m.group(0)
            if tok in PER_BAD_TOKENS:
                break
            tokens.append((tok, m.start(), m.end()))

        if not tokens:
            continue

        name_st: Optional[int] = None
        name_en: Optional[int] = None
        count = 0

        for tok, a, b in tokens:
            if NAME_TOKEN_RE.fullmatch(tok):
                if name_st is None:
                    name_st = a
                name_en = b
                count += 1
                if count == 2:
                    break
            else:
                break

        if name_st is None or name_en is None:
            continue

        rel_chunk_off = span_full.find(chunk)
        if rel_chunk_off < 0:
            continue

        abs_start = hit.start + rel_chunk_off + name_st
        abs_end = hit.start + rel_chunk_off + name_en

        if abs_end - abs_start >= 2:
            return Treffer(
                abs_start,
                abs_end,
                hit.label,
                hit.source,
                from_regex=hit.from_regex,
                from_ner=hit.from_ner,
            )

    return None


def _line_bounds(text: str, pos: int) -> tuple[int, int]:
    ls = text.rfind("\n", 0, pos)
    le = text.find("\n", pos)
    start = 0 if ls < 0 else ls + 1
    end = len(text) if le < 0 else le
    return start, end


def _expand_org_if_only_legalform(text: str, hit: Treffer) -> Treffer:
    span = text[hit.start:hit.ende].strip()
    if not span:
        return hit

    if not _ORG_LEGALFORM_RE.fullmatch(span):
        return hit

    line_start, line_end = _line_bounds(text, hit.start)
    left_text = text[line_start:hit.start]
    right_text = text[hit.ende:line_end]

    toks_left: List[tuple[str, int, int]] = []
    for m in _ORG_NAME_TOKEN_RE.finditer(left_text):
        tok = m.group(0)
        toks_left.append((tok, m.start(), m.end()))

    toks_right: List[tuple[str, int, int]] = []
    for m in _ORG_NAME_TOKEN_RE.finditer(right_text):
        tok = m.group(0)
        toks_right.append((tok, m.start(), m.end()))

    start_abs = hit.start
    end_abs = hit.ende

    kept = 0
    i = len(toks_left) - 1
    while i >= 0 and kept < 6:
        tok, a, b = toks_left[i]
        low = tok.lower()

        if low in _ORG_CONTEXT_BREAKS:
            break

        if _ORG_CONNECTOR_RE.fullmatch(tok):
            start_abs = line_start + a
            i -= 1
            continue

        if len(tok) < 2:
            break

        prev_char = left_text[a - 1] if a - 1 >= 0 else ""
        if prev_char in ":;()\"„“":
            break

        start_abs = line_start + a
        kept += 1
        i -= 1

    if toks_right:
        t0, a0, b0 = toks_right[0]
        if _ORG_CONNECTOR_RE.fullmatch(t0) and len(toks_right) >= 2:
            t1, a1, b1 = toks_right[1]
            if t1.lower() in {"co", "kg"} or re.fullmatch(r"[A-Za-zÄÖÜäöüß0-9]{2,}", t1):
                end_abs = hit.ende + b1

        if t0.lower() == "co" and len(toks_right) >= 2:
            t1, a1, b1 = toks_right[1]
            if t1.lower() in {"kg"}:
                end_abs = hit.ende + b1

    while end_abs > start_abs and text[end_abs - 1] in " \t\r\n,.;:)]}":
        end_abs -= 1

    if end_abs <= start_abs:
        return hit

    expanded_span = text[start_abs:end_abs].strip()
    if not expanded_span:
        return hit

    if _ORG_LEGALFORM_RE.fullmatch(expanded_span):
        return hit

    if not _ORG_LEGALFORM_RE.search(expanded_span):
        return hit

    return Treffer(
        start_abs,
        end_abs,
        hit.label,
        hit.source,
        from_regex=hit.from_regex,
        from_ner=hit.from_ner,
    )


def _normalize_org_hit(text: str, hit: Treffer) -> Treffer | None:
    span_full = text[hit.start:hit.ende]
    span_full_stripped = span_full.strip()
    if not span_full_stripped:
        return None

    if "\n" in span_full_stripped or "\r" in span_full_stripped:
        chunks = re.split(r"[\n\r]+", span_full)
    else:
        chunks = [span_full]

    best: Treffer | None = None

    for chunk in chunks:
        chunk = chunk.strip()
        if not chunk:
            continue

        if len(chunk) > 140:
            continue

        m_form_last = None
        for m in _ORG_LEGALFORM_RE.finditer(chunk):
            m_form_last = m
        if m_form_last is None:
            continue

        form_start = m_form_last.start()
        form_end = m_form_last.end()

        toks: List[tuple[str, int, int]] = []
        for m in _ORG_NAME_TOKEN_RE.finditer(chunk):
            tok = m.group(0)
            toks.append((tok, m.start(), m.end()))

        if not toks:
            continue

        form_tok_idx: Optional[int] = None
        for i, (_tok, a, b) in enumerate(toks):
            if not (b <= form_start or form_end <= a):
                form_tok_idx = i
                break
        if form_tok_idx is None:
            continue

        left = form_tok_idx - 1
        start_idx = form_tok_idx
        name_tokens_seen = 0

        while left >= 0:
            tok, a, b = toks[left]
            low = tok.lower()

            if low in _ORG_CONTEXT_BREAKS:
                break

            if _ORG_CONNECTOR_RE.fullmatch(tok):
                start_idx = left
                left -= 1
                continue

            if len(tok) < 2:
                break

            prev_char = chunk[a - 1] if a - 1 >= 0 else ""
            if prev_char in ":;()\"„“":
                break

            start_idx = left
            name_tokens_seen += 1
            if name_tokens_seen >= 6:
                break

            left -= 1

        tail = chunk[form_end:]
        m_tail = re.match(r"^\s*(?:&|und)\s*Co\.?\s*(?:\s*\.?\s*)?(?:KG|kg)\b", tail)
        if m_tail:
            end_pos = form_end + m_tail.end()
        else:
            end_pos = form_end

        rel_chunk_off = span_full.find(chunk)
        if rel_chunk_off < 0:
            continue

        abs_start = hit.start + rel_chunk_off + toks[start_idx][1]
        abs_end = hit.start + rel_chunk_off + end_pos

        while abs_end > abs_start and text[abs_end - 1] in " \t\r\n,.;:)]}":
            abs_end -= 1

        if abs_end - abs_start < 4:
            continue

        cand = Treffer(
            abs_start,
            abs_end,
            hit.label,
            hit.source,
            from_regex=hit.from_regex,
            from_ner=hit.from_ner,
        )

        cand_span = text[cand.start:cand.ende].strip()
        if not _ORG_LEGALFORM_RE.search(cand_span):
            continue

        if best is None:
            best = cand
        else:
            len_best = best.ende - best.start
            len_cand = cand.ende - cand.start
            if 4 <= len_cand < len_best:
                best = cand

    return best


def _add_at_mentions(text: str) -> List[Treffer]:
    out: List[Treffer] = []
    for m in _AT_MENTION_RE.finditer(text):
        s = m.start("name")
        e = m.end("name")
        out.append(Treffer(s, e, "PER", "ner", from_ner=True))
    return out


def filter_ner_strict(
    text: str,
    hits: List[Treffer],
    *,
    allowed_labels: Iterable[str] = ("PER", "ORG"),
) -> List[Treffer]:
    allowed: Set[str] = {a.upper() for a in allowed_labels}
    out: List[Treffer] = []

    for h in hits:
        L = h.label.upper()
        span = text[h.start:h.ende].strip()

        if not span:
            continue

        if span in PER_HINTS and "PER" in allowed and L != "PER":
            L = "PER"
            h = Treffer(
                h.start,
                h.ende,
                "PER",
                h.source,
                from_regex=h.from_regex,
                from_ner=h.from_ner,
            )

        if L not in allowed:
            continue

        low = span.lower()

        if low in COMMON_GREETING_WORDS:
            continue

        if _is_numeric_or_short(span):
            continue

        if L == "PER":
            nh = _normalize_person_hit(text, h)
            if nh is None:
                continue
            h = nh
            L = h.label.upper()

        if L == "ORG":
            h = _expand_org_if_only_legalform(text, h)

            nh = _normalize_org_hit(text, h)
            if nh is None:
                continue
            h = nh
            span = text[h.start:h.ende].strip()
            low = span.lower()

        if L == "ORG":
            low_span = " " + span.lower()

            if any(sw in low_span for sw in ORG_STOPWORDS):
                continue

            if "-" in span:
                right = span.split("-", 1)[1].strip().lower()
                if right in ORG_STOPWORDS:
                    continue

            has_legal_hint = any(hint in low_span for hint in ORG_HINTS)
            caps_count = sum(1 for c in span if c.isupper())
            has_caps_style = caps_count >= 3
            is_short_acronym = bool(re.fullmatch(r"[A-ZÄÖÜ]{2,3}", span.strip()))

            if not has_legal_hint and (is_short_acronym or not has_caps_style):
                continue

        out.append(h)

    if "PER" in allowed:
        extra = _add_at_mentions(text)
        if extra:
            filtered: List[Treffer] = []
            for x in extra:
                if any(not (x.ende <= y.start or y.ende <= x.start) for y in out):
                    continue
                filtered.append(x)
            if filtered:
                out.extend(filtered)
                out.sort(key=lambda t: t.start)

    return out


def clean_ner_hits(text: str, hits: List[Treffer]) -> List[Treffer]:
    allowed = config.get("ner_labels", ["PER", "ORG"])
    return filter_ner_strict(text, hits, allowed_labels=allowed)