from __future__ import annotations

import json
from pathlib import Path
from typing import List

from core import config


def _storage_path() -> Path:
    path_str = config.get("manual_types_file", "")
    if path_str:
        return Path(path_str)
    base_dir = Path(config.get("data_dir", "."))
    return base_dir / "manual_types.json"


def _load_raw() -> List[str]:
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
    types: List[str] = []
    for item in data:
        s = str(item or "").strip()
        if not s:
            continue
        types.append(s.upper())
    # unique, sort
    return sorted(set(types))


def _save_raw(types: List[str]) -> None:
    path = _storage_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(sorted(set(types)), f, ensure_ascii=False, indent=2)


def get_all_types() -> List[str]:
    return _load_raw()


def add_type(typ: str) -> str:
    norm = (typ or "").strip().upper()
    if not norm:
        raise ValueError("type must not be empty")
    types = _load_raw()
    if norm not in types:
        types.append(norm)
        _save_raw(types)
    return norm


def remove_type(typ: str) -> None:
    norm = (typ or "").strip().upper()
    types = _load_raw()
    filtered = [t for t in types if t != norm]
    _save_raw(filtered)