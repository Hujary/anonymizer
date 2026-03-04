###     Anonymizer Wrapper (Stable Tokens + Mapping + De-Anonymisierung)
### __________________________________________________________________________
#
#  - Orchestriert Maskierung über pipeline.anonymisieren.maskiere
#  - Unterstützt zwei Modi:
#    - nicht-reversibel: nutzt Masking-Engine direkt (kein Mapping)
#    - reversibel: erzeugt stabile Tokens + token->original Mapping
#  - Stable Tokens basieren auf HMAC-SHA256(label::value, secret) und sind deterministisch pro Wert,
#    aber ohne Secret nicht offline nachrechenbar (Schutz gegen Dictionary-/Rate-Angriffe)
#  - Token-Kürzung: 16 Hex (=64 Bit) als Kompromiss aus Lesbarkeit und Kollisionsrisiko
#  - De-Anonymisierung ersetzt Tokens rückwärts (längste Tokens zuerst) via Mapping
#  - mapping_to_json serialisiert Mapping deterministisch lesbar (indentiert)
#
#  Hinweis:
#  - Reversibilität entsteht ausschließlich über das Mapping. Das Token selbst ist nicht umkehrbar.
#  - TTL/Reset (z.B. alle 24h) betrifft typischerweise das Mapping und/oder den Secret-Key-Rotation-Zyklus.


from __future__ import annotations

import json
import hashlib
import hmac
from typing import Tuple, Dict, List, Any

from pipeline.anonymisieren import maskiere


# Prototyp: Secret-Key hardcoded.
# Produktion: aus Secret-Store / Env, pro Deployment/Service; optional Key-Rotation (v1/v2) mit Version im Token.
_SECRET_KEY = b"prototype-secret-change-me"


# Erzeugt deterministischen Token aus Label und Originalwert (keyed hash, nicht umkehrbar)
def _stable_token(label: str, value: str) -> str:
    msg = (label.upper() + "::" + (value or "")).encode("utf-8")
    h = hmac.new(_SECRET_KEY, msg, hashlib.sha256).hexdigest()[:16]
    return f"[{label.upper()}_{h}]"


# Maskiert Text und liefert (masked_text, mapping, hits)
def anonymize(text: str, reversible: bool = False) -> Tuple[str, Dict[str, str], List[Any]]:

    # Nicht-reversibel: delegiert vollständig an Masking-Engine, kein Mapping
    if not reversible:
        masked, hits = maskiere(text, reversible=False)
        return masked, {}, hits

    # Reversibel: Detektion/Masking laufen, Token-Ersetzung wird hier selbst gebaut
    _, hits = maskiere(text, reversible=True)

    # Treffer nach Startposition sortieren, um den Text deterministisch aufzubauen
    hits_sorted = sorted(hits, key=lambda h: getattr(h, "start"))

    parts: List[str] = []
    mapping: Dict[str, str] = {}
    pos = 0

    # Baut Output-Text als Sequenz aus "unverändertem Text" + "Token"
    for h in hits_sorted:
        s = getattr(h, "start")
        e = getattr(h, "ende")
        label = getattr(h, "label").upper()

        parts.append(text[pos:s])

        original = text[s:e]
        tag = _stable_token(label, original)

        parts.append(tag)
        mapping[tag] = original

        pos = e

    parts.append(text[pos:])
    masked_with_ids = "".join(parts)

    return masked_with_ids, mapping, hits_sorted


# Ersetzt Tokens zurück auf Originalwerte (längste Tokens zuerst zur Kollisionsvermeidung)
def de_anonymize(text: str, mapping: Dict[str, str]) -> str:
    for k in sorted(mapping.keys(), key=lambda s: -len(s)):
        text = text.replace(k, mapping[k])
    return text


# Serialisiert token->original Mapping als JSON (UTF-8 sicher, lesbar formatiert)
def mapping_to_json(mapping: Dict[str, str]) -> str:
    return json.dumps(mapping, ensure_ascii=False, indent=2)