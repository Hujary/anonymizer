from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import List

from core import config


@dataclass(frozen=True)
class ManualToken:
    typ: str
    value: str


def _storage_path() -> Path:
    path_str = config.get("manual_tokens_file", "")
    if path_str:
        return Path(path_str)
    base_dir = Path(config.get("data_dir", "."))
    return base_dir / "manual_tokens.json"


def _load_raw() -> List[dict]:
    path = _storage_path()
    if not path.exists():
        return []
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return []
    if not isinstance(data, list):
        return []
    cleaned: List[dict] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        typ = str(item.get("typ", "")).upper().strip()
        value = str(item.get("value", "")).strip()
        if not value:
            continue
        if not typ:
            typ = "MISC"
        cleaned.append({"typ": typ, "value": value})
    return cleaned


def _save_raw(items: List[dict]) -> None:
    path = _storage_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)


def get_all() -> List[ManualToken]:
    raw = _load_raw()
    return [ManualToken(typ=item["typ"], value=item["value"]) for item in raw]


def add_manual_token(typ: str, value: str) -> ManualToken:
    norm_typ = (typ or "MISC").upper().strip()
    norm_val = (value or "").strip()
    if not norm_val:
        raise ValueError("manual token value must not be empty")

    items = _load_raw()

    # global eindeutiger Wert: ein Text darf nur in genau einer Kategorie vorkommen
    for item in items:
        if item["value"] == norm_val:
            existing_typ = item["typ"]
            if existing_typ == norm_typ:
                return ManualToken(typ=norm_typ, value=norm_val)
            raise ValueError(f"Wert '{norm_val}' existiert bereits in Kategorie '{existing_typ}'.")

    items.append({"typ": norm_typ, "value": norm_val})
    _save_raw(items)
    return ManualToken(typ=norm_typ, value=norm_val)


def remove_manual_token(typ: str, value: str) -> None:
    norm_typ = (typ or "MISC").upper().strip()
    norm_val = (value or "").strip()
    items = _load_raw()
    filtered = [item for item in items if not (item["typ"] == norm_typ and item["value"] == norm_val)]
    _save_raw(filtered)


def clear_all() -> None:
    _save_raw([])


def as_match_list() -> List[ManualToken]:
    return get_all()