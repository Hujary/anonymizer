from __future__ import annotations
import json
from pathlib import Path
from typing import Any, Dict

# Pfad: <repo-root>/config.json
_CONFIG_PATH = Path(__file__).resolve().parents[1] / "config.json"

_DEFAULTS: Dict[str, Any] = {
    "use_regex": True,
    "use_ner": True,
    "debug_mask": False,
    "spacy_model": "de_core_news_lg"
}

_CONFIG: Dict[str, Any] | None = None

def _ensure_loaded() -> None:
    global _CONFIG
    if _CONFIG is not None:
        return
    if not _CONFIG_PATH.exists():
        _CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        _CONFIG = dict(_DEFAULTS)
        _save_file(_CONFIG)
        return
    try:
        data = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            data = {}
    except Exception:
        data = {}
    merged = dict(_DEFAULTS)
    merged.update(data)
    _CONFIG = merged

def _save_file(data: Dict[str, Any]) -> None:
    tmp = _CONFIG_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(_CONFIG_PATH)

def load() -> Dict[str, Any]:
    _ensure_loaded()
    return dict(_CONFIG)  # Kopie

def save(values: Dict[str, Any]) -> Dict[str, Any]:
    _ensure_loaded()
    _CONFIG.update(values)
    _save_file(_CONFIG)
    return dict(_CONFIG)

def get(key: str, default: Any = None) -> Any:
    _ensure_loaded()
    return _CONFIG.get(key, _DEFAULTS.get(key, default))

def set(key: str, value: Any) -> Dict[str, Any]:
    return save({key: value})

def get_flags() -> Dict[str, Any]:
    _ensure_loaded()
    return {
        "use_regex": bool(_CONFIG.get("use_regex", _DEFAULTS["use_regex"])),
        "use_ner": bool(_CONFIG.get("use_ner", _DEFAULTS["use_ner"])),
        "debug_mask": bool(_CONFIG.get("debug_mask", _DEFAULTS["debug_mask"])),
    }

def set_flags(*, use_regex: bool | None = None, use_ner: bool | None = None, debug_mask: bool | None = None) -> Dict[str, Any]:
    payload: Dict[str, Any] = {}
    if use_regex is not None:
        payload["use_regex"] = bool(use_regex)
    if use_ner is not None:
        payload["use_ner"] = bool(use_ner)
    if debug_mask is not None:
        payload["debug_mask"] = bool(debug_mask)
    return save(payload)