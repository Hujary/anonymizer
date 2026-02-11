###     Globale Einstellungen (Pfadkonstanten + Mask-Presets + Defaults)
### ________________________________________________________________________
#
#  - Definiert projektweite Konstanten ohne Laufzeit-Logik
#  - Enthält Pfaddefinitionen relativ zum Repo-Root
#  - Definiert spaCy-Modell-Presets + Default-Modell
#  - Enthält zentrale Mask-Strings pro Entitätstyp (Policy-Mapping)
#  - Beinhaltet Legacy-/Fallback-Flags für Detection und Debug
#  - Wird von Core, Pipeline und UI konsumiert (keine zyklischen Abhängigkeiten)


from pathlib import Path


# Projekt-Root (von .../src/core/einstellungen.py zwei Ebenen nach oben)
ROOT = Path(__file__).resolve().parents[2]


# Beispiel-IO-Pfade (nur für CLI/Tests relevant, nicht für UI-Workflow)
INPUT_PATH = ROOT / "input" / "example_input_invoice_de_v1.txt"
OUTPUT_PATH = ROOT / "output" / "masked.txt"


# spaCy-Modell-Presets (ermöglichen Umschalten ohne harten Modellnamen)
NER_PRESETS = {
    "fast": "de_core_news_md",
    "large": "de_core_news_lg",
}


# Default spaCy-Modell (wird von NER-Modul verwendet)
SPACY_MODELL = NER_PRESETS["large"]


# Default CLI-Command (falls kein Argument übergeben wird)
DEFAULT_RUN_COMMAND = "mask"


# Zentrale Maskierungs-Policy:
# Mapping: Entitätslabel → Mask-String (nicht-reversibler Modus)
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

    # spaCy-/NER-kompatible Labels (EN → interne Mask-Policy)
    "PER": "[NAME]",
    "ORG": "[ORGANISATION]",
    "LOC": "[ORT]",
    "GPE": "[ORT]",
    "DATE": "[DATUM]",
    "MISC": "[MASK]",
}


# Default-Flags für Detection (Fallback, falls config.json fehlt)
SETTINGS_DEFAULTS = {
    "use_regex": True,
    "use_ner": True,
    "debug_mask": False,
}


# Globale Debug-Flags (Legacy / nicht dynamisch via config)
DEBUG = False
DEBUG_MASK = False


# Globale Detection-Flags (Legacy-Fallback, wenn Config nicht genutzt wird)
USE_REGEX = True
USE_NER = True


# Regex-spezifisches Feature-Flag (z.B. BIC-Erkennung aktivieren/deaktivieren)
MASK_BIC = True