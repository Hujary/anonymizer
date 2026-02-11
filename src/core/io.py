###     Text-I/O Hilfsfunktionen (UTF-8, minimalistisch)
### __________________________________________________________________________
#
#  - Kapselt Datei-Ein-/Ausgabe für Textdateien
#  - Erzwingt UTF-8 Encoding für konsistente Verarbeitung
#  - Erstellt Zielverzeichnis automatisch beim Schreiben
#  - Keine Validierung, kein Error-Handling (Exceptions propagieren bewusst)


from pathlib import Path


# Liest vollständigen Dateiinhalt als UTF-8 String (keine Streaming-Verarbeitung)
def read_text(path: str) -> str:
    p = Path(path)
    return p.read_text(encoding="utf-8")


# Schreibt String als UTF-8 Datei; legt Parent-Ordner bei Bedarf an
def write_text(path: str, content: str) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")