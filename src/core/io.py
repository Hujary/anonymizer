###     Hilfsdatei zum ein und auslesen von Text (I/O)
### __________________________________________________________________________

from pathlib import Path

# liest den kompletten Inhalt einer Textdatei und gibt ihn als String zurück (INPUT)
def read_text(path: str) -> str:
    p = Path(path)
    return p.read_text(encoding="utf-8")

# schreibt Text in eine Datei und erstellt den Zielordner automatisch, falls er nicht existiert (OUTPUT)
def write_text(path: str, content: str) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")