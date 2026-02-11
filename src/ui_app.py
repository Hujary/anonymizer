###     Entry-Point für Flet UI (Router + globaler AppState)
### __________________________________________________________________________

from __future__ import annotations

import flet as ft

# interne Module
from state.store import AppStore
from ui.routing.router import Router
from ui.style.translations import t


# ==========================================================
#  Statische Konfiguration
# ==========================================================

# Verzeichnis für Icons, Logos etc.
ASSETS_DIR = "src/assets"


# ==========================================================
#  Page-Grundkonfiguration
# ==========================================================
def _configure_page(page: ft.Page, store: AppStore) -> None:
    """
    Setzt alle globalen Fenster- und Theme-Einstellungen.
    Keine UI-Logik – nur Rahmenbedingungen.
    """

    # Asset-Verzeichnis für Bilder/Icons
    page.assets_dir = ASSETS_DIR

    # Fenstertitel (abhängig von Sprache)
    page.title = t(store.lang, "app.title")

    # Standard-Startgröße
    page.window_width = 1600
    page.window_height = 950

    # Minimale Fenstergröße
    page.window_min_width = 1200
    page.window_min_height = 800

    # Fenster darf skaliert werden
    page.window_resizable = True

    # Kein globales Padding – Layout regelt das selbst
    page.padding = 0

    # Hintergrundfarbe aus aktivem Theme
    page.bgcolor = store.theme["page_bg"]

    # Dark/Light Mode für Flet setzen
    page.theme_mode = (
        ft.ThemeMode.DARK
        if store.theme_name == "dark"
        else ft.ThemeMode.LIGHT
    )

    # Scroll wird von einzelnen Views geregelt
    page.scroll = "none"

    # Fenster-Icon abhängig vom Theme
    page.window_icon = (
        f"{ASSETS_DIR}/"
        f"{'logo_white.png' if store.theme_name == 'dark' else 'logo.png'}"
    )


# ==========================================================
#  Hauptfunktion (UI-Start)
# ==========================================================
def main(page: ft.Page) -> None:
    """
    Initialisiert:
    - globalen AppStore
    - Seitenkonfiguration
    - Router
    - Start-View
    """

    # Zentralen Zustand erzeugen
    store = AppStore()

    # Fenster konfigurieren
    _configure_page(page, store)

    # Router erzeugen (verwaltet Navigation + Views)
    router = Router(page=page, store=store, assets_dir=ASSETS_DIR,)

    # Router-Root-Control ins Page-Tree einhängen
    page.add(router.mount())

    # Start-View setzen
    router.set_view("dashboard")

    # Initiales Rendering
    page.update()


# ==========================================================
#  Standalone-Start
# ==========================================================
if __name__ == "__main__":
    ft.app(
        target=main,
        view=ft.AppView.FLET_APP,
    )