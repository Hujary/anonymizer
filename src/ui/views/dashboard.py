from __future__ import annotations

import re

import flet as ft
from core import config
from services.manual_categories import get_all_types as get_custom_types
from services.manual_tokens import add_manual_token as persist_manual_token
from ui.helpers.dashboard_helpers import (
    synced_textfield_height,
    type_label,
)
from ui.helpers.dashboard_context import DashboardContext
from ui.helpers.dashboard_actions import (
    add_manual_token as ui_add_manual_token,
    clear_both as ui_clear_both,
    handle_input_change,
    refresh_tokens_from_store,
    run_masking_internal,
    update_add_button_state,
)
from ui.style.components import outlined_pill, pill_button
from ui.style.translations import t

BASE_TYPES = [
    "E_MAIL",
    "TELEFON",
    "IBAN",
    "URL",
    "PLZ",
    "DATUM",
    "PER",
    "ORG",
    "LOC",
    "MISC",
]


def _all_types() -> list[str]:
    custom = get_custom_types()
    all_types = list(BASE_TYPES)
    for c in custom:
        if c not in all_types:
            all_types.append(c)
    return all_types


def view(page: ft.Page, theme: dict, store) -> ft.Control:
    lang = getattr(store, "lang", None) or config.get("lang", "de")
    if lang not in ("de", "en"):
        lang = "de"

    if lang == "de":
        input_title = "Text hier eingeben oder einfügen"
        input_sub = (
            "Füge vertrauliche Inhalte ein, die DSGVO-konform maskiert werden sollen. "
            "Links siehst du den Originaltext, rechts erscheint die maskierte Ausgabe."
        )
    else:
        input_title = "Type or paste text here"
        input_sub = (
            "Paste sensitive text you want to anonymize. "
            "The original text is shown on the left, the masked output on the right."
        )

    if not hasattr(store, "reversible"):
        setattr(store, "reversible", config.get("reversible_masking", True))

    if not hasattr(store, "auto_mask_enabled"):
        setattr(store, "auto_mask_enabled", config.get("auto_mask_enabled", True))

    accent = theme.get("accent", theme.get("text_primary"))

    input_ref: ft.Ref[ft.TextField] = ft.Ref[ft.TextField]()
    placeholder_ref: ft.Ref[ft.Column] = ft.Ref[ft.Column]()

    input_field = ft.TextField(
        ref=input_ref,
        hint_text="",
        multiline=True,
        min_lines=18,
        max_lines=None,
        border=ft.InputBorder.NONE,
        bgcolor=ft.Colors.TRANSPARENT,
        filled=False,
        text_vertical_align=ft.VerticalAlignment.START,
        content_padding=ft.padding.only(right=4),
        value=getattr(store, "dash_input_text", "") or "",
        text_style=ft.TextStyle(color=theme["text_primary"]),
        cursor_color=accent,
    )

    placeholder_title = ft.Text(
        input_title,
        size=18,
        weight=ft.FontWeight.W_600,
        color=theme.get("input_placeholder_title", theme["text_primary"]),
    )
    placeholder_sub = ft.Text(
        input_sub,
        size=13,
        color=theme.get("input_placeholder_sub", theme["text_secondary"]),
    )

    placeholder_column = ft.Column(
        ref=placeholder_ref,
        controls=[placeholder_title, placeholder_sub],
        spacing=4,
        alignment=ft.MainAxisAlignment.START,
        horizontal_alignment=ft.CrossAxisAlignment.START,
    )

    clear_button = ft.IconButton(
        icon=ft.Icons.CLOSE,
        icon_size=18,
        icon_color=theme["text_secondary"],
        tooltip=t(lang, "btn.clear"),
        visible=bool((getattr(store, "dash_input_text", "") or "").strip()),
    )

    def update_clear_icon() -> None:
        clear_button.visible = bool((input_field.value or "").strip())

    def update_placeholder() -> None:
        if placeholder_ref.current:
            is_empty = not (input_field.value or "").strip()
            placeholder_ref.current.visible = is_empty
        update_clear_icon()

    def focus_input(_: ft.ControlEvent) -> None:
        if input_ref.current:
            input_ref.current.focus()
        if placeholder_ref.current:
            placeholder_ref.current.visible = False
        page.update()

    shadow_color = theme["shadow_color"]
    card_shadow_color = ft.Colors.with_opacity(theme["shadow_opacity"], shadow_color)

    field_stack = ft.Stack(
        controls=[
            ft.Container(
                content=placeholder_column,
                alignment=ft.alignment.top_left,
                padding=ft.padding.only(top=-4),
                on_click=focus_input,
            ),
            input_field,
        ]
    )

    input_stack = ft.Row(
        controls=[
            ft.Container(
                content=field_stack,
                expand=True,
            ),
            ft.Container(
                content=clear_button,
                alignment=ft.alignment.top_right,
                padding=ft.padding.only(top=-10, right=-10),
            ),
        ],
        spacing=0,
        vertical_alignment=ft.CrossAxisAlignment.START,
    )

    input_box = ft.Container(
        content=input_stack,
        border_radius=8,
        bgcolor=theme["surface"],
        border=ft.border.all(1, theme["divider"]),
        padding=ft.padding.only(left=18, right=18, top=18, bottom=24),
        shadow=ft.BoxShadow(
            spread_radius=0,
            blur_radius=8,
            color=card_shadow_color,
            offset=ft.Offset(0, 8),
        ),
        on_click=focus_input,
    )

    output_field = ft.TextField(
        hint_text="",
        read_only=True,
        multiline=True,
        min_lines=18,
        max_lines=None,
        border=ft.InputBorder.NONE,
        bgcolor=ft.Colors.TRANSPARENT,
        filled=False,
        text_vertical_align=ft.VerticalAlignment.START,
        content_padding=0,
        value=getattr(store, "dash_output_text", "") or "",
        text_style=ft.TextStyle(color=theme["text_primary"]),
        cursor_color=accent,
    )

    output_box = ft.Container(
        content=output_field,
        border_radius=8,
        bgcolor=theme["surface"],
        border=ft.border.all(1, theme["divider"]),
        padding=ft.padding.only(left=18, right=18, top=18, bottom=24),
        shadow=ft.BoxShadow(
            spread_radius=0,
            blur_radius=8,
            color=card_shadow_color,
            offset=ft.Offset(0, 8),
        ),
    )

    def sync_equal_height() -> None:
        left_preview = (input_field.value or "").strip()
        if not left_preview:
            left_preview = f"{input_title}\n{input_sub}"
        right_preview = (output_field.value or "").strip()
        h = synced_textfield_height(
            left_preview,
            right_preview,
            page.window_width or 1200,
        )
        input_field.min_lines = h
        output_field.min_lines = h
        input_field.max_lines = None
        output_field.max_lines = None

    initial_status = getattr(store, "dash_status_text", "") or ""

    results_icon = ft.Icon(ft.Icons.SHIELD_OUTLINED, size=23, color=theme["text_secondary"])
    results_text = ft.Text(
        initial_status,
        size=15,
        weight=ft.FontWeight.W_500,
        color=theme["text_secondary"],
    )
    results_banner = ft.Container(
        visible=bool(initial_status),
        margin=ft.margin.only(top=12, bottom=4),
        padding=ft.padding.symmetric(20, 20),
        border_radius=10,
        bgcolor=theme["surface_muted"],
        content=ft.Row(
            [
                results_icon,
                results_text,
            ],
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
    )

    token_groups_col = ft.Column(spacing=10)
    tokens_host = ft.Container(
        padding=ft.padding.all(16),
        border_radius=12,
        bgcolor=theme["surface"],
        border=ft.border.all(1, theme["divider"]),
        content=token_groups_col,
        visible=False,
    )

    search_box = ft.TextField(
        hint_text=("Suchen…" if lang == "de" else "Search…"),
        prefix_icon=ft.Icons.SEARCH,
        bgcolor=theme["background"],
        border_radius=999,
        border=ft.InputBorder.OUTLINE,
        border_color=theme["divider"],
        focused_border_color=accent,
        filled=True,
        dense=True,
        width=420,
    )

    manual_token_text = ft.TextField(
        hint_text="Text für neuen Token…" if lang == "de" else "Text for new token…",
        bgcolor=theme["background"],
        border_radius=8,
        border=ft.InputBorder.OUTLINE,
        border_color=theme["divider"],
        focused_border_color=accent,
        filled=True,
        dense=False,
        height=48,
        expand=True,
        content_padding=ft.padding.symmetric(10, 16),
    )

    manual_token_type_values = _all_types()
    manual_token_type_value = ["MISC" if "MISC" in manual_token_type_values else manual_token_type_values[0]]

    manual_token_type = ft.Dropdown(
        options=[ft.dropdown.Option(v, text=type_label(lang, v)) for v in manual_token_type_values],
        value=manual_token_type_value[0],
        dense=False,
        text_size=12,
        width=180,
        menu_height=260,
        bgcolor=theme["background"],
        border_color=theme["divider"],
        border_radius=8,
    )

    manual_token_type_container = ft.Container(
        content=manual_token_type,
        height=48,
        alignment=ft.alignment.center,
    )

    add_button = ft.FilledButton(
        "Hinzufügen" if lang == "de" else "Add",
        icon=ft.Icons.ADD,
        disabled=True,
        height=40,
        bgcolor=None,
    )

    group_title = ft.Text(
        "Erkannte Tokens bearbeiten" if lang == "de" else "Review detected tokens",
        weight=ft.FontWeight.W_600,
        color=theme["text_primary"],
    )
    header_with_search = ft.Row(
        [
            group_title,
            ft.Container(expand=True),
            search_box,
        ],
        alignment=ft.MainAxisAlignment.START,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )

    manual_add_row = ft.Row(
        [
            manual_token_text,
            manual_token_type_container,
            add_button,
        ],
        spacing=8,
        alignment=ft.MainAxisAlignment.START,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )

    tokens_section = ft.Column(
        [
            ft.Container(height=24),
            header_with_search,
            ft.Container(height=12),
            manual_add_row,
            ft.Container(height=16),
            tokens_host,
        ],
        spacing=0,
        visible=False,
    )

    ctx = DashboardContext(
        page=page,
        theme=theme,
        store=store,
        lang=lang,
        accent=accent,
        input_title=input_title,
        input_sub=input_sub,
        input_field=input_field,
        output_field=output_field,
        results_text=results_text,
        results_banner=results_banner,
        token_groups_col=token_groups_col,
        tokens_host=tokens_host,
        tokens_section=tokens_section,
        search_box=search_box,
        manual_token_text=manual_token_text,
        manual_token_type=manual_token_type,
        manual_token_type_values=manual_token_type_values,
        manual_token_type_value=manual_token_type_value,
        add_button=add_button,
        sync_equal_height=sync_equal_height,
        update_placeholder=update_placeholder,
    )

    setattr(store, "dashboard_ctx", ctx)

    busy_count = [0]

    progress_ring = ft.ProgressRing(
        width=14,
        height=14,
        stroke_width=2.2,
        visible=False,
        color=accent,
    )

    progress_host = ft.Container(
        content=progress_ring,
        width=16,
        height=16,
        alignment=ft.alignment.center,
        margin=ft.margin.only(left=8),
        visible=False,
    )

    def _set_busy(is_busy: bool) -> None:
        if is_busy:
            busy_count[0] += 1
        else:
            busy_count[0] = max(0, busy_count[0] - 1)

        v = busy_count[0] > 0
        progress_ring.visible = v
        progress_host.visible = v
        page.update()

    ctx.on_masking_state = _set_busy

    def run_masking(_: ft.ControlEvent) -> None:
        run_masking_internal(ctx, auto=False)
        update_clear_icon()
        page.update()

    def clear_both(_: ft.ControlEvent) -> None:
        ui_clear_both(ctx)
        update_clear_icon()
        page.update()

    clear_button.on_click = clear_both

    def on_input_change(_: ft.ControlEvent) -> None:
        handle_input_change(ctx)
        update_clear_icon()

    def on_manual_text_change(_: ft.ControlEvent) -> None:
        update_add_button_state(ctx)

    def on_manual_type_change(e: ft.ControlEvent) -> None:
        manual_token_type_value[0] = e.control.value or manual_token_type_value[0]
        update_add_button_state(ctx)

    manual_token_text.on_change = on_manual_text_change
    manual_token_type.on_change = on_manual_type_change
    input_field.on_change = on_input_change

    def on_add_manual_token(_: ft.ControlEvent) -> None:
        text = (manual_token_text.value or "").strip()
        if not text:
            return

        token_type = manual_token_type.value or manual_token_type_value[0] or "MISC"

        try:
            persist_manual_token(token_type, text)
        except Exception as e:
            page.snack_bar = ft.SnackBar(
                content=ft.Text(str(e)),
                bgcolor=theme.get("danger", ft.Colors.RED),
            )
            page.snack_bar.open = True
            page.update()
            return

        ui_add_manual_token(ctx)
        manual_token_text.value = ""
        update_add_button_state(ctx)
        page.update()

    add_button.on_click = on_add_manual_token

    page.on_resize = lambda _: (sync_equal_height(), page.update())

    def on_search_change(_: ft.ControlEvent) -> None:
        refresh_tokens_from_store(ctx)

    search_box.on_change = on_search_change

    actions = ft.Row(
        [
            ft.Row(
                [
                    pill_button(
                        t(lang, "btn.mask"),
                        icon=ft.Icons.PLAY_ARROW,
                        on_click=run_masking,
                        theme=theme,
                        scale=1.05,
                    ),
                    outlined_pill(
                        t(lang, "btn.copy_out"),
                        icon=ft.Icons.CONTENT_COPY,
                        on_click=lambda _: page.set_clipboard(output_field.value or ""),
                        theme=theme,
                        scale=1.05,
                    ),
                    progress_host,
                ],
                spacing=12,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        ],
        spacing=0,
        alignment=ft.MainAxisAlignment.START,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )

    editors = ft.Row(
        [
            ft.Container(content=input_box, expand=True),
            ft.Container(content=output_box, expand=True),
        ],
        spacing=16,
        alignment=ft.MainAxisAlignment.START,
        vertical_alignment=ft.CrossAxisAlignment.START,
    )

    update_placeholder()
    sync_equal_height()
    refresh_tokens_from_store(ctx)
    update_clear_icon()
    update_add_button_state(ctx)

    base_margin = ft.margin.only(left=4, right=4)

    content_column = ft.Column(
        [
            ft.Container(content=actions, margin=base_margin),
            ft.Container(height=5),
            ft.Container(content=editors, margin=base_margin),
            ft.Container(content=results_banner, margin=base_margin),
            ft.Container(height=20),
            ft.Container(content=tokens_section, margin=base_margin),
            ft.Container(height=30),
        ],
        spacing=8,
        expand=True,
        scroll=ft.ScrollMode.AUTO,
        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
    )

    return ft.Container(
        padding=24,
        expand=True,
        bgcolor=theme["background"],
        alignment=ft.alignment.top_left,
        content=content_column,
    )