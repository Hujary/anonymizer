from __future__ import annotations

from collections.abc import Callable

import flet as ft


def nav_item(icon, label: str, selected: bool, on_click, theme: dict) -> ft.Container:
    return ft.Container(
        content=ft.Row(
            [
                ft.Icon(icon, size=18, color=theme["text_secondary"]),
                ft.Text(label, size=13, weight=ft.FontWeight.W_500, color=theme["sidebar_text"]),
            ],
            spacing=12,
            alignment=ft.MainAxisAlignment.START,
        ),
        padding=ft.padding.symmetric(10, 12),
        bgcolor=theme["sidebar_active"] if selected else None,
        border_radius=10,
        ink=True,
        on_click=on_click,
    )


def pill_button(
    text: str,
    icon=None,
    on_click=None,
    theme: dict | None = None,
    scale: float = 1.0,
) -> ft.Container:
    if theme is None:
        raise ValueError("pill_button requires a theme")

    bg_default = theme["button_bg"]
    outline_color = theme["button_outline"]
    text_color = theme.get("button_text", theme["text_primary"])
    hover_bg = theme["button_hover"]

    base_pad_v = 10
    base_pad_h = 18
    base_radius = 10
    base_icon_size = 16
    base_font_size = 13
    base_blur = 6
    base_offset_y = 4

    pad_v = base_pad_v * scale
    pad_h = base_pad_h * scale
    radius = base_radius * scale
    icon_size = base_icon_size * scale
    font_size = base_font_size * scale
    blur = base_blur * scale
    offset_y = base_offset_y * scale

    row_items: list[ft.Control] = []
    if icon is not None:
        row_items.append(ft.Icon(icon, size=icon_size, color=text_color))
    row_items.append(
        ft.Text(text, size=font_size, weight=ft.FontWeight.W_500, color=text_color)
    )

    content = ft.Row(
        row_items,
        spacing=8 * scale,
        alignment=ft.MainAxisAlignment.CENTER,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )

    def on_hover(e: ft.HoverEvent):
        e.control.bgcolor = hover_bg if e.data == "true" else bg_default
        e.control.update()

    shadow_color = theme["shadow_color"]
    shadow_opacity = theme["shadow_opacity"]

    return ft.Container(
        content=content,
        padding=ft.padding.symmetric(vertical=pad_v, horizontal=pad_h),
        border_radius=radius,
        bgcolor=bg_default,
        border=ft.border.all(0.8, outline_color),
        shadow=ft.BoxShadow(
            spread_radius=0,
            blur_radius=blur,
            color=ft.Colors.with_opacity(shadow_opacity, shadow_color),
            offset=ft.Offset(0, offset_y),
        ),
        ink=True,
        on_click=on_click,
        on_hover=on_hover,
    )


def outlined_pill(
    text: str,
    icon=None,
    on_click=None,
    theme: dict | None = None,
    scale: float = 0.7,
) -> ft.Container:
    if theme is None:
        raise ValueError("outlined_pill requires a theme")

    bg_default = theme["button_bg"]
    outline_color = theme["button_outline"]
    text_color = theme.get("button_text", theme["text_primary"])
    hover_bg = theme["button_hover"]

    base_pad_v = 10
    base_pad_h = 14
    base_radius = 10
    base_icon_size = 13
    base_font_size = 13
    base_blur = 6
    base_offset_y = 4

    pad_v = base_pad_v * scale
    pad_h = base_pad_h * scale
    radius = base_radius * scale
    icon_size = base_icon_size * scale
    font_size = base_font_size * scale
    blur = base_blur * scale
    offset_y = base_offset_y * scale

    row_items: list[ft.Control] = []
    if icon is not None:
        row_items.append(ft.Icon(icon, size=icon_size, color=text_color))
    row_items.append(
        ft.Text(text, size=font_size, weight=ft.FontWeight.W_500, color=text_color)
    )

    content = ft.Row(
        row_items,
        spacing=8 * scale,
        alignment=ft.MainAxisAlignment.CENTER,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )

    def on_hover(e: ft.HoverEvent):
        e.control.bgcolor = hover_bg if e.data == "true" else bg_default
        e.control.update()

    shadow_color = theme["shadow_color"]
    shadow_opacity = theme["shadow_opacity"]

    return ft.Container(
        content=content,
        padding=ft.padding.symmetric(vertical=pad_v, horizontal=pad_h),
        border_radius=radius,
        bgcolor=bg_default,
        border=ft.border.all(0.8, outline_color),
        shadow=ft.BoxShadow(
            spread_radius=0,
            blur_radius=blur,
            color=ft.Colors.with_opacity(shadow_opacity, shadow_color),
            offset=ft.Offset(0, offset_y),
        ),
        ink=True,
        on_click=on_click,
        on_hover=on_hover,
    )


