# Anonymizer

Werkzeug zur automatischen Maskierung personenbezogener Daten in Texten
zur datenschutzkonformen Nutzung externer KI-Systeme.

---

## BEFEHLE

### Virtuelle Umgebung anlegen
```bash
python3 -m venv .venv
```

### Virtuelle Umgebung aktivieren
```bash
source .venv/bin/activate
```

### Abhängigkeiten installieren
```bash
pip install -r requirements.txt
```

### NER Manuell Installieren
```bash
python -m spacy download de_core_news_sm
python -m spacy download de_core_news_lg
```

### UI starten
```bash
python src/ui_app.py
```

### Produktions-Build (Desktop-App)
```bash
flet pack src/ui_app.py --name anonymizer --icon src/assets/logo.icns
```

---

## BEISPIELE

### Text manuell maskieren (CLI)
```bash
python -m cli mask
```

Beispielausgabe:
```
maskiert → output/masked.txt (7 Treffer)
```

### UI starten
```bash
python src/ui_app.py
```

---

## ARCHITEKTUR

### UI
**src/ui_app.py**  
Grafische Benutzeroberfläche zur interaktiven Maskierung von Texten.
Erlaubt die Auswahl von NER- und Regex-Typen sowie die Verwaltung von Maskierungssessions.

### CLI
**src/cli.py**  
Stellt die Kommandozeilenschnittstelle bereit.
Verarbeitet Benutzerbefehle (z. B. `detect`, `mask`) und übergibt Eingabe- und Ausgabepfade
an die interne Maskierungspipeline.

### Pipeline
Die Maskierung erfolgt in mehreren Schritten:

1. Erkennung personenbezogener Daten (NER + Regex)
2. Erzeugung kontextstabiler Maskierungstoken
3. Ersetzung der Originalwerte im Text
4. Optional: Rückauflösung über lokale Token-Mappings

---

## ERKENNUNG PERSONENBEZOGENER DATEN (REGEX)

### src/detectors/regex/contact.py
Erkennt:
- E-Mail-Adressen
- Telefonnummern

Unterstützt:
- internationale Schreibweisen (+49, 0049, 0…)
- unterschiedliche Trennzeichen  
Filtert typische Fehlklassifikationen (z. B. Rechnungsnummern).

---

### src/detectors/regex/date.py
Erkennt Datumsangaben in Formaten wie:
- `17.10.2024`
- `2024-10-17`
- `17. Oktober 2024`

Unterstützt:
- deutsche und englische Monatsnamen
- flexible Regex-Muster für Alltagstexte

---

### src/detectors/regex/finance.py
Erkennt:
- IBAN
- BIC

Prüft:
- gültige Länderpräfixe (z. B. DE, AT, CH)

Optional:
- einfache Kontonummern im Kontext finanzieller Angaben

---

### src/detectors/regex/location.py
Erkennt:
- deutsche Postleitzahlen (5-stellig)
- Ortsnamen im Adresskontext

Kombiniert:
- PLZ-Erkennung
- Schlüsselwörter wie „Adresse“, „Ort“, „Stadt“

Ziel: vollständige Adressbestandteile maskieren.

---

### src/detectors/regex/invoice.py
Erkennt Rechnungs- und Belegnummern, z. B.:
- `INV-2024-0012`
- `TS-2024-0915`
- `Rechnungsnr. RG-12345`

Berücksichtigt:
- unterschiedliche Präfixe (INV, RG, RE, TS, …)
- verschiedene Schreibweisen

Maskiert ausschließlich tatsächliche Identifikatoren,
keine allgemeinen Begriffe wie „Verwendungszweck“.

---

## HINWEIS ZUM DATENSCHUTZ

Das System zielt auf die Maskierung personenbezogener Daten ab.
Eine vollständige Anonymisierung gegen kontextuelle Re-Identifikation
kann nicht garantiert werden und ist nicht Ziel der Implementierung.