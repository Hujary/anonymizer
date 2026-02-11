###     Strikter NER-Postfilter (Qualitätssicherung für PER / ORG)
### __________________________________________________________________________
#
#  - Entfernt typische spaCy-Fehlklassifikationen (Grußwörter, Rollen, Metabegriffe)
#  - Erzwingt harte Regeln für ORG (Rechtsform-Hinweis oder starke Großschreibung)
#  - Normalisiert PER-Treffer auf echte Namenssegmente
#  - Unterstützt statische + konfigurierbare Person-Hints
#  - Verhindert numerische / triviale / zu kurze Entitäten
#  - Label-Whitelist wird dynamisch aus der App-Config geladen


import re
from typing import List, Iterable, Set
from core.typen import Treffer
from core import config


# Wörter, die fast immer als Gruß/Floskel vorkommen und NIE als Entität gelten sollen
COMMON_GREETING_WORDS = {
    "hallo", "hi", "hey", "danke", "vielen", "gruß", "grüße",
    "mit", "freundlichen", "beste", "liebe", "servus", "moin",
}


# Kennzeichen (Suffixe), die typischerweise auf Organisationen hinweisen
ORG_HINTS = {
    " gmbh", " ag", " kg", " ug", " gbr", " mbh",
    " kgaa", " e.v", " ev", " verein", " eg",
}


# Wörter, die NICHT zu einer echten Organisation gehören dürfen
ORG_STOPWORDS = {
    "ordner", "team", "teams", "postfach", "inbox",
    "gruppe", "folder", "verzeichnis", "kanal",
    "channel", "chat", "projekt", "abteilung",
    "bereich", "rolle", "rollen", "konto",
    "account", "sammlung", "collection", "upload",
}


# Tokens, die spaCy häufig fälschlich als PER erkennt → strikt blockieren
PER_BAD_TOKENS = {
    "Hallo", "Hi", "Hey", "Danke", "Mit",
    "Freundlichen", "Beste", "Liebe",
    "Servus", "Moin", "Team", "Upload",
    "HR", "Budgetfreigabe",
}


# Statische Person-Hints (immer als PER interpretieren)
PER_HINTS_STATIC = {"Tom", "Max", "Anna", "Julia"}


# Dynamische, vom User konfigurierbare Person-Hints
PER_HINTS_CONFIG = set(config.get("ner_person_hints", []))


# Zusammengeführte Person-Prioritätsliste
PER_HINTS: Set[str] = {
    h.strip() for h in (PER_HINTS_STATIC | PER_HINTS_CONFIG) if h.strip()
}


# Regex für echte Namensbestandteile (Großschreibung + optionale Bindestriche)
NAME_TOKEN_RE = re.compile(r"[A-ZÄÖÜ][a-zäöüß]+(?:-[A-ZÄÖÜ][a-zäöüß]+)?")


# Prüft, ob ein Span rein numerisch, symbolisch oder zu kurz ist
def _is_numeric_or_short(span: str) -> bool:
    s = span.strip()
    if not s:
        return True
    if re.fullmatch(r"[0-9\-\s/.()+]{1,}", s):
        return True
    if len(s) <= 2:
        return True
    return False


# Extrahiert aus einem PER-Treffer den tatsächlichen Namensteil
def _normalize_person_hit(text: str, hit: Treffer) -> Treffer | None:

    span_full = text[hit.start : hit.ende]

    # Segmentierung grober Teilbereiche
    for chunk in re.split(r"[\n,;|]+", span_full):
        chunk = chunk.strip()
        if not chunk:
            continue

        tokens = []

        # Tokenisierung + sofortiger Abbruch bei verbotenen Tokens
        for m in re.finditer(r"\b\w[\w\-ÄÖÜäöüß]*\b", chunk):
            tok = m.group(0)
            if tok in PER_BAD_TOKENS:
                break
            tokens.append((tok, m.start(), m.end()))

        if not tokens:
            continue

        # Suche 1–2 valide Namensbestandteile
        name_st = None
        name_en = None
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

        abs_start = hit.start + span_full.index(chunk) + name_st
        abs_end = hit.start + span_full.index(chunk) + name_en

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


# Strenger Hauptfilter für NER-Ergebnisse
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
        span = text[h.start : h.ende].strip()

        if not span:
            continue

        # Person-Hints erzwingen PER-Label
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

        # Grußformeln entfernen
        if low in COMMON_GREETING_WORDS:
            continue

        # Numerische / triviale Treffer entfernen
        if _is_numeric_or_short(span):
            continue

        # Personen-Normalisierung
        if L == "PER":
            nh = _normalize_person_hit(text, h)
            if nh is None:
                continue
            h = nh

        # ORG-Speziallogik
        if L == "ORG":

            low_span = " " + span.lower()

            # Blacklist prüfen
            if any(sw in low_span for sw in ORG_STOPWORDS):
                continue

            # Bindestrich-Teil prüfen
            if "-" in span:
                right = span.split("-", 1)[1].strip().lower()
                if right in ORG_STOPWORDS:
                    continue

            # Rechtsform oder starke Großschreibung erforderlich
            has_legal_hint = any(hint in low_span for hint in ORG_HINTS)
            caps_count = sum(1 for c in span if c.isupper())
            has_caps_style = caps_count >= 3
            is_short_acronym = bool(re.fullmatch(r"[A-ZÄÖÜ]{2,3}", span.strip()))

            if not has_legal_hint and (is_short_acronym or not has_caps_style):
                continue

        out.append(h)

    return out


# Wrapper, der erlaubte Labels aus der App-Config zieht
def clean_ner_hits(text: str, hits: List[Treffer]) -> List[Treffer]:
    allowed = config.get("ner_labels", ["PER", "ORG"])
    return filter_ner_strict(text, hits, allowed_labels=allowed)