def appbar(theme: dict, on_help=None) -> ft.AppBar:
    def handle_help(e):
        if on_help:
            on_help(e)

    return ft.AppBar(
        bgcolor=theme.get("appbar", theme.get("header", theme["background"])),
        elevation=0,
        center_title=False,
        leading=None,
        title=ft.Text(
            "anonymizer • Desktop",
            size=16,
            weight=ft.FontWeight.W_600,
            color=theme["text_on_appbar"],
        ),
        actions=[
            ft.IconButton(
                icon=ft.Icons.HELP_OUTLINE,
                tooltip="Hilfe / Help",
                icon_color=theme["icon_on_appbar"],
                on_click=handle_help,
            ),
            ft.CircleAvatar(
                content=ft.Text("P", size=14, color=theme["icon_on_appbar"]),
                radius=16,
                bgcolor=theme["accent"],
            ),
            ft.Container(width=14),
        ],
    )


def pill_switch(
    label: str,
    value: bool,
    on_change: Callable | None,
    theme: dict,
    scale: float = 1.0,
) -> ft.Container:
    switch_ref: ft.Ref[ft.Switch] = ft.Ref[ft.Switch]()
    container_ref: ft.Ref[ft.Container] = ft.Ref[ft.Container]()

    bg_default = theme["button_bg"]
    outline_color = theme["button_outline"]
    hover_bg = theme["button_hover"]

    active_track = theme["switch_track_active"]
    inactive_track = theme["switch_track_inactive"]
    inactive_thumb = theme["switch_thumb"]

    base_pad_v = 8
    base_pad_h = 18
    base_radius = 10
    base_font_size = 13
    base_spacing = 10
    base_blur = 6
    base_offset_y = 4
    base_switch_scale = 0.68
    base_box_height = 36

    pad_v = base_pad_v * scale
    pad_h = base_pad_h * scale
    radius = base_radius * scale
    font_size = base_font_size * scale
    spacing = base_spacing * scale
    blur = base_blur * scale
    offset_y = base_offset_y * scale
    box_height = base_box_height * scale
    switch_scale = base_switch_scale * scale

    def handle_switch_change(e: ft.ControlEvent):
        if on_change and switch_ref.current is not None:
            on_change(switch_ref.current.value)

    sw = ft.Switch(
        ref=switch_ref,
        value=value,
        on_change=handle_switch_change,
        active_color=theme["switch_thumb"],
        active_track_color=active_track,
        inactive_track_color=inactive_track,
        inactive_thumb_color=inactive_thumb,
        thumb_color=theme["switch_thumb"],
        scale=switch_scale,
    )

    row = ft.Row(
        [
            ft.Text(
                label,
                size=font_size,
                weight=ft.FontWeight.W_500,
                color=theme["text_primary"],
            ),
            sw,
        ],
        spacing=spacing,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )

    def on_hover(e: ft.HoverEvent):
        if container_ref.current:
            container_ref.current.bgcolor = hover_bg if e.data == "true" else bg_default
            container_ref.current.update()

    def toggle(e: ft.ControlEvent):
        if switch_ref.current is None:
            return
        switch_ref.current.value = not switch_ref.current.value
        if on_change:
            on_change(switch_ref.current.value)
        e.page.update()

    shadow_color = theme["shadow_color"]
    shadow_opacity = theme["shadow_opacity"]

    return ft.Container(
        ref=container_ref,
        height=box_height,
        padding=ft.padding.symmetric(vertical=pad_v, horizontal=pad_h),
        border_radius=radius,
        bgcolor=bg_default,
        border=ft.border.all(0.8, outline_color),
        shadow=ft.BoxShadow(
            spread_radius=0,
            blur_radius=blur,
            color=ft.Colors.with_opacity(shadow_opacity, shadow_color),
            offset=ft.Offset(0, offset_y),
        ),
        ink=True,
        on_click=toggle,
        on_hover=on_hover,
        content=row,
    )