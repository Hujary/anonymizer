###     Pfad-Resolver (Repo-Root + Data-Directory + Persistenzpfade)
### __________________________________________________________________________
#
#  - Ermittelt projektweiten Repo-Root relativ zur Dateistruktur
#  - Unterstützt optionales Override des Data-Verzeichnisses via ENV-Variable
#    (ANONYMIZER_DATA_DIR)
#  - Stellt sicher, dass Data-Verzeichnis existiert (mkdir bei Zugriff)
#  - Liefert zentrale Persistenzpfade für manual_tokens.json / manual_types.json
#  - Keine globale Zustandsverwaltung, reine Pfad-Funktionen


from __future__ import annotations

import os
from pathlib import Path


# Ermittelt Repo-Root (zwei Ebenen über src/core/)
def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]



# Liefert Data-Verzeichnis:
# 1) Falls ENV gesetzt → dieses verwenden
# 2) Sonst <repo-root>/data
def data_dir() -> Path:
    env = (os.getenv("ANONYMIZER_DATA_DIR") or "").strip()

    if env:
        p = Path(env).expanduser().resolve()
        p.mkdir(parents=True, exist_ok=True)
        return p

    p = repo_root() / "data"
    p.mkdir(parents=True, exist_ok=True)
    return p



# Persistenzpfad für manuelle Tokens
def manual_tokens_path() -> Path:
    return data_dir() / "manual_tokens.json"



# Persistenzpfad für manuelle Kategorien
def manual_types_path() -> Path:
    return data_dir() / "manual_types.json"