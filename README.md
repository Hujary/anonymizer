# Anonymizer

Prototypische Implementierung zur automatischen Maskierung personenbezogener Daten in Texten.

---

## BEFEHLE

### Virtuelle Umgebung anlegen
```bash
python3 -m venv .venv
```

### Virtuelle Umgebung aktivieren
**macOS / Linux (bash/zsh)**
```bash
source .venv/bin/activate
```

**Windows**
```bash
source .venv/Scripts/activate
```

### Abhängigkeiten installieren
```bash
pip install -r requirements.txt
```

### NER Installieren (aktuell MUSS)
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

## SCREENSHOTS - ANLEITUNG

**Hauptmaskierung: Dashboard**
Hier wird der Text eingefügt und automatisch (oder manuell) Maskiert, dieser wird dann rechts visuell dargestellt und kann kopiert werden an KI Systeme, etc.
<img width="2541" height="791" alt="image" src="https://github.com/user-attachments/assets/4f2e5a8c-592b-453d-9b95-f44d2dffc875" />
<img width="2312" height="869" alt="image" src="https://github.com/user-attachments/assets/f54e15a3-021f-4df7-a250-96a288a14ca3" />

Einstellungen
<img width="1898" height="904" alt="image" src="https://github.com/user-attachments/assets/2d1eb2e6-a854-4267-a0c3-62f6ebc2ce1e" />

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
