###     Manuelle Kategorien (Custom-Entity-Typen Persistenz)
### __________________________________________________________________________
#
#  - Persistiert benutzerdefinierte Entity-Typen als einfache String-Liste (JSON)
#  - Normalisiert alle Typen auf UPPERCASE
#  - Unterstützt Migration von alter Datei-Location (repo_root/manual_types.json → Data/)
#  - Verhindert Duplikate durch Set-Semantik bei add_type
#  - Liefert deterministisch sortierte Liste für UI + Pipeline


from __future__ import annotations

import json
from pathlib import Path

from core.paths import manual_types_path, repo_root


# Liest JSON-Liste ein und normalisiert alle Einträge auf getrimmte UPPERCASE-Strings
def _read_list(path: Path) -> list[str]:
    if not path.exists():
        return []

    raw = path.read_text(encoding="utf-8").strip()
    if not raw:
        return []

    data = json.loads(raw)

    if not isinstance(data, list):
        return []

    out: list[str] = []

    for x in data:
        s = str(x).strip().upper()
        if s:
            out.append(s)

    return out



# Schreibt String-Liste als JSON-Datei (legt Parent-Ordner bei Bedarf an)
def _write_list(path: Path, items: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(items, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )



# Migriert alte Datei-Location (repo_root/manual_types.json) in neue Data-Struktur
def _migrate_from_repo_root_if_needed() -> None:
    new_path = manual_types_path()

    if new_path.exists():
        return

    old_path = repo_root() / "manual_types.json"
    if not old_path.exists():
        return

    new_path.parent.mkdir(parents=True, exist_ok=True)
    new_path.write_text(old_path.read_text(encoding="utf-8"), encoding="utf-8")



# Liefert alle gespeicherten Custom-Typen
def get_all_types() -> list[str]:
    _migrate_from_repo_root_if_needed()
    return _read_list(manual_types_path())



# Fügt neuen Typ hinzu (validiert, normalisiert, dedupliziert, sortiert)
def add_type(name: str) -> str:
    _migrate_from_repo_root_if_needed()

    typ = (name or "").strip().upper()

    if not typ:
        raise ValueError("Kategorie darf nicht leer sein.")

    path = manual_types_path()
    items = _read_list(path)

    if typ not in items:
        items.append(typ)
        items = sorted(set(items), key=str.upper)
        _write_list(path, items)

    return typ



# Entfernt einen Typ aus Persistenz (falls vorhanden)
def remove_type(name: str) -> None:
    _migrate_from_repo_root_if_needed()

    typ = (name or "").strip().upper()

    path = manual_types_path()
    items = _read_list(path)

    items = [x for x in items if x != typ]

    _write_list(path, items)