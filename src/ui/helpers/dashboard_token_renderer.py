from __future__ import annotations

from typing import Dict, List, Callable

import flet as ft

from ui.helpers.dashboard_context import OccurrenceRow
from ui.helpers.dashboard_helpers import type_label, group_sort_key


def build_token_rows(
    *,
    page: ft.Page,
    theme: Dict,
    lang: str,
    accent: str,
    token_groups_col: ft.Column,
    tokens_host: ft.Container,
    search_query: str,
    editing_row_ids: set[str],
    rows: List[OccurrenceRow],
    on_start_edit: Callable[[str], None],
    on_cancel_edit: Callable[[str], None],
    on_save_edit: Callable[[str, str], None],
    on_delete_row: Callable[[str], None],
) -> None:
    token_groups_col.controls.clear()

    q = (search_query or "").strip().lower()

    def match_filter(row: OccurrenceRow) -> bool:
        if not q:
            return True

        span_text = f"{row.start}-{row.ende}"
        hay = [
            row.token.lower(),
            (row.value or "").lower(),
            row.label.lower(),
            (row.source_label or "").lower(),
            span_text,
        ]

        if row.validation_status:
            hay.append(str(row.validation_status).lower())

        return any(q in part for part in hay)

    items_all = [row for row in rows if match_filter(row)]

    if not items_all:
        tokens_host.visible = False
        page.update()
        return

    groups: Dict[str, List[OccurrenceRow]] = {}
    for row in items_all:
        groups.setdefault(row.label, []).append(row)

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

    def make_validation_badge(row: OccurrenceRow) -> ft.Control | None:
        status = row.validation_status
        score = row.validation_score

        if status not in ("accepted", "declined"):
            return None

        score_text = "—" if score is None else f"{float(score):.2f}"
        label = f"ML {status} · {score_text}"

        if status == "accepted":
            badge_bg = ft.Colors.with_opacity(0.12, ft.Colors.GREEN)
            badge_fg = ft.Colors.GREEN_700
        else:
            badge_bg = ft.Colors.with_opacity(0.12, ft.Colors.RED)
            badge_fg = ft.Colors.RED_700

        return ft.Container(
            padding=ft.padding.symmetric(2, 8),
            bgcolor=badge_bg,
            border_radius=20,
            content=ft.Text(label, size=11, color=badge_fg),
        )

    def make_span_badge(row: OccurrenceRow) -> ft.Control:
        return ft.Container(
            padding=ft.padding.symmetric(2, 8),
            bgcolor=theme["surface_muted"],
            border_radius=20,
            content=ft.Text(
                f"{row.start}-{row.ende}",
                size=11,
                color=theme["text_secondary"],
            ),
        )

    def make_token_row(row: OccurrenceRow) -> ft.Control:
        type_badge = ft.Container(
            padding=ft.padding.symmetric(2, 8),
            bgcolor=theme["surface_muted"],
            border_radius=20,
            content=ft.Text(row.label, size=11, color=theme["text_secondary"]),
        )

        src_badge = ft.Container(
            padding=ft.padding.symmetric(2, 8),
            bgcolor=theme["surface_muted"],
            border_radius=20,
            content=ft.Text(row.source_label, size=11, color=theme["text_secondary"]),
        )

        span_badge = make_span_badge(row)
        validation_badge = make_validation_badge(row)

        head_controls: List[ft.Control] = [
            ft.Text(row.token, size=12, color=theme["text_secondary"]),
            type_badge,
            src_badge,
            span_badge,
        ]

        if validation_badge is not None:
            head_controls.append(validation_badge)

        head_controls.append(ft.Container(expand=True))

        head = ft.Row(
            head_controls,
            spacing=8,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        bg = theme["surface_muted"] if row.enabled else theme["background"]
        border_color = theme["divider"]

        if row.row_id in editing_row_ids:
            tf_ref = ft.Ref[ft.TextField]()
            tf = ft.TextField(
                ref=tf_ref,
                value=row.value,
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
                on_cancel_edit(row.row_id)

            def _save(_: ft.ControlEvent):
                on_save_edit(row.row_id, tf_ref.current.value or "")

            def _delete(_: ft.ControlEvent):
                on_delete_row(row.row_id)

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
                on_start_edit(row.row_id)

            def _delete(_: ft.ControlEvent):
                on_delete_row(row.row_id)

            value_text = row.value or "—"
            value_color = theme["text_primary"] if row.enabled else theme["text_secondary"]

            body = ft.Container(
                bgcolor=bg,
                border_radius=8,
                border=ft.border.all(1, border_color),
                padding=ft.padding.symmetric(10, 12),
                content=ft.Row(
                    [
                        ft.Text(
                            value_text,
                            selectable=False,
                            color=value_color,
                            expand=True,
                        ),
                        ft.IconButton(
                            icon=ft.Icons.EDIT,
                            icon_color=theme["text_secondary"],
                            tooltip="Bearbeiten" if lang == "de" else "Edit",
                            on_click=_start,
                        ),
                        ft.IconButton(
                            icon=ft.Icons.DELETE_OUTLINE,
                            icon_color=theme["danger"],
                            tooltip="Löschen" if lang == "de" else "Delete",
                            on_click=_delete,
                        ),
                    ],
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                on_click=_start,
            )

        return ft.Column([head, body], spacing=6)

    for i, typ in enumerate(ordered_types):
        items = sorted(groups[typ], key=lambda row: (row.start, row.ende, row.row_id))
        cards = [make_token_row(row) for row in items]

        grid_rows: List[ft.Control] = []
        for j in range(0, len(cards), 2):
            pair = cards[j:j + 2]
            row_controls: List[ft.Control] = [
                ft.Container(content=pair[0], expand=True)
            ]

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