###                   Hilfsdatei für globale Einstellungen
### ________________________________________________________________________

from pathlib import Path

# Projekt-Root: von .../src/core/einstellungen.py drei Ebenen nach oben
ROOT = Path(__file__).resolve().parents[2]

# Pfad als Path-Objekte für INPUT/OUTPUT
INPUT_PATH = ROOT / "input" / "example_input_invoice_de_v1.txt"
OUTPUT_PATH = ROOT / "output" / "masked.txt"

# Optional: sprechende Presets, falls du später weitere Varianten willst
NER_PRESETS = {
    "fast": "de_core_news_md",
    "large": "de_core_news_lg",
}

SPACY_MODELL = NER_PRESETS["large"]

# Default RUN flag
DEFAULT_RUN_COMMAND = "mask"

# Platzhalter für Maskierung
MASKIERUNGEN = {
    "E_MAIL": "[E_MAIL]",
    "TELEFON": "[TELEFON]",
    "PLZ": "[PLZ]",
    "ORT": "[ORT]",
    "STRASSE": "[STRASSE]",
    "IBAN": "[IBAN]",
    "BIC": "[BIC]",
    "USTID": "[USTID]",
    "DATUM": "[DATUM]",
    "NAME": "[NAME]",
    "ORGANISATION": "[ORGANISATION]",
    "RECHNUNGS_NUMMER": "[RECHNUNGS_NUMMER]",
    "URL": "[URL]",

    # Englisch (NER-kompatibel)
    "PER": "[NAME]",
    "ORG": "[ORGANISATION]",
    "LOC": "[ORT]",
    "GPE": "[ORT]",
    "DATE": "[DATUM]",
    "MISC": "[MASK]"
}

SETTINGS_DEFAULTS = {"use_regex": True, "use_ner": True, "debug_mask": False}

# Debug
DEBUG = False
DEBUG_MASK = False

# Detection
USE_REGEX = True
USE_NER = True

# REGEX
MASK_BIC = True