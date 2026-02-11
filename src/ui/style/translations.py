from __future__ import annotations

STRINGS = {
    "en": {
        "app.title": "anonymizer • Desktop",
        "dark_mode": "Dark Mode",
        "language": "Language",
        "lang.de": "German",
        "lang.en": "English",
        "save": "Save",
        "saved": "Settings saved",
        "apply": "Apply model",
        "loaded": "Loaded",
        "use_regex": "Use Regex",
        "use_ner": "Use NER",
        "debug_mask": "Debug_MASK",

        "settings.title": "Settings",
        "settings.all": "All",
        "settings.none": "None",
        "settings.recommended": "Recommended",
        "ner_model": "NER model",
        "ner_model.fast": "Smaller & faster (less accurate)",
        "ner_model.large": "Larger & slower (more accurate)",
        "ner_set_ok": "NER model set",
        "ner_set_fail": "Model change failed",

        "reversible": "Reversible masking",
        "input.label": "Input",
        "input.hint": "Paste or type text…",
        "output.label": "Output (masked)",

        "btn.mask": "Mask text",
        "btn.clear": "Clear",
        "btn.copy_out": "Copy output",

        "status.no_input": "No input.",
        "status.masked_base": "Masked: {total} | {src} | cfg: regex={rx} ner={ner} debug_mask={dbg}",
        "status.masked_rev":  "Masked: {total} | reversible: {ids} IDs | {src} | cfg: regex={rx} ner={ner} debug_mask={dbg}",

        "status.banner.none": "No GDPR-relevant findings in this text.",
        "status.banner.one": "Found 1 potential GDPR-relevant finding.",
        "status.banner.some": "Found {total} potential GDPR-relevant findings.",

        # Vault / Demask view
        "vault.apply_active": "Unmask text",
        "vault.active_map": "Active mapping (JSON)",
        "vault.masked_in": "Paste masked text here",
        "vault.demasked_out": "De-masked output",

        # NEW – demask input header + toggle + search placeholder
        "vault.input.title": "Paste masked text here",
        "vault.input.sub": (
            "Paste already anonymized text that should be restored to clear text using the active mapping. "
            "On the left you see the masked input, on the right the de-masked output."
        ),
        "vault.live_demask": "Live unmask",
        "search.placeholder": "Search…",

        # snackbar / mapping
        "sb.no_mapping": "No mapping available",
        "sb.map_copied": "Mapping copied to clipboard",
        "sb.map_saved": "Saved mapping to {path}",
        "sb.map_save_fail": "Save failed: {err}",

        # navigation
        "nav.dashboard": "Dashboard",
        "nav.vault": "Unmask",
        "nav.dictionary": "Dictionary",
        "nav.settings": "Settings",

        # help overlay
        "help.title": "Welcome to anonymizer",
        "help.intro": (
            "This app helps you mask sensitive information in text and unmask it again when needed. "
            "You can safely share real content without exposing the original data."
        ),
        "help.dashboard.body": (
            "Here you work with the original text: paste your content, run automatic masking and review all "
            "detected tokens. You can edit tokens, add new ones manually and immediately see how the masked "
            "output on the right changes."
        ),
        "help.vault.body": (
            "In this view you paste already masked text, for example from the Dashboard or from a file. Using "
            "the currently active mapping, placeholders are converted back to their original values – useful when "
            "you later need the full clear-text version internally."
        ),
        "help.dictionary.body": (
            "Manage your own terms, names or patterns that should be taken into account during masking. This lets "
            "you handle recurring domain-specific terms, project names or internal identifiers consistently, even if "
            "the standard model does not detect them automatically."
        ),
        "help.settings.body": (
            "Configure language, the NER model and which entity / regex types are used. You can fine-tune which "
            "categories should be detected and masked – for example only people and email addresses, or a richer "
            "set including IBANs, invoice numbers and more."
        ),
        "help.close": "Close",

        "help.dashboard.bullet": "Dashboard",
        "help.vault.bullet": "Unmask",
        "help.dictionary.bullet": "Dictionary",
        "help.settings.bullet": "Settings",

        # token source labels
        "token.src.ner": "NER",
        "token.src.regex": "Regex",
        "token.src.auto": "Automatic",
    },
    "de": {
        "app.title": "anonymizer • Desktop",
        "dark_mode": "Dunkler Modus",
        "language": "Sprache",
        "lang.de": "Deutsch",
        "lang.en": "Englisch",
        "save": "Speichern",
        "saved": "Einstellungen gespeichert",
        "apply": "Modell anwenden",
        "loaded": "Geladen",
        "use_regex": "Regex verwenden",
        "use_ner": "NER verwenden",
        "debug_mask": "Debug_MASK",

        "settings.title": "Einstellungen",
        "settings.all": "Alle",
        "settings.none": "Keine",
        "settings.recommended": "Empfohlen",
        "ner_model": "NER-Modell",
        "ner_model.fast": "Kleiner & schneller (weniger genau)",
        "ner_model.large": "Größer & langsamer (genauer)",
        "ner_set_ok": "NER-Modell gesetzt",
        "ner_set_fail": "Modellwechsel fehlgeschlagen",

        "reversible": "Reversible Maskierung",
        "input.label": "Eingabe",
        "input.hint": "Text einfügen oder schreiben…",
        "output.label": "Ausgabe (maskiert)",

        "btn.mask": "Text maskieren",
        "btn.clear": "Leeren",
        "btn.copy_out": "Ausgabe kopieren",

        "status.no_input": "Keine Eingabe.",
        "status.masked_base": "Maskiert: {total} | {src} | cfg: regex={rx} ner={ner} debug_mask={dbg}",
        "status.masked_rev":  "Maskiert: {total} | reversibel: {ids} IDs | {src} | cfg: regex={rx} ner={ner} debug_mask={dbg}",

        "status.banner.none": "Keine DSGVO-relevanten Treffer in diesem Text gefunden.",
        "status.banner.one": "Es wurde 1 DSGVO-relevanter Treffer gefunden.",
        "status.banner.some": "Es wurden {total} DSGVO-relevante Treffer gefunden.",

        # Vault / Demask view
        "vault.apply_active": "Text demaskieren",
        "vault.active_map": "Aktives Mapping (JSON)",
        "vault.masked_in": "Hier maskierten Text einfügen",
        "vault.demasked_out": "Demaskierte Ausgabe",

        # NEU – Demask Überschriften + Toggle + Suche
        "vault.input.title": "Maskierten Text hier eingeben oder einfügen",
        "vault.input.sub": (
            "Füge bereits anonymisierten Text ein, der mithilfe der aktiven Zuordnung wieder in Klartext "
            "umgewandelt werden soll. Links siehst du den maskierten Text, rechts die demaskierte Ausgabe."
        ),
        "vault.live_demask": "Live demaskieren",
        "search.placeholder": "Suchen…",

        # Snackbar / Mapping
        "sb.no_mapping": "Kein Mapping vorhanden",
        "sb.map_copied": "Mapping in Zwischenablage kopiert",
        "sb.map_saved": "Mapping gespeichert nach {path}",
        "sb.map_save_fail": "Speichern fehlgeschlagen: {err}",

        # Navigation
        "nav.dashboard": "Dashboard",
        "nav.vault": "Demaskieren",
        "nav.dictionary": "Wörterbuch",
        "nav.settings": "Einstellungen",

        # Hilfe-Overlay
        "help.title": "Willkommen im anonymizer",
        "help.intro": (
            "Diese App hilft dir dabei, sensible Informationen in Texten zu maskieren und bei Bedarf wieder zu "
            "demaskieren. So kannst du echte Inhalte sicher mit anderen teilen, ohne die Originaldaten offenzulegen."
        ),
        "help.dashboard.body": (
            "Hier arbeitest du mit dem ursprünglichen Text: Du fügst deinen Inhalt ein, startest die automatische "
            "Maskierung und siehst anschließend alle erkannten Tokens. Du kannst Tokens bearbeiten, neue hinzufügen "
            "und direkt verfolgen, wie sich die Ausgabe im rechten Feld verändert."
        ),
        "help.vault.body": (
            "In diesem Bereich fügst du bereits maskierten Text ein, zum Beispiel aus dem Dashboard oder aus einer "
            "Datei. Mithilfe des aktuell aktiven Mappings werden die Platzhalter wieder in die ursprünglichen Werte "
            "zurückverwandelt – ideal, wenn du maskierte Texte später intern wieder im Klartext benötigst."
        ),
        "help.dictionary.body": (
            "Im Wörterbuch verwaltest du eigene Begriffe, Namen oder Muster, die bei der Maskierung zusätzlich "
            "berücksichtigt werden sollen. So kannst du wiederkehrende Fachbegriffe, Projektnamen oder firmenspezifische "
            "Informationen konsistent behandeln, auch wenn sie vom Standardmodell nicht automatisch erkannt werden."
        ),
        "help.settings.body": (
            "Unter Einstellungen legst du Sprache, NER-Modell und die zu verwendenden Entity- und Regex-Typen fest. "
            "Du kannst hier also feinsteuern, welche Kategorien überhaupt erkannt und maskiert werden sollen – zum "
            "Beispiel nur Personen und E-Mail-Adressen oder ein umfangreicheres Set inklusive IBAN, Rechnungsnummern "
            "und mehr."
        ),
        "help.close": "Schließen",

        "help.dashboard.bullet": "Dashboard",
        "help.vault.bullet": "Demaskieren",
        "help.dictionary.bullet": "Wörterbuch",
        "help.settings.bullet": "Einstellungen",

        # Token-Quellen
        "token.src.ner": "NER",
        "token.src.regex": "Regex",
        "token.src.auto": "Automatisch",
    },
}


def t(lang: str, key: str, **kwargs) -> str:
    lang = lang if lang in STRINGS else "en"
    s = STRINGS[lang].get(key, key)
    try:
        return s.format(**kwargs)
    except Exception:
        return s