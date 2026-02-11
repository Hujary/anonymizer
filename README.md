# Anonymizer

Prototypische Implementierung zur automatischen Maskierung personenbezogener Daten in Texten.
- Erkennung durch Kombination von REGEX, NER und CUSTOM_TOKEN

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

### NER Installieren (aktuell MUSS Abhängigkeit)
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

### Dashboard - Maskierung ###
Hier wird der Text eingefügt und automatisch (oder manuell) Maskiert, dieser wird dann rechts visuell dargestellt und kann kopiert werden an KI Systeme, etc.

<img width="2541" height="791" alt="image" src="https://github.com/user-attachments/assets/4f2e5a8c-592b-453d-9b95-f44d2dffc875" />
<img width="2312" height="869" alt="image" src="https://github.com/user-attachments/assets/f54e15a3-021f-4df7-a250-96a288a14ca3" />

### Demaskierung ###
Hier kann die Antwort der KI eingesetzt werden und wird automatisch (wenn Token nicht abgelaufen) demaskiert.

<img width="2560" height="735" alt="image" src="https://github.com/user-attachments/assets/88b11b46-d0ab-49aa-b92d-432826d1d378" />
<img width="2320" height="627" alt="image" src="https://github.com/user-attachments/assets/8ba611da-771b-4925-b2cd-aa1d6d23ce4b" />

### Wörterbuch ###
Hier kann man Custom Token ergänzen welche bei JEDEM Maskierungsprozess priorisiert erkannt werden & sieht alle erkannten (Key/Token) Paare der aktiven Sessions

<img width="2560" height="1084" alt="image" src="https://github.com/user-attachments/assets/c20f319f-f55f-4712-8509-630549bc77b4" />


### Einstellungen ###
Hier kann man Einstellen was der Maskierungsprozess erkennt (NER, REGEX) und einige zusätzliche Einstellungen (Sprache, Darkmode, ..)

<img width="1898" height="904" alt="image" src="https://github.com/user-attachments/assets/2d1eb2e6-a854-4267-a0c3-62f6ebc2ce1e" />

---

## ARCHITEKTUR

### Projektstruktur
```text
repo-root/
├─ src/
│  ├─ ui_app.py
│  ├─ cli.py
│  ├─ app_store.py
│  │
│  ├─ core/
│  │  ├─ __init__.py
│  │  ├─ config.py
│  │  ├─ io.py
│  │  ├─ types.py
│  │  └─ warnpolicy.py
│  │
│  ├─ services/
│  │  ├─ __init__.py
│  │  ├─ anonymizer.py
│  │  ├─ session_manager.py
│  │  ├─ manual_tokens.py
│  │  └─ manual_categories.py
│  │
│  ├─ detectors/
│  │  ├─ __init__.py
│  │  ├─ ner/
│  │  │  ├─ __init__.py
│  │  │  ├─ ner_core.py
│  │  │  └─ filters.py
│  │  ├─ regex/
│  │  │  ├─ __init__.py
│  │  │  ├─ contact.py
│  │  │  ├─ date.py
│  │  │  ├─ finance.py
│  │  │  ├─ invoice.py
│  │  │  ├─ location.py
│  │  │  └─ url.py
│  │  └─ custom/
│  │     ├─ __init__.py
│  │     └─ manual_dict.py
│  │
│  ├─ pipeline/
│  │  ├─ __init__.py
│  │  ├─ detect.py
│  │  ├─ mask.py
│  │  └─ demask.py
│  │
│  ├─ ui/
│  │  ├─ __init__.py
│  │  ├─ style/
│  │  │  ├─ __init__.py
│  │  │  ├─ theme.py
│  │  │  ├─ translations.py
│  │  │  └─ components.py
│  │  ├─ routing/
│  │  │  ├─ __init__.py
│  │  │  └─ router.py
│  │  ├─ shared/
│  │  │  ├─ __init__.py
│  │  │  ├─ flet_helpers.py
│  │  │  └─ validation.py
│  │  └─ features/
│  │     ├─ __init__.py
│  │     ├─ dashboard/
│  │     │  ├─ __init__.py
│  │     │  ├─ view.py
│  │     │  ├─ state.py
│  │     │  ├─ actions.py
│  │     │  ├─ token_renderer.py
│  │     │  ├─ masking_engine.py
│  │     │  └─ helpers.py
│  │     ├─ dictionary/
│  │     │  ├─ __init__.py
│  │     │  └─ view.py
│  │     ├─ demask/
│  │     │  ├─ __init__.py
│  │     │  └─ view.py
│  │     └─ settings/
│  │        ├─ __init__.py
│  │        └─ view.py
│  │
├─ assets/
├─ config.json                          # zentrale Policy- und Feature-Konfigurationsdatei für Pipeline und UI
└─ README.md
```

---


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

## HINWEIS ZUM DATENSCHUTZ
Eine vollständige Anonymisierung gegen kontextuelle Re-Identifikation
kann nicht garantiert werden und ist nicht Ziel der Implementierung.
