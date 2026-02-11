from __future__ import annotations

from ui.style.theme import THEMES
from core import config
from services.session_manager import SessionManager, SESSION_TTL_SECONDS


class AppStore:
    """
    Zentrale In-Memory-Zustandsverwaltung der Anwendung.

    Diese Klasse ist der einzige Ort, an dem:
    - globale UI-relevante Zustände gehalten werden
    - Maskierungs-Mappings zwischengespeichert werden
    - Dashboard-Draft-Texte persistiert werden
    - Session-Management angebunden ist

    Keine UI-Logik, keine Rendering-Logik – nur Zustand.
    """

    def __init__(self):
        # Aktueller Theme-Name (aus Config geladen oder Fallback)
        self.theme_name = self._load_theme_name()

        # Aktuelles Theme-Dict (Farben etc.)
        self.theme = THEMES[self.theme_name]

        # Aktuelle Sprache (de/en)
        self.lang = self._load_lang()

        # Letztes aktives Mapping (token -> original value)
        self.last_mapping = {}

        # Letzte Treffer (NER/Regex etc.), wie vom Service geliefert
        self.last_hits = []

        # Letzter maskierter Text
        self.last_masked_text = ""

        # Letzter Originaltext (Basis für Remask/Demask)
        self.last_original_text = ""

        # Ob reversible Maskierung aktiv ist
        self.reversible = True

        # Persistenter Dashboard-Zustand (Input/Output/Status)
        self.dash_input_text: str = ""
        self.dash_output_text: str = ""
        self.dash_status_text: str = ""

        # Feature-Flags für Auto-Verhalten
        self.auto_mask_enabled: bool = True
        self.auto_demask_enabled: bool = True

        # Zustand für Demask-View
        self.demask_input_text: str = ""
        self.demask_output_text: str = ""

        # Zentrales Session-Management (TTL-basiert)
        self.session_mgr = SessionManager(SESSION_TTL_SECONDS)

    def _load_theme_name(self) -> str:
        # Theme aus Config laden, Fallback auf "light"
        try:
            t = config.get("theme")
            if t in THEMES:
                return t
        except Exception:
            pass
        return "light"

    def _load_lang(self) -> str:
        # Sprache aus Config laden, nur "de" oder "en" erlaubt
        try:
            l = config.get("lang", "de")
            return l if l in ("de", "en") else "de"
        except Exception:
            return "de"

    def set_theme(self, name: str):
        # Theme wechseln und persistent speichern
        if name not in THEMES:
            return

        self.theme_name = name
        self.theme = THEMES[name]

        try:
            config.set("theme", name)
        except Exception:
            # Config-Fehler blockieren UI nicht
            pass

    def set_lang(self, lang: str):
        # Sprache wechseln und persistent speichern
        if lang not in ("de", "en"):
            return

        self.lang = lang

        try:
            config.set("lang", lang)
        except Exception:
            pass

    def set_mapping(self, mapping, hits, original, masked):
        """
        Setzt den aktuellen Maskierungszustand.

        mapping  -> token -> original value
        hits     -> Trefferliste aus Anonymizer
        original -> Quelltext
        masked   -> maskierter Text
        """
        self.last_mapping = mapping or {}
        self.last_hits = hits or []
        self.last_original_text = original or ""
        self.last_masked_text = masked or ""

    def set_reversible(self, value: bool):
        # Aktiviert/Deaktiviert reversible Maskierung
        self.reversible = bool(value)

    def set_dash(self, *, input_text=None, output_text=None, status_text=None) -> None:
        """
        Persistiert den Dashboard-Zustand selektiv.
        Nur übergebene Werte werden aktualisiert.
        """
        if input_text is not None:
            self.dash_input_text = input_text

        if output_text is not None:
            self.dash_output_text = output_text

        if status_text is not None:
            self.dash_status_text = status_text

    def clear_dash(self) -> None:
        """
        Hard-Reset des Dashboard-Zustands inklusive Mapping.
        """
        self.dash_input_text = ""
        self.dash_output_text = ""
        self.dash_status_text = ""

        # Auch Maskierungszustand zurücksetzen
        self.set_mapping({}, [], "", "")

    def add_session_mapping(self, mapping: dict):
        """
        Fügt Mapping der aktuellen Session hinzu.
        Wird nur verwendet, wenn reversible Maskierung aktiv ist.
        """
        if not mapping:
            return

        if self.session_mgr is None:
            # Fallback: SessionManager neu instanziieren
            self.session_mgr = SessionManager(SESSION_TTL_SECONDS)

        self.session_mgr.add_mapping(mapping)

    def close_active_session(self):
        """
        Schließt die aktuell aktive Session (setzt closed_at).
        """
        if self.session_mgr is None:
            return

        self.session_mgr.close_active_session()