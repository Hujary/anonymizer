


# -------------------------------------------------------------------------------------------------------------------------------------------------
### BEFEHLE

# neue venv anlegen
python3 -m venv .venv

# Dependencyd Installieren
pip install -r requirements.txt

# Venv aktivieren
source .venv/bin/activate

# UI Starten
python src/ui_app.py 

# Produktion build
flet pack src/ui_app.py --name anonymizer --icon src/assets/logo.icns
# -------------------------------------------------------------------------------------------------------------------------------------------------





# -------------------------------------------------------------------------------------------------------------------------------------------------
### BEISPIELE

# Text maskieren (manuell)
(.venv) tompetzold@Mac src % python -m cli mask
maskiert → /Users/tompetzold/Desktop/RWU/Semester 10/Bachelorarbeit/bachelor_python/anonymizer/output/masked.txt (7 Treffer)

# UI starten
(.venv) tompetzold@MacBook-Air-M3-von-Tom anonymizer % python src/ui_app.py 
# -------------------------------------------------------------------------------------------------------------------------------------------------





# -------------------------------------------------------------------------------------------------------------------------------------------------
### ARCHITEKTUR

# run.py
  einfaches Userinterface um die Maskierung so einfach wie möglich zu maskieren

# src/cli.py    ->    „CLI“ = Command Line Interface 
  src/cli.py stellt die Kommandozeilenschnittstelle des Projekts bereit.
  Sie verarbeitet Benutzerbefehle (hello, echo, detect, mask), nimmt Argumente wie Eingabe- und Ausgabepfade entgegen und ruft intern die passenden Funktionen der Pipeline auf. Damit bildet sie den Einstiegspunkt zum Starten und Steuern der gesamten Anonymisierungslogik über die Konsole.
# -------------------------------------------------------------------------------------------------------------------------------------------------





# -------------------------------------------------------------------------------------------------------------------------------------------------
### ERKENNUNG PB DATEN - REGEX

### src/detectors/regex/contact.py
  Erkennt E-Mail-Adressen und Telefonnummern in typischen Formaten.
  Unterstützt internationale Schreibweisen (+49, 0049, 0...) sowie verschiedene Trennzeichen.
  Filtert falsch-positive Matches wie Rechnungsnummern oder Postleitzahlen.

### src/detectors/regex/date.py
  Erkennt Datumsangaben in unterschiedlichen Formaten (z. B. „17.10.2024“, „2024-10-17“, „17. Oktober 2024“).
  Normalisiert Monatsnamen (deutsch/englisch) und Zahlenformate.
  Verwendet zur Erkennung flexible Regex-Muster für Alltagstexte.

### src/detectors/regex/finance.py
  Erkennt IBANs und BICs nach offiziellen Strukturen.
  Prüft gültige Länderpräfixe (z. B. DE, AT, CH).
  Erkennt auch einfache Kontonummern und Banknamen, falls vorhanden.

### src/detectors/regex/location.py
  Erkennt Postleitzahlen (5-stellig, deutsch) und Ortsnamen im Umfeld typischer Adressangaben.
  Kombiniert PLZ-Erkennung mit Schlüsselwörtern wie „Adresse“, „Ort“, „Stadt“.
  Ziel: vollständige Adressbestandteile anonymisieren.

### src/detectors/regex/invoice.py
  Erkennt Rechnungsnummern und ähnliche Bezeichner wie „Invoice No. INV-2024-0012“ oder „Rechnungsnr. TS-2024-0915“.
  Berücksichtigt verschiedene Schreibweisen und Präfixe (TS-, INV-, RG-, RE- usw.).
  Maskiert ausschließlich tatsächliche IDs, nicht Wörter wie „Verwendungszweck“.
  Dient zur Erkennung personenbezogener Referenzen auf Buchungsvorgänge.
# -------------------------------------------------------------------------------------------------------------------------------------------------