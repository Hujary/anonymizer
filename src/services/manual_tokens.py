from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import List

from core.paths import manual_tokens_path, repo_root


@dataclass(frozen=True)
class ManualToken:
    typ: str
    value: str


def _read_json(path: Path) -> list[dict]:
    if not path.exists():
        return []
    raw = path.read_text(encoding="utf-8").strip()
    if not raw:
        return []
    data = json.loads(raw)
    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]
    return []


def _write_json(path: Path, items: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")


def _migrate_from_repo_root_if_needed() -> None:
    new_path = manual_tokens_path()
    if new_path.exists():
        return
    old_path = repo_root() / "manual_tokens.json"
    if not old_path.exists():
        return
    new_path.parent.mkdir(parents=True, exist_ok=True)
    new_path.write_text(old_path.read_text(encoding="utf-8"), encoding="utf-8")


def get_all() -> List[ManualToken]:
    _migrate_from_repo_root_if_needed()
    items = _read_json(manual_tokens_path())
    out: list[ManualToken] = []
    for it in items:
        typ = str(it.get("typ", "")).strip().upper()
        value = str(it.get("value", "")).strip()
        if not typ or not value:
            continue
        out.append(ManualToken(typ=typ, value=value))
    return out


def add_manual_token(typ: str, value: str) -> None:
    _migrate_from_repo_root_if_needed()
    typ_n = (typ or "").strip().upper()
    val_n = (value or "").strip()
    if not typ_n:
        raise ValueError("typ darf nicht leer sein.")
    if not val_n:
        raise ValueError("value darf nicht leer sein.")

    path = manual_tokens_path()
    items = _read_json(path)

    for it in items:
        if str(it.get("typ", "")).strip().upper() == typ_n and str(it.get("value", "")).strip() == val_n:
            return

    items.append({"typ": typ_n, "value": val_n})
    items.sort(key=lambda x: (str(x.get("typ", "")).upper(), str(x.get("value", "")).lower()))
    _write_json(path, items)


def remove_manual_token(typ: str, value: str) -> None:
    _migrate_from_repo_root_if_needed()
    typ_n = (typ or "").strip().upper()
    val_n = (value or "").strip()

    path = manual_tokens_path()
    items = _read_json(path)

    new_items = [
        it
        for it in items
        if not (
            str(it.get("typ", "")).strip().upper() == typ_n
            and str(it.get("value", "")).strip() == val_n
        )
    ]
    _write_json(path, new_items)


def as_match_list() -> List[ManualToken]:
    """
    Liefert die persistenten ManualTokens als Liste für den Custom-Detector.

    Wichtig für Matching:
    - längere Werte zuerst, damit z.B. "Briachstraße 2" vor "Briachstraße" gematcht wird
    - danach stabil nach Typ und Wert sortiert
    """
    tokens = get_all()
    tokens.sort(key=lambda t: (-len(t.value), t.typ, t.value.lower()))
    return tokens