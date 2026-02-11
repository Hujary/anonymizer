from __future__ import annotations

from typing import Dict, List, Callable

import flet as ft

from ui.helpers.dashboard_helpers import typ_of, type_label, group_sort_key


def build_token_rows(
    *,
    page: ft.Page,
    theme: Dict,
    lang: str,
    accent: str,
    token_groups_col: ft.Column,
    tokens_host: ft.Container,
    search_query: str,
    editing_keys: set[str],
    mapping: Dict[str, str],
    token_source_label: Callable[[str, str], str],
    on_start_edit: Callable[[str], None],
    on_cancel_edit: Callable[[str], None],
    on_save_edit: Callable[[str, str], None],
    on_delete_token: Callable[[str], None],
) -> None:
    token_groups_col.controls.clear()

    q = (search_query or "").strip().lower()

    def match_filter(k: str, v: str) -> bool:
        if not q:
            return True
        return (q in k.lower()) or (q in (v or "").lower()) or (q in typ_of(k).lower())

    items_all = [(k, v) for k, v in (mapping or {}).items() if match_filter(k, v)]

    if not items_all:
        tokens_host.visible = False
        page.update()
        return

    groups: Dict[str, List[tuple[str, str]]] = {}
    for key, value in items_all:
        typ = typ_of(key)
        groups.setdefault(typ, []).append((key, value))

    ordered_types = sorted(groups.keys(), key=group_sort_key)

    def group_header(typ: str, count: int) -> ft.Control:
        badge = ft.Container(
            padding=ft.padding.symmetric(2, 8),
            bgcolor=theme["surface_muted"],
            border_radius=20,
            content=ft.Text(str(count), size=12, color=theme["text_secondary"]),
        )
        title = ft.Text(
            type_label(lang, typ),
            weight=ft.FontWeight.W_600,
            color=theme["text_primary"],
        )
        return ft.Row(
            [title, badge],
            spacing=8,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

    def make_token_row(key: str, value: str) -> ft.Control:
        type_badge = ft.Container(
            padding=ft.padding.symmetric(2, 8),
            bgcolor=theme["surface_muted"],
            border_radius=20,
            content=ft.Text(typ_of(key), size=11, color=theme["text_secondary"]),
        )

        src_label = token_source_label(key, value)
        src_badge = ft.Container(
            padding=ft.padding.symmetric(2, 8),
            bgcolor=theme["surface_muted"],
            border_radius=20,
            content=ft.Text(src_label, size=11, color=theme["text_secondary"]),
        )

        head = ft.Row(
            [
                ft.Text(key, size=12, color=theme["text_secondary"]),
                type_badge,
                src_badge,
                ft.Container(expand=True),
            ],
            spacing=8,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        if key in editing_keys:
            tf_ref = ft.Ref[ft.TextField]()
            tf = ft.TextField(
                ref=tf_ref,
                value=value,
                autofocus=True,
                dense=False,
                multiline=False,
                bgcolor=theme["background"],
                filled=True,
                border_radius=8,
                border=ft.InputBorder.OUTLINE,
                border_color=accent,
                focused_border_color=accent,
                content_padding=ft.padding.symmetric(10, 12),
            )

            def _cancel(_: ft.ControlEvent):
                on_cancel_edit(key)

            def _save(_: ft.ControlEvent):
                on_save_edit(key, tf_ref.current.value or "")

            def _delete(_: ft.ControlEvent):
                on_delete_token(key)

            actions = ft.Row(
                [
                    ft.Container(expand=True),
                    ft.TextButton(
                        "Löschen" if lang == "de" else "Delete",
                        style=ft.ButtonStyle(color=theme["danger"]),
                        on_click=_delete,
                    ),
                    ft.TextButton(
                        "Abbrechen" if lang == "de" else "Cancel",
                        style=ft.ButtonStyle(color=theme["text_secondary"]),
                        on_click=_cancel,
                    ),
                    ft.FilledButton(
                        "Übernehmen" if lang == "de" else "Apply",
                        on_click=_save,
                        bgcolor=accent,
                        color=ft.Colors.WHITE,
                    ),
                ],
                spacing=8,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            )

            body = ft.Column([tf, actions], spacing=8)
        else:

            def _start(_: ft.ControlEvent):
                on_start_edit(key)

            body = ft.Container(
                bgcolor=theme["surface_muted"],
                border_radius=8,
                border=ft.border.all(1, theme["divider"]),
                padding=ft.padding.symmetric(10, 12),
                content=ft.Row(
                    [
                        ft.Text(
                            value or "—",
                            selectable=False,
                            color=theme["text_primary"],
                            expand=True,
                        ),
                        ft.IconButton(
                            icon=ft.Icons.EDIT,
                            icon_color=theme["text_secondary"],
                            tooltip="Bearbeiten" if lang == "de" else "Edit",
                            on_click=_start,
                        ),
                    ],
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                on_click=_start,
            )

        return ft.Column([head, body], spacing=6)

    for i, typ in enumerate(ordered_types):
        items = sorted(groups[typ], key=lambda kv: kv[0].lower())
        cards = [make_token_row(key, value) for key, value in items]

        grid_rows: List[ft.Control] = []
        for j in range(0, len(cards), 2):
            pair = cards[j: j + 2]
            row_controls: List[ft.Control] = []
            row_controls.append(ft.Container(content=pair[0], expand=True))
            if len(pair) == 2:
                row_controls.append(ft.Container(content=pair[1], expand=True))
            else:
                row_controls.append(ft.Container(expand=True))
            grid_rows.append(
                ft.Row(
                    row_controls,
                    spacing=12,
                    vertical_alignment=ft.CrossAxisAlignment.START,
                )
            )

        grp = ft.Column(
            [
                group_header(typ, len(items)),
                ft.Container(height=6),
                ft.Column(grid_rows, spacing=8),
            ],
            spacing=4,
        )
        token_groups_col.controls.append(grp)
        if i < len(ordered_types) - 1:
            token_groups_col.controls.append(ft.Container(height=16))

    tokens_host.visible = True
    page.update()