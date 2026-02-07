from __future__ import annotations

import flet as ft
from state.store import AppStore
from ui.style.components import nav_item
from ui.views import dashboard as dashboard_view
from ui.views import settings as settings_view
from ui.views import demask as demask_view
from ui.views import dictionary as dictionary_view
from ui.style.translations import t

HELP_ICON_SIZE = 24
LOGO_SIZE = 45
LOGO_TEXT_SIZE = 18
LOGO_FILE_LIGHT = "logo.png"
LOGO_FILE_DARK = "logo_white.png"


def main(page: ft.Page):
    store = AppStore()
    assets_dir = "src/assets"

    page.assets_dir = assets_dir
    page.title = t(store.lang, "app.title")
    page.window_width = 1600
    page.window_height = 950
    page.window_min_width = 1200
    page.window_min_height = 800
    page.window_resizable = True
    page.padding = 0
    page.bgcolor = store.theme["page_bg"]
    page.theme_mode = ft.ThemeMode.DARK if store.theme_name == "dark" else ft.ThemeMode.LIGHT
    page.scroll = "none"

    def current_logo_file() -> str:
        return LOGO_FILE_DARK if store.theme_name == "dark" else LOGO_FILE_LIGHT

    page.window_icon = f"{assets_dir}/{current_logo_file()}"

    current = {"view": "dashboard"}
    center = ft.Container(expand=True)

    sidebar = ft.Container()
    right_area = ft.Container()
    sidebar_list = ft.Column(
        spacing=4,
        expand=True,
        alignment=ft.MainAxisAlignment.START,
        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
    )

    help_overlay = ft.Container(visible=False, expand=True)
    header_container = ft.Container()

    def rebuild_help_overlay():
        lang = store.lang

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

        def close_overlay(_):
            help_overlay.visible = False
            page.update()

        help_overlay.on_click = close_overlay

        card = ft.Container(
            width=720,
            padding=24,
            bgcolor=store.theme["surface"],
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
                                color=store.theme["text_primary"],
                            ),
                            ft.Container(expand=True),
                            ft.IconButton(
                                icon=ft.Icons.CLOSE,
                                tooltip=close_tt,
                                on_click=close_overlay,
                            ),
                        ],
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.Container(height=12),
                    ft.Text(intro, size=13, color=store.theme["text_secondary"]),
                    ft.Container(height=18),
                    ft.Text(
                        bullet_dash,
                        weight=ft.FontWeight.W_600,
                        size=13,
                        color=store.theme["text_primary"],
                    ),
                    ft.Text(dash, size=13, color=store.theme["text_secondary"]),
                    ft.Container(height=10),
                    ft.Text(
                        bullet_demask,
                        weight=ft.FontWeight.W_600,
                        size=13,
                        color=store.theme["text_primary"],
                    ),
                    ft.Text(demask_txt, size=13, color=store.theme["text_secondary"]),
                    ft.Container(height=10),
                    ft.Text(
                        bullet_dict,
                        weight=ft.FontWeight.W_600,
                        size=13,
                        color=store.theme["text_primary"],
                    ),
                    ft.Text(dictionary_txt, size=13, color=store.theme["text_secondary"]),
                    ft.Container(height=10),
                    ft.Text(
                        bullet_settings,
                        weight=ft.FontWeight.W_600,
                        size=13,
                        color=store.theme["text_primary"],
                    ),
                    ft.Text(settings_txt, size=13, color=store.theme["text_secondary"]),
                ],
                spacing=4,
                tight=True,
            ),
        )

        help_overlay.bgcolor = ft.Colors.with_opacity(0.55, ft.Colors.BLACK)
        help_overlay.content = ft.Container(
            expand=True,
            alignment=ft.alignment.center,
            content=card,
        )

    def show_help(_):
        help_overlay.visible = True
        page.update()

    def render_header():
        header_bg = store.theme.get("header", store.theme.get("surface", store.theme["page_bg"]))
        logo_file = current_logo_file()
        header_container.bgcolor = header_bg
        header_container.padding = ft.padding.symmetric(horizontal=24, vertical=12)
        header_container.content = ft.Row(
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
                            t(store.lang, "app.title"),
                            size=LOGO_TEXT_SIZE,
                            weight=ft.FontWeight.W_600,
                            color=store.theme["text_primary"],
                        ),
                    ],
                    spacing=10,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.Container(expand=True),
                ft.IconButton(
                    icon=ft.Icons.HELP_OUTLINE,
                    icon_size=HELP_ICON_SIZE,
                    icon_color=store.theme["icon_on_appbar"],
                    tooltip=t(store.lang, "help.icon.tooltip"),
                    on_click=show_help,
                ),
            ],
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

    def _maximize_on_connect(_):
        page.window_maximized = True
        page.update()

    page.on_connect = _maximize_on_connect

    def build_sidebar_controls() -> list[ft.Control]:
        return [
            nav_item(
                ft.Icons.DASHBOARD_OUTLINED,
                t(store.lang, "nav.dashboard"),
                selected=current["view"] == "dashboard",
                on_click=lambda _: set_view("dashboard"),
                theme=store.theme,
            ),
            nav_item(
                ft.Icons.VPN_KEY,
                t(store.lang, "nav.vault"),
                selected=current["view"] == "vault",
                on_click=lambda _: set_view("vault"),
                theme=store.theme,
            ),
            nav_item(
                ft.Icons.BOOK_OUTLINED,
                t(store.lang, "nav.dictionary"),
                selected=current["view"] == "dictionary",
                on_click=lambda _: set_view("dictionary"),
                theme=store.theme,
            ),
            nav_item(
                ft.Icons.SETTINGS_OUTLINED,
                t(store.lang, "nav.settings"),
                selected=current["view"] == "settings",
                on_click=lambda _: set_view("settings"),
                theme=store.theme,
            ),
        ]

    def render_sidebar():
        sidebar_list.controls = build_sidebar_controls()

    def render_center():
        if current["view"] == "dashboard":
            center.content = dashboard_view.view(page, store.theme, store)
        elif current["view"] == "vault":
            center.content = demask_view.view(page, store.theme, store)
        elif current["view"] == "dictionary":
            center.content = dictionary_view.view(page, store.theme, store)
        elif current["view"] == "settings":
            center.content = settings_view.view(
                page,
                store.theme_name,
                on_toggle_theme,
                store.theme,
                on_lang_changed=on_lang_changed,
            )

    def set_view(view: str):
        current["view"] = view
        render_sidebar()
        render_center()
        page.update()

    def on_toggle_theme(new_name: str):
        store.set_theme(new_name)
        page.bgcolor = store.theme["page_bg"]
        page.theme_mode = ft.ThemeMode.DARK if store.theme_name == "dark" else ft.ThemeMode.LIGHT
        page.window_icon = f"{assets_dir}/{current_logo_file()}"
        sidebar.bgcolor = store.theme["sidebar"]
        right_area.bgcolor = store.theme["background"]
        render_header()
        render_sidebar()
        render_center()
        rebuild_help_overlay()
        page.update()

    def on_lang_changed(new_lang: str):
        store.set_lang(new_lang)
        page.title = t(store.lang, "app.title")
        render_header()
        render_sidebar()
        render_center()
        rebuild_help_overlay()
        page.update()

    set_view("dashboard")

    sidebar.width = 220
    sidebar.bgcolor = store.theme["sidebar"]
    sidebar.padding = 12
    sidebar.content = sidebar_list

    right_area.expand = True
    right_area.bgcolor = store.theme["background"]
    right_area.content = center

    body = ft.Row(
        [sidebar, right_area],
        spacing=0,
        expand=True,
        vertical_alignment=ft.CrossAxisAlignment.STRETCH,
    )

    render_header()
    rebuild_help_overlay()

    root = ft.Container(
        expand=True,
        bgcolor=store.theme["page_bg"],
        content=ft.Column(
            [
                header_container,
                ft.Container(expand=True, content=body),
            ],
            spacing=0,
            expand=True,
        ),
    )

    page.add(root)
    page.overlay.append(help_overlay)
    page.update()


if __name__ == "__main__":
    ft.app(target=main, view=ft.AppView.FLET_APP)