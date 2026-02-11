###     Warning-Policy (Runtime-Suppression für Drittanbieter-Warnungen)
### __________________________________________________________________________
#
#  - Unterdrückt bestimmte Runtime-Warnings (z. B. urllib3)
#  - Aktivierung abhängig von DEBUG-Flag oder ENV-Variable
#  - ENV-Override: ANON_SILENCE_WARNINGS=1|true|yes erzwingt Stummschaltung
#  - Keine granulare Kategorie-Filterung außer Modulbasis
#  - Wird typischerweise beim App-Start einmalig aufgerufen


import warnings
import os


# Wendet Warning-Filter basierend auf Settings + ENV an
def apply_from_settings() -> None:
    try:
        from .einstellungen import DEBUG
    except Exception:
        DEBUG = False

    # ENV-Override zur globalen Unterdrückung von Warnungen
    silence_env = os.getenv("ANON_SILENCE_WARNINGS", "").lower() in ("1", "true", "yes")

    # Wenn nicht im Debug-Modus oder explizit gewünscht → urllib3-Warnings ignorieren
    if not DEBUG or silence_env:
        warnings.filterwarnings(
            "ignore",
            category=Warning,
            module=r"urllib3(\.|$)",
        )