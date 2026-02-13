###     AppStore (Zentraler UI-State + Session-Mapping)
### __________________________________________________________________________
#
#  - Single Source of Truth für UI-relevanten In-Memory-State
#  - Hält Ergebnis des letzten Masking-Laufs (Original, Masked, Hits, Mapping)
#  - Persistiert View-States (Dashboard, Demask) über Navigation hinweg
#  - Verwaltet Theme/Sprache inkl. Schreiben in config.json
#  - Bindet SessionManager an für reversible Maskierung (persistente Sessions + TTL)
#
#  WICHTIG:
#    - Session-Mapping ist NICHT "Source of Truth" für Treffer-Erkennung.
#    - Session-Mapping dient zum:
#        (1) Demaskieren (Token -> Original)
#        (2) Token-Reuse: gleiches (Label, Original) soll möglichst denselben Token behalten
#


from __future__ import annotations

from core import config
from services.session_manager import SessionManager, SESSION_TTL_SECONDS
from ui.style.theme import THEMES


class AppStore:
    def __init__(self):
        self.theme_name = self._load_theme_name()
        self.theme = THEMES[self.theme_name]

        self.lang = self._load_lang()

        self.last_mapping = {}
        self.last_hits = []
        self.last_masked_text = ""
        self.last_original_text = ""

        self.reversible = True

        self.dash_input_text: str = ""
        self.dash_output_text: str = ""
        self.dash_status_text: str = ""

        self.auto_mask_enabled: bool = True
        self.auto_demask_enabled: bool = True

        self.demask_input_text: str = ""
        self.demask_output_text: str = ""

        self.session_mgr = SessionManager(SESSION_TTL_SECONDS)

    def _load_theme_name(self) -> str:
        try:
            t = config.get("theme")
            if t in THEMES:
                return t
        except Exception:
            pass
        return "light"

    def _load_lang(self) -> str:
        try:
            l = config.get("lang", "de")
            return l if l in ("de", "en") else "de"
        except Exception:
            return "de"

    def set_theme(self, name: str):
        if name not in THEMES:
            return

        self.theme_name = name
        self.theme = THEMES[name]

        try:
            config.set("theme", name)
        except Exception:
            pass

    def set_lang(self, lang: str):
        if lang not in ("de", "en"):
            return

        self.lang = lang

        try:
            config.set("lang", lang)
        except Exception:
            pass

    def set_mapping(self, mapping, hits, original, masked):
        self.last_mapping = mapping or {}
        self.last_hits = hits or []
        self.last_original_text = original or ""
        self.last_masked_text = masked or ""

    def set_reversible(self, value: bool):
        self.reversible = bool(value)

    def set_dash(self, *, input_text=None, output_text=None, status_text=None) -> None:
        if input_text is not None:
            self.dash_input_text = input_text

        if output_text is not None:
            self.dash_output_text = output_text

        if status_text is not None:
            self.dash_status_text = status_text

    def clear_dash(self) -> None:
        self.dash_input_text = ""
        self.dash_output_text = ""
        self.dash_status_text = ""
        self.set_mapping({}, [], "", "")

    def add_session_mapping(self, mapping: dict):
        if not mapping:
            return
        if self.session_mgr is None:
            self.session_mgr = SessionManager(SESSION_TTL_SECONDS)
        self.session_mgr.add_mapping(mapping)

    def close_active_session(self):
        if self.session_mgr is None:
            return
        self.session_mgr.close_active_session()