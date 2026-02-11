from __future__ import annotations

import flet as ft

from ui.style.components import nav_item
from ui.style.translations import t
from ui.shared.help_overlay import HelpOverlay

from ui.views import dashboard as dashboard_view
from ui.views import settings as settings_view
from ui.views import demask as demask_view
from ui.views import dictionary as dictionary_view

LOGO_SIZE = 45
LOGO_TEXT_SIZE = 18
LOGO_FILE_LIGHT = "logo.png"
LOGO_FILE_DARK = "logo_white.png"


class Router:
    def __init__(self, page: ft.Page, store, assets_dir: str):
        self.page = page
        self.store = store
        self.assets_dir = assets_dir

        self.current_view = "dashboard"

        self.center = ft.Container(expand=True)

        self.sidebar_list = ft.Column(
            spacing=4,
            expand=True,
            alignment=ft.MainAxisAlignment.START,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        )

        self.sidebar = ft.Container(width=220, padding=12)
        self.right_area = ft.Container(expand=True)

        self.header_container = ft.Container()
        self.help = HelpOverlay(page, store)

        self.sidebar.bgcolor = self.store.theme["sidebar"]
        self.sidebar.content = self.sidebar_list

        self.right_area.bgcolor = self.store.theme["background"]
        self.right_area.content = self.center

        body = ft.Row(
            [self.sidebar, self.right_area],
            spacing=0,
            expand=True,
            vertical_alignment=ft.CrossAxisAlignment.STRETCH,
        )

        self.root = ft.Container(
            expand=True,
            bgcolor=self.store.theme["page_bg"],
            content=ft.Column(
                [
                    self.header_container,
                    ft.Container(expand=True, content=body),
                ],
                spacing=0,
                expand=True,
            ),
        )

        self.page.overlay.append(self.help.overlay)

        self._render_header()
        self._render_sidebar()
        self._render_center()

        def _maximize_on_connect(_: ft.ControlEvent) -> None:
            self.page.window_maximized = True
            self.page.update()

        self.page.on_connect = _maximize_on_connect

    def current_logo_file(self) -> str:
        return LOGO_FILE_DARK if self.store.theme_name == "dark" else LOGO_FILE_LIGHT

    def mount(self) -> ft.Control:
        return self.root

    def set_view(self, view: str) -> None:
        self.current_view = view
        self._render_sidebar()
        self._render_center()
        self.page.update()

    def on_toggle_theme(self, new_name: str) -> None:
        self.store.set_theme(new_name)

        self.page.bgcolor = self.store.theme["page_bg"]
        self.page.theme_mode = ft.ThemeMode.DARK if self.store.theme_name == "dark" else ft.ThemeMode.LIGHT
        self.page.window_icon = f"{self.assets_dir}/{self.current_logo_file()}"

        self.sidebar.bgcolor = self.store.theme["sidebar"]
        self.right_area.bgcolor = self.store.theme["background"]
        self.root.bgcolor = self.store.theme["page_bg"]

        self._render_header()
        self._render_sidebar()
        self._render_center()
        self.help.rebuild()
        self.page.update()

    def on_lang_changed(self, new_lang: str) -> None:
        self.store.set_lang(new_lang)
        self.page.title = t(self.store.lang, "app.title")
        self._render_header()
        self._render_sidebar()
        self._render_center()
        self.help.rebuild()
        self.page.update()

    def _render_header(self) -> None:
        header_bg = self.store.theme.get("header", self.store.theme.get("surface", self.store.theme["page_bg"]))
        logo_file = self.current_logo_file()

        self.header_container.bgcolor = header_bg
        self.header_container.padding = ft.padding.symmetric(horizontal=24, vertical=12)
        self.header_container.content = ft.Row(
            [
                ft.Row(
                    [
                        ft.Image(
                            src=f"/{logo_file}",
                            width=LOGO_SIZE,
                            height=LOGO_SIZE,
                            fit=ft.ImageFit.CONTAIN,
                        ),
                        ft.Text(
                            t(self.store.lang, "app.title"),
                            size=LOGO_TEXT_SIZE,
                            weight=ft.FontWeight.W_600,
                            color=self.store.theme["text_primary"],
                        ),
                    ],
                    spacing=10,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.Container(expand=True),
                self.help.build_help_button(),
            ],
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

    def _build_sidebar_controls(self) -> list[ft.Control]:
        return [
            nav_item(
                ft.Icons.DASHBOARD_OUTLINED,
                t(self.store.lang, "nav.dashboard"),
                selected=self.current_view == "dashboard",
                on_click=lambda _: self.set_view("dashboard"),
                theme=self.store.theme,
            ),
            nav_item(
                ft.Icons.VPN_KEY,
                t(self.store.lang, "nav.vault"),
                selected=self.current_view == "vault",
                on_click=lambda _: self.set_view("vault"),
                theme=self.store.theme,
            ),
            nav_item(
                ft.Icons.BOOK_OUTLINED,
                t(self.store.lang, "nav.dictionary"),
                selected=self.current_view == "dictionary",
                on_click=lambda _: self.set_view("dictionary"),
                theme=self.store.theme,
            ),
            nav_item(
                ft.Icons.SETTINGS_OUTLINED,
                t(self.store.lang, "nav.settings"),
                selected=self.current_view == "settings",
                on_click=lambda _: self.set_view("settings"),
                theme=self.store.theme,
            ),
        ]

    def _render_sidebar(self) -> None:
        self.sidebar_list.controls = self._build_sidebar_controls()

    def _render_center(self) -> None:
        if self.current_view == "dashboard":
            self.center.content = dashboard_view.view(self.page, self.store.theme, self.store)
            return

        if self.current_view == "vault":
            self.center.content = demask_view.view(self.page, self.store.theme, self.store)
            return

        if self.current_view == "dictionary":
            self.center.content = dictionary_view.view(self.page, self.store.theme, self.store)
            return

        if self.current_view == "settings":
            self.center.content = settings_view.view(
                self.page,
                self.store.theme_name,
                self.on_toggle_theme,
                self.store.theme,
                on_lang_changed=self.on_lang_changed,
            )
            return

        self.center.content = ft.Container()