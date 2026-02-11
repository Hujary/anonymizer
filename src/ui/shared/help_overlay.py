from __future__ import annotations

import flet as ft
from ui.style.translations import t


class HelpOverlay:
    def __init__(self, page: ft.Page, store):
        self.page = page
        self.store = store
        self.overlay = ft.Container(visible=False, expand=True)
        self.overlay.on_click = self._close
        self._rebuild()

    def _close(self, _: ft.ControlEvent) -> None:
        self.overlay.visible = False
        self.page.update()

    def open(self, _: ft.ControlEvent | None = None) -> None:
        self.overlay.visible = True
        self.page.update()

    def rebuild(self) -> None:
        self._rebuild()
        self.page.update()

    def _rebuild(self) -> None:
        lang = self.store.lang

        title = t(lang, "help.title")
        intro = t(lang, "help.intro")
        dash = t(lang, "help.dashboard.body")
        demask_txt = t(lang, "help.vault.body")
        dictionary_txt = t(lang, "help.dictionary.body")
        settings_txt = t(lang, "help.settings.body")

        bullet_dash = t(lang, "help.dashboard.bullet")
        bullet_demask = t(lang, "help.vault.bullet")
        bullet_dict = t(lang, "help.dictionary.bullet")
        bullet_settings = t(lang, "help.settings.bullet")
        close_tt = t(lang, "help.close")

        card = ft.Container(
            width=720,
            padding=24,
            bgcolor=self.store.theme["surface"],
            border_radius=16,
            on_click=lambda e: e.stop_propagation(),
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.Text(
                                title,
                                size=18,
                                weight=ft.FontWeight.W_600,
                                color=self.store.theme["text_primary"],
                            ),
                            ft.Container(expand=True),
                            ft.IconButton(
                                icon=ft.Icons.CLOSE,
                                tooltip=close_tt,
                                on_click=self._close,
                            ),
                        ],
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.Container(height=12),
                    ft.Text(intro, size=13, color=self.store.theme["text_secondary"]),
                    ft.Container(height=18),
                    ft.Text(
                        bullet_dash,
                        weight=ft.FontWeight.W_600,
                        size=13,
                        color=self.store.theme["text_primary"],
                    ),
                    ft.Text(dash, size=13, color=self.store.theme["text_secondary"]),
                    ft.Container(height=10),
                    ft.Text(
                        bullet_demask,
                        weight=ft.FontWeight.W_600,
                        size=13,
                        color=self.store.theme["text_primary"],
                    ),
                    ft.Text(demask_txt, size=13, color=self.store.theme["text_secondary"]),
                    ft.Container(height=10),
                    ft.Text(
                        bullet_dict,
                        weight=ft.FontWeight.W_600,
                        size=13,
                        color=self.store.theme["text_primary"],
                    ),
                    ft.Text(dictionary_txt, size=13, color=self.store.theme["text_secondary"]),
                    ft.Container(height=10),
                    ft.Text(
                        bullet_settings,
                        weight=ft.FontWeight.W_600,
                        size=13,
                        color=self.store.theme["text_primary"],
                    ),
                    ft.Text(settings_txt, size=13, color=self.store.theme["text_secondary"]),
                ],
                spacing=4,
                tight=True,
            ),
        )

        self.overlay.bgcolor = ft.Colors.with_opacity(0.55, ft.Colors.BLACK)
        self.overlay.content = ft.Container(
            expand=True,
            alignment=ft.alignment.center,
            content=card,
        )

    def build_help_button(self) -> ft.Control:
        return ft.IconButton(
            icon=ft.Icons.HELP_OUTLINE,
            icon_size=24,
            icon_color=self.store.theme["icon_on_appbar"],
            tooltip=t(self.store.lang, "help.icon.tooltip"),
            on_click=self.open,
        )