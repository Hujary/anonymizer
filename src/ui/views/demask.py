from __future__ import annotations

import json
import re
import flet as ft
from ui.style.components import pill_button, outlined_pill
from services.anonymizer import de_anonymize
from ui.style.translations import t
from core import config
from ui.helpers.dashboard_helpers import synced_textfield_height


def view(page: ft.Page, theme: dict, store) -> ft.Control:
    lang = getattr(store, "lang", None) or config.get("lang", "de")
    if lang not in ("de", "en"):
        lang = "de"

    masked_title = t(lang, "vault.input.title")
    masked_sub = t(lang, "vault.input.sub")

    if not hasattr(store, "auto_demask_enabled"):
        setattr(store, "auto_demask_enabled", config.get("auto_demask_enabled", True))

    _type_re = re.compile(r"^\[([A-ZÄÖÜa-zäöü_]+)(?:_[^\]]+)?\]$")

    def extract_type(key: str) -> str:
        m = _type_re.match(key.strip())
        if not m:
            return "MISC"
        return m.group(1).upper()

    TYPE_LABELS_DE = {
        "E_MAIL": "E-Mail",
        "TELEFON": "Telefon",
        "IBAN": "IBAN",
        "BIC": "BIC",
        "URL": "URL",
        "USTID": "USt-IdNr.",
        "RECHNUNGS_NUMMER": "Rechnungsnummer",
        "PLZ": "PLZ",
        "DATUM": "Datum",
        "PER": "Person",
        "ORG": "Organisation",
        "LOC": "Ort",
        "MISC": "Sonstiges",
    }
    TYPE_LABELS_EN = {
        "E_MAIL": "E-mail",
        "TELEFON": "Phone",
        "IBAN": "IBAN",
        "BIC": "BIC",
        "URL": "URL",
        "USTID": "VAT ID",
        "RECHNUNGS_NUMMER": "Invoice No.",
        "PLZ": "ZIP",
        "DATUM": "Date",
        "PER": "Person",
        "ORG": "Organization",
        "LOC": "Location",
        "MISC": "Other",
    }

    def type_label(typ: str) -> str:
        return (TYPE_LABELS_DE if lang == "de" else TYPE_LABELS_EN).get(typ, typ.title())

    GROUP_ORDER = [
        "E_MAIL",
        "TELEFON",
        "IBAN",
        "BIC",
        "URL",
        "USTID",
        "RECHNUNGS_NUMMER",
        "PLZ",
        "DATUM",
        "PER",
        "ORG",
        "LOC",
        "MISC",
    ]

    def group_sort_key(typ: str) -> tuple[int, str]:
        try:
            return (GROUP_ORDER.index(typ), typ)
        except ValueError:
            return (len(GROUP_ORDER), typ)

    input_ref: ft.Ref[ft.TextField] = ft.Ref[ft.TextField]()
    placeholder_ref: ft.Ref[ft.Column] = ft.Ref[ft.Column]()

    masked_input_field = ft.TextField(
        ref=input_ref,
        hint_text="",
        multiline=True,
        min_lines=18,
        max_lines=18,
        border=ft.InputBorder.NONE,
        bgcolor=ft.Colors.TRANSPARENT,
        filled=False,
        text_vertical_align=ft.VerticalAlignment.START,
        content_padding=ft.padding.only(right=4),
        text_style=ft.TextStyle(color=theme["text_primary"]),
        cursor_color=theme["accent"],
        value=getattr(store, "demask_input_text", "") or "",
    )

    unmasked_output_field = ft.TextField(
        hint_text="",
        multiline=True,
        min_lines=18,
        max_lines=18,
        read_only=True,
        border=ft.InputBorder.NONE,
        bgcolor=ft.Colors.TRANSPARENT,
        filled=False,
        text_vertical_align=ft.VerticalAlignment.START,
        content_padding=0,
        text_style=ft.TextStyle(color=theme["text_primary"]),
        cursor_color=theme["accent"],
        value=getattr(store, "demask_output_text", "") or "",
    )

    placeholder_title = ft.Text(
        masked_title,
        size=18,
        weight=ft.FontWeight.W_600,
        color=theme["input_placeholder_title"],
    )
    placeholder_sub = ft.Text(
        masked_sub,
        size=13,
        color=theme["input_placeholder_sub"],
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
        visible=bool((getattr(store, "demask_input_text", "") or "").strip()),
    )

    def update_clear_icon():
        clear_button.visible = bool((masked_input_field.value or "").strip())

    def update_placeholder():
        if placeholder_ref.current:
            is_empty = not (masked_input_field.value or "").strip()
            placeholder_ref.current.visible = is_empty
        update_clear_icon()

    def focus_input(_):
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
            masked_input_field,
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

    masked_input_box = ft.Container(
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

    unmasked_output_box = ft.Container(
        content=unmasked_output_field,
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

    def sync_equal_height():
        left_preview = (masked_input_field.value or "").strip()
        if not left_preview:
            left_preview = f"{masked_title}\n{masked_sub}"
        right_preview = (unmasked_output_field.value or "").strip()
        h = synced_textfield_height(
            left_preview,
            right_preview,
            page.window_width or 1200,
        )
        masked_input_field.min_lines = masked_input_field.max_lines = h
        unmasked_output_field.min_lines = unmasked_output_field.max_lines = h

    # HIER die einzige fachliche Änderung:
    def full_mapping() -> dict[str, str]:
        mapping: dict[str, str] = {}

        session_mgr = getattr(store, "session_mgr", None)
        if session_mgr is not None:
            try:
                sessions = session_mgr.list_sessions()
            except Exception:
                sessions = []
            for sess in sessions:
                sess_mapping = sess.get("mapping") or {}
                if isinstance(sess_mapping, dict):
                    mapping.update(sess_mapping)

        current = getattr(store, "last_mapping", None) or {}
        if isinstance(current, dict):
            mapping.update(current)

        return mapping

    def ui_mapping() -> dict[str, str]:
        base = full_mapping()
        text = masked_input_field.value or ""
        if not base or not text:
            return {}
        return {k: v for k, v in base.items() if k in text}

    def apply_active_mapping(_):
        mapping = full_mapping()
        unmasked_output_field.value = de_anonymize(masked_input_field.value or "", mapping)
        setattr(store, "demask_input_text", masked_input_field.value or "")
        setattr(store, "demask_output_text", unmasked_output_field.value or "")
        sync_equal_height()
        rebuild_mapping_rows()
        update_clear_icon()
        page.update()

    def clear_fields(_):
        masked_input_field.value = ""
        unmasked_output_field.value = ""
        setattr(store, "demask_input_text", "")
        setattr(store, "demask_output_text", "")
        update_placeholder()
        sync_equal_height()
        rebuild_mapping_rows()
        page.update()

    clear_button.on_click = clear_fields

    def copy_output(_):
        page.set_clipboard(unmasked_output_field.value or "")

    def on_masked_change(_):
        setattr(store, "demask_input_text", masked_input_field.value or "")
        mapping = full_mapping()
        if getattr(store, "auto_demask_enabled", False) and mapping:
            unmasked_output_field.value = de_anonymize(masked_input_field.value or "", mapping)
            setattr(store, "demask_output_text", unmasked_output_field.value or "")
        sync_equal_height()
        update_placeholder()
        rebuild_mapping_rows()
        page.update()

    masked_input_field.on_change = on_masked_change

    page.on_resize = lambda _: (sync_equal_height(), page.update())

    actions_top = ft.Row(
        [
            ft.Row(
                [
                    pill_button(
                        t(lang, "vault.apply_active"),
                        icon=ft.Icons.KEY,
                        on_click=apply_active_mapping,
                        theme=theme,
                        scale=1.05,
                    ),
                    outlined_pill(
                        t(lang, "btn.copy_out"),
                        icon=ft.Icons.CONTENT_COPY,
                        on_click=copy_output,
                        theme=theme,
                        scale=1.05,
                    ),
                ],
                spacing=12,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        ],
        spacing=0,
        alignment=ft.MainAxisAlignment.START,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )

    editors_row = ft.Row(
        [
            ft.Container(masked_input_box, expand=True),
            ft.Container(unmasked_output_box, expand=True),
        ],
        spacing=16,
        expand=False,
        vertical_alignment=ft.CrossAxisAlignment.START,
    )

    mapping_title = ft.Text(
        t(lang, "vault.active_map"),
        weight=ft.FontWeight.W_600,
        color=theme["text_secondary"],
    )

    search_box = ft.TextField(
        hint_text=t(lang, "search.placeholder"),
        prefix_icon=ft.Icons.SEARCH,
        bgcolor=theme["surface"],
        border_radius=10,
        filled=True,
        dense=True,
        text_style=ft.TextStyle(color=theme["text_primary"]),
        hint_style=ft.TextStyle(color=theme["text_secondary"]),
        cursor_color=theme["accent"],
    )

    mapping_list = ft.Column(spacing=10)

    def as_text(v) -> str:
        if isinstance(v, (str, int, float, bool)) or v is None:
            return str(v if v is not None else "")
        try:
            return json.dumps(v, ensure_ascii=False)
        except Exception:
            return str(v)

    def make_row(k: str, v) -> ft.Control:
        return ft.Container(
            bgcolor=theme["surface"],
            border_radius=8,
            padding=ft.padding.symmetric(10, 12),
            content=ft.Row(
                [
                    ft.Container(ft.Text(k, selectable=False, color=theme["text_primary"]), expand=1),
                    ft.Container(
                        ft.Text(
                            as_text(v),
                            selectable=False,
                            color=theme["text_primary"],
                            overflow=ft.TextOverflow.VISIBLE,
                            max_lines=None,
                            text_align=ft.TextAlign.LEFT,
                        ),
                        expand=1,
                        alignment=ft.alignment.center_left,
                        padding=ft.padding.only(left=20, right=28),
                    ),
                ],
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        )

    def group_header(typ: str, count: int) -> ft.Control:
        badge = ft.Container(
            padding=ft.padding.symmetric(2, 8),
            bgcolor=theme["surface_muted"],
            border_radius=20,
            content=ft.Text(str(count), size=12, color=theme["text_secondary"]),
        )
        title = ft.Text(type_label(typ), weight=ft.FontWeight.W_600, color=theme["text_primary"])
        return ft.Row(
            [
                title,
                badge,
            ],
            spacing=8,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

    def build_group(typ: str, items: list[tuple[str, str]]) -> ft.Control:
        rows = [make_row(k, v) for k, v in items]
        return ft.Column(
            [
                group_header(typ, len(items)),
                ft.Container(height=6),
                ft.Column(rows, spacing=6),
            ],
            spacing=4,
        )

    mapping_header_row = ft.Row(
        [
            mapping_title,
            ft.Container(expand=True),
            ft.Container(search_box, width=420),
        ],
        alignment=ft.MainAxisAlignment.START,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )

    mapping_block = ft.Column(
        [
            mapping_header_row,
            mapping_list,
        ],
        spacing=10,
        expand=False,
        visible=False,
    )

    def rebuild_mapping_rows() -> None:
        mapping = ui_mapping()
        q = (search_box.value or "").strip().lower()

        filtered: list[tuple[str, str, str]] = []
        for k in mapping.keys():
            v = mapping[k]
            kv = as_text(v)
            if q and (q not in k.lower()) and (q not in kv.lower()):
                continue
            typ = extract_type(k)
            filtered.append((typ, k, v))

        groups: dict[str, list[tuple[str, str]]] = {}
        for typ, k, v in filtered:
            groups.setdefault(typ, []).append((k, v))

        ordered_types = sorted(groups.keys(), key=group_sort_key)

        controls: list[ft.Control] = []
        for i, typ in enumerate(ordered_types):
            items = sorted(groups[typ], key=lambda kv: kv[0].lower())
            controls.append(build_group(typ, items))
            if i < len(ordered_types) - 1:
                controls.append(ft.Container(height=12))

        mapping_list.controls = controls
        mapping_block.visible = bool(mapping)
        page.update()

    search_box.on_change = lambda _: rebuild_mapping_rows()

    rebuild_mapping_rows()
    update_placeholder()
    sync_equal_height()

    base_margin = ft.margin.only(left=4, right=4)

    content_column = ft.Column(
        [
            ft.Container(content=actions_top, margin=base_margin),
            ft.Container(height=5),
            ft.Container(content=editors_row, margin=base_margin),
            ft.Container(height=16),
            ft.Container(content=mapping_block, margin=base_margin),
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