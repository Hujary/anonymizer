from __future__ import annotations

import time
from datetime import datetime

import flet as ft
from core import config
from ui.style.translations import t
from ui.helpers.dashboard_helpers import type_label, group_sort_key
from ui.helpers.dashboard_actions import (
    refresh_tokens_from_store,
    run_masking_internal,
)
from services.manual_tokens import get_all, add_manual_token, remove_manual_token, ManualToken
from services.manual_categories import (
    get_all_types as get_custom_types,
    add_type as add_custom_type,
    remove_type as remove_custom_type,
)
from services.session_manager import SESSION_TTL_SECONDS

BASE_TYPES = [
    "E_MAIL",
    "TELEFON",
    "IBAN",
    "BIC",
    "URL",
    "USTID",
    "PLZ",
    "IP_ADRESSE",
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


def _format_dt(ts: float, lang: str) -> str:
    if not ts:
        return ""
    dt = datetime.fromtimestamp(ts)
    if lang == "de":
        return dt.strftime("%d.%m.%Y %H:%M:%S")
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def _format_ttl_remaining(closed_at: float | None, lang: str) -> str:
    if closed_at is None:
        return ""
    now = time.time()
    remaining = SESSION_TTL_SECONDS - (now - closed_at)
    if remaining <= 0:
        if lang == "de":
            return "abgelaufen"
        return "expired"
    mins = int(remaining // 60)
    hours = mins // 60
    mins = mins % 60
    if lang == "de":
        if hours > 0:
            return f"läuft in {hours}h {mins}min ab"
        return f"läuft in {mins}min ab"
    if hours > 0:
        return f"expires in {hours}h {mins}min"
    return f"expires in {mins}min"


def view(page: ft.Page, theme: dict, store) -> ft.Control:
    lang = getattr(store, "lang", None) or config.get("lang", "de")
    if lang not in ("de", "en"):
        lang = "de"

    title = ft.Text(
        t(lang, "nav.dictionary"),
        size=20,
        weight=ft.FontWeight.W_600,
        color=theme["text_primary"],
    )

    if lang == "de":
        subtitle_text = "Verwalte eigene Wörter und Tokens, die bei der Maskierung verwendet werden."
        add_label = "Neuen Eintrag hinzufügen"
        value_hint = "Wort oder Ausdruck…"
        new_type_hint = "Neue Kategorie (z. B. KUNDENNUMMER)…"
        save_button = "Speichern"
        cancel_button = "Abbrechen"
        delete_button = "Löschen"
        edit_button_tooltip = "Bearbeiten"
        empty_text = "Es sind noch keine eigenen Tokens vorhanden."
        add_type_label = "Kategorie hinzufügen"
        categories_title = "Eigene Kategorien"
        delete_token_msg = "Eintrag gelöscht."
        delete_type_msg = "Kategorie und zugehörige Einträge gelöscht."
        sessions_title = "Maskierungssessions"
        sessions_empty_text = "Es sind noch keine Sessions vorhanden."
        session_active_label = "Aktive Session"
        session_closed_label = "Abgeschlossene Session"
        session_tokens_label = "Tokens"
        session_created_label = "Erstellt"
        session_closed_at_label = "Beendet"
        session_tokens_heading = "Token-Mapping"
        session_token_id_header = "Token"
        session_token_value_header = "Originalwert"
        session_delete_tooltip = "Session löschen"
        session_delete_msg = "Session gelöscht."
    else:
        subtitle_text = "Manage custom words and tokens used for masking."
        add_label = "Add new entry"
        value_hint = "Word or phrase…"
        new_type_hint = "New category (e.g. CUSTOMER_ID)…"
        save_button = "Save"
        cancel_button = "Cancel"
        delete_button = "Delete"
        edit_button_tooltip = "Edit"
        empty_text = "No custom tokens yet."
        add_type_label = "Add category"
        categories_title = "Custom categories"
        delete_token_msg = "Entry deleted."
        delete_type_msg = "Category and related entries deleted."
        sessions_title = "Masking sessions"
        sessions_empty_text = "No sessions yet."
        session_active_label = "Active session"
        session_closed_label = "Closed session"
        session_tokens_label = "Tokens"
        session_created_label = "Created"
        session_closed_at_label = "Closed"
        session_tokens_heading = "Token mapping"
        session_token_id_header = "Token"
        session_token_value_header = "Original value"
        session_delete_tooltip = "Delete session"
        session_delete_msg = "Session deleted."

    subtitle = ft.Text(
        subtitle_text,
        size=13,
        color=theme["text_secondary"],
    )

    tokens: list[ManualToken] = get_all()
    editing_key: list[tuple[str, str] | None] = [None]

    expanded_session_ids: list[set[str]] = [set()]

    add_value_field = ft.TextField(
        hint_text=value_hint,
        bgcolor=theme["surface"],
        border_radius=10,
        filled=True,
        dense=True,
        expand=True,
    )

    type_options_state: list[list[str]] = [_all_types()]

    add_type_dropdown = ft.Dropdown(
        options=[ft.dropdown.Option(v, text=type_label(lang, v)) for v in type_options_state[0]],
        value="MISC",
        dense=True,
        text_size=12,
        width=220,
        menu_height=260,
    )

    add_type_value = ["MISC"]

    def on_add_type_change(e: ft.ControlEvent):
        add_type_value[0] = e.control.value or "MISC"

    add_type_dropdown.on_change = on_add_type_change

    new_type_field = ft.TextField(
        hint_text=new_type_hint,
        bgcolor=theme["surface"],
        border_radius=10,
        filled=True,
        dense=True,
        width=260,
    )

    token_groups_col = ft.Column(spacing=12)
    categories_col = ft.Column(spacing=8)
    sessions_col = ft.Column(spacing=8)

    def refresh_type_options():
        type_options_state[0] = _all_types()
        add_type_dropdown.options = [
            ft.dropdown.Option(v, text=type_label(lang, v)) for v in type_options_state[0]
        ]
        if add_type_value[0] not in type_options_state[0]:
            add_type_value[0] = "MISC"
        add_type_dropdown.value = add_type_value[0]

    def reload_tokens():
        tokens[:] = get_all()
        build_token_rows()

    def show_snackbar(text: str, color_key: str = "danger"):
        page.snack_bar = ft.SnackBar(
            ft.Text(text),
            bgcolor=theme.get(color_key, theme["danger"]),
        )
        page.snack_bar.open = True
        page.update()

    def handle_add_category(_):
        raw = (new_type_field.value or "").strip()
        if not raw:
            msg = "Bitte eine Kategorie eingeben." if lang == "de" else "Please enter a category."
            show_snackbar(msg, "danger")
            return
        try:
            added = add_custom_type(raw)
        except Exception as e:
            show_snackbar(str(e), "danger")
            return
        new_type_field.value = ""
        refresh_type_options()
        add_type_value[0] = added
        add_type_dropdown.value = added
        build_categories_rows()
        page.update()

    def handle_add_entry(_):
        value = (add_value_field.value or "").strip()
        if not value:
            msg = "Bitte einen Wert eingeben." if lang == "de" else "Please enter a value."
            show_snackbar(msg, "danger")
            return
        typ = add_type_value[0] or "MISC"
        try:
            add_manual_token(typ, value)
        except Exception as e:
            show_snackbar(str(e), "danger")
            return
        add_value_field.value = ""
        reload_tokens()
        page.update()

    def _remask_dashboard() -> None:
        dashboard_ctx = getattr(store, "dashboard_ctx", None)
        if dashboard_ctx is None:
            return
        run_masking_internal(dashboard_ctx, auto=True)
        dashboard_ctx.update_placeholder()
        dashboard_ctx.sync_equal_height()
        dashboard_ctx.page.update()

    def _remove_from_current_mapping(tok: ManualToken):
        mapping = getattr(store, "last_mapping", None) or {}
        to_remove = [k for k, v in mapping.items() if v == tok.value]
        for key in to_remove:
            mapping.pop(key, None)
        setattr(store, "last_mapping", mapping)
        dashboard_ctx = getattr(store, "dashboard_ctx", None)
        if dashboard_ctx is not None:
            refresh_tokens_from_store(dashboard_ctx)
        _remask_dashboard()

    def _remove_values_from_current_mapping(values: list[str]):
        if not values:
            return
        mapping = getattr(store, "last_mapping", None) or {}
        to_remove = [k for k, v in mapping.items() if v in values]
        for key in to_remove:
            mapping.pop(key, None)
        setattr(store, "last_mapping", mapping)
        dashboard_ctx = getattr(store, "dashboard_ctx", None)
        if dashboard_ctx is not None:
            refresh_tokens_from_store(dashboard_ctx)
        _remask_dashboard()

    def delete_token_immediately(tok: ManualToken):
        try:
            remove_manual_token(tok.typ, tok.value)
        except Exception as e:
            show_snackbar(str(e), "danger")
            return
        _remove_from_current_mapping(tok)
        reload_tokens()
        show_snackbar(delete_token_msg, "surface_muted")

    def delete_category_immediately(typ: str):
        if typ in BASE_TYPES:
            return
        removed_values: list[str] = []
        try:
            remove_custom_type(typ)
        except Exception as e:
            show_snackbar(str(e), "danger")
            return
        for tok in list(tokens):
            if tok.typ == typ:
                removed_values.append(tok.value)
                try:
                    remove_manual_token(tok.typ, tok.value)
                except Exception:
                    pass
        _remove_values_from_current_mapping(removed_values)
        reload_tokens()
        refresh_type_options()
        if add_type_value[0] == typ:
            add_type_value[0] = "MISC"
            add_type_dropdown.value = "MISC"
        build_categories_rows()
        show_snackbar(delete_type_msg, "surface_muted")
        page.update()

    def build_token_rows():
        token_groups_col.controls.clear()
        if not tokens:
            token_groups_col.controls.append(
                ft.Container(
                    padding=ft.padding.symmetric(16, 16),
                    border_radius=10,
                    bgcolor=theme["surface_muted"],
                    content=ft.Row(
                        [
                            ft.Icon(ft.Icons.INFO_OUTLINED, size=18, color=theme["text_secondary"]),
                            ft.Text(empty_text, color=theme["text_secondary"]),
                        ],
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                )
            )
            page.update()
            return

        filtered_sorted = sorted(tokens, key=lambda t: (group_sort_key(t.typ), t.value.lower()))

        groups: dict[str, list[ManualToken]] = {}
        for tok in filtered_sorted:
            groups.setdefault(tok.typ, []).append(tok)

        def group_header(typ: str, count: int) -> ft.Control:
            badge = ft.Container(
                padding=ft.padding.symmetric(2, 8),
                bgcolor=theme["surface_muted"],
                border_radius=20,
                content=ft.Text(str(count), size=12, color=theme["text_secondary"]),
            )
            title_text = type_label(lang, typ)
            title = ft.Text(title_text, weight=ft.FontWeight.W_600, color=theme["text_primary"])
            return ft.Row(
                [title, badge],
                spacing=8,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            )

        for i, typ in enumerate(sorted(groups.keys(), key=group_sort_key)):
            items = groups[typ]
            rows: list[ft.Control] = []
            for tok in items:
                key = (tok.typ, tok.value)
                if editing_key[0] == key:
                    edit_value_field = ft.TextField(
                        value=tok.value,
                        bgcolor=theme["surface"],
                        border_radius=8,
                        filled=True,
                        dense=True,
                        expand=True,
                    )

                    edit_type_dropdown = ft.Dropdown(
                        options=[
                            ft.dropdown.Option(v, text=type_label(lang, v))
                            for v in type_options_state[0]
                        ],
                        value=tok.typ,
                        dense=True,
                        text_size=12,
                        width=220,
                        menu_height=260,
                    )

                    edit_type_state = [tok.typ]

                    def on_edit_type_change(e: ft.ControlEvent, state=edit_type_state):
                        state[0] = e.control.value or tok.typ

                    edit_type_dropdown.on_change = on_edit_type_change

                    def on_save_edit(
                        _,
                        _tok: ManualToken = tok,
                        value_field: ft.TextField = edit_value_field,
                        type_state: list[str] = edit_type_state,
                    ):
                        new_value = (value_field.value or "").strip()
                        if not new_value:
                            msg = "Bitte einen Wert eingeben." if lang == "de" else "Please enter a value."
                            show_snackbar(msg, "danger")
                            return
                        new_typ = (type_state[0] or _tok.typ).upper().strip()
                        try:
                            remove_manual_token(_tok.typ, _tok.value)
                            add_manual_token(new_typ, new_value)
                        except Exception as e:
                            show_snackbar(str(e), "danger")
                            reload_tokens()
                            editing_key[0] = None
                            page.update()
                            return
                        _remove_from_current_mapping(_tok)
                        editing_key[0] = None
                        reload_tokens()
                        page.update()

                    def on_cancel_edit(_):
                        editing_key[0] = None
                        build_token_rows()
                        page.update()

                    row = ft.Container(
                        bgcolor=theme["surface"],
                        border_radius=10,
                        padding=ft.padding.symmetric(10, 12),
                        content=ft.Column(
                            [
                                ft.Row(
                                    [
                                        edit_type_dropdown,
                                    ],
                                    spacing=8,
                                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                ),
                                ft.Container(height=6),
                                ft.Row(
                                    [
                                        edit_value_field,
                                    ],
                                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                ),
                                ft.Container(height=6),
                                ft.Row(
                                    [
                                        ft.TextButton(cancel_button, on_click=on_cancel_edit),
                                        ft.FilledButton(save_button, on_click=on_save_edit),
                                    ],
                                    spacing=8,
                                    alignment=ft.MainAxisAlignment.END,
                                ),
                            ],
                            spacing=4,
                        ),
                    )
                    rows.append(row)
                else:
                    def start_edit(e, tok_inner: ManualToken = tok):
                        editing_key[0] = (tok_inner.typ, tok_inner.value)
                        build_token_rows()
                        page.update()

                    def on_delete_click(e, tok_inner: ManualToken = tok):
                        delete_token_immediately(tok_inner)

                    value_text = ft.Text(
                        tok.value,
                        color=theme["text_primary"],
                        size=13,
                        no_wrap=False,
                        expand=True,
                    )
                    type_chip = ft.Container(
                        padding=ft.padding.symmetric(2, 8),
                        border_radius=20,
                        bgcolor=theme["surface_muted"],
                        content=ft.Text(
                            type_label(lang, tok.typ),
                            size=11,
                            color=theme["text_secondary"],
                        ),
                    )
                    action_row = ft.Row(
                        [
                            ft.IconButton(
                                icon=ft.Icons.EDIT,
                                tooltip=edit_button_tooltip,
                                icon_size=18,
                                on_click=start_edit,
                            ),
                            ft.IconButton(
                                icon=ft.Icons.DELETE_OUTLINE,
                                tooltip=delete_button,
                                icon_size=18,
                                on_click=on_delete_click,
                            ),
                        ],
                        spacing=4,
                        alignment=ft.MainAxisAlignment.END,
                    )
                    row = ft.Container(
                        bgcolor=theme["surface"],
                        border_radius=10,
                        padding=ft.padding.symmetric(10, 12),
                        content=ft.Row(
                            [
                                ft.Column(
                                    [
                                        ft.Row(
                                            [
                                                type_chip,
                                            ],
                                            spacing=8,
                                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                        ),
                                        ft.Container(height=4),
                                        value_text,
                                    ],
                                    spacing=2,
                                    expand=True,
                                ),
                                action_row,
                            ],
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                    )
                    rows.append(row)

            grp = ft.Column(
                [
                    group_header(typ, len(items)),
                    ft.Container(height=6),
                    ft.Column(rows, spacing=8),
                ],
                spacing=4,
            )
            token_groups_col.controls.append(grp)
            if i < len(groups.keys()) - 1:
                token_groups_col.controls.append(ft.Container(height=10))

        page.update()

    def build_categories_rows():
        categories_col.controls.clear()
        custom_types = [t for t in get_custom_types() if t not in BASE_TYPES]
        if not custom_types:
            return
        header = ft.Text(
            categories_title,
            size=14,
            weight=ft.FontWeight.W_600,
            color=theme["text_secondary"],
        )
        categories_col.controls.append(header)
        categories_col.controls.append(ft.Container(height=6))
        for typ in sorted(custom_types, key=str.upper):
            chip = ft.Container(
                padding=ft.padding.symmetric(4, 10),
                border_radius=20,
                bgcolor=theme["surface"],
                content=ft.Row(
                    [
                        ft.Text(
                            type_label(lang, typ),
                            size=12,
                            color=theme["text_primary"],
                        ),
                        ft.IconButton(
                            icon=ft.Icons.DELETE_OUTLINE,
                            icon_size=16,
                            tooltip=delete_button,
                            on_click=lambda e, t_name=typ: delete_category_immediately(t_name),
                        ),
                    ],
                    spacing=4,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
            )
            categories_col.controls.append(chip)
        page.update()

    def build_sessions_rows():
        sessions_col.controls.clear()
        session_mgr = getattr(store, "session_mgr", None)
        if session_mgr is None:
            return

        sessions = session_mgr.list_sessions()
        sessions_sorted = sorted(
            sessions,
            key=lambda s: s.get("created_at") or 0,
            reverse=True,
        )

        header = ft.Text(
            sessions_title,
            size=14,
            weight=ft.FontWeight.W_600,
            color=theme["text_secondary"],
        )
        sessions_col.controls.append(header)
        sessions_col.controls.append(ft.Container(height=6))

        if not sessions_sorted:
            info = ft.Container(
                padding=ft.padding.symmetric(12, 12),
                border_radius=10,
                bgcolor=theme["surface_muted"],
                content=ft.Row(
                    [
                        ft.Icon(ft.Icons.INFO_OUTLINED, size=18, color=theme["text_secondary"]),
                        ft.Text(sessions_empty_text, color=theme["text_secondary"]),
                    ],
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
            )
            sessions_col.controls.append(info)
            page.update()
            return

        def handle_delete_session(sess_id: str):
            try:
                if hasattr(session_mgr, "delete_session"):
                    session_mgr.delete_session(sess_id)
                elif hasattr(session_mgr, "remove_session"):
                    session_mgr.remove_session(sess_id)
                else:
                    raise RuntimeError("SessionManager hat keine delete/remove_session-Methode.")
            except Exception as e:
                show_snackbar(str(e), "danger")
                return
            if sess_id in expanded_session_ids[0]:
                expanded_session_ids[0].remove(sess_id)
            show_snackbar(session_delete_msg, "surface_muted")
            build_sessions_rows()

        for sess in sessions_sorted:
            sid = sess.get("session_id", "") or ""
            created_at = sess.get("created_at")
            closed_at = sess.get("closed_at")
            mapping = sess.get("mapping") or {}
            count = len(mapping)
            created_str = _format_dt(created_at, lang)
            closed_str = _format_dt(closed_at, lang) if closed_at else "-"
            if closed_at is None:
                status_label = session_active_label
                ttl_str = ""
            else:
                status_label = session_closed_label
                ttl_str = _format_ttl_remaining(closed_at, lang)
            id_text = sid if len(sid) <= 16 else f"{sid[:16]}…"
            status_chip = ft.Container(
                padding=ft.padding.symmetric(2, 8),
                border_radius=20,
                bgcolor=theme["surface_muted"],
                content=ft.Text(
                    status_label,
                    size=11,
                    color=theme["text_secondary"],
                ),
            )
            tokens_chip = ft.Container(
                padding=ft.padding.symmetric(2, 8),
                border_radius=20,
                bgcolor=theme["surface_muted"],
                content=ft.Text(
                    f"{session_tokens_label}: {count}",
                    size=11,
                    color=theme["text_secondary"],
                ),
            )
            ttl_text = ft.Text(
                ttl_str,
                size=11,
                color=theme["text_secondary"],
            ) if ttl_str else ft.Text("", size=11, color=theme["text_secondary"])
            is_expanded = sid in expanded_session_ids[0]

            def toggle_expand(e, sess_id=sid):
                if sess_id in expanded_session_ids[0]:
                    expanded_session_ids[0].remove(sess_id)
                else:
                    expanded_session_ids[0].add(sess_id)
                build_sessions_rows()

            expand_icon = ft.IconButton(
                icon=ft.Icons.KEYBOARD_ARROW_DOWN if not is_expanded else ft.Icons.KEYBOARD_ARROW_UP,
                icon_size=18,
                on_click=toggle_expand,
                tooltip="Aufklappen" if lang == "de" else "Expand",
            )

            delete_icon = ft.IconButton(
                icon=ft.Icons.DELETE_OUTLINE,
                icon_size=18,
                tooltip=session_delete_tooltip,
                on_click=lambda e, sess_id=sid: handle_delete_session(sess_id),
            )

            row_top = ft.Row(
                [
                    expand_icon,
                    ft.Text(
                        id_text,
                        size=13,
                        weight=ft.FontWeight.W_500,
                        color=theme["text_primary"],
                    ),
                    ft.Container(expand=True),
                    status_chip,
                    tokens_chip,
                    delete_icon,
                ],
                spacing=8,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            )
            row_bottom = ft.Row(
                [
                    ft.Text(
                        f"{session_created_label}: {created_str}",
                        size=11,
                        color=theme["text_secondary"],
                    ),
                    ft.Container(width=18),
                    ft.Text(
                        f"{session_closed_at_label}: {closed_str}",
                        size=11,
                        color=theme["text_secondary"],
                    ),
                    ft.Container(expand=True),
                    ttl_text,
                ],
                spacing=6,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            )

            children: list[ft.Control] = [row_top, ft.Container(height=4), row_bottom]

            if is_expanded and mapping:
                token_rows: list[ft.Control] = []
                header_row = ft.Row(
                    [
                        ft.Text(
                            session_tokens_heading,
                            size=12,
                            weight=ft.FontWeight.W_600,
                            color=theme["text_secondary"],
                        ),
                    ],
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                )
                token_rows.append(header_row)
                token_rows.append(ft.Container(height=4))

                header_cols = ft.Row(
                    [
                        ft.Text(
                            session_token_id_header,
                            size=11,
                            weight=ft.FontWeight.W_500,
                            color=theme["text_secondary"],
                            width=220,
                        ),
                        ft.Text(
                            session_token_value_header,
                            size=11,
                            weight=ft.FontWeight.W_500,
                            color=theme["text_secondary"],
                            expand=True,
                        ),
                    ],
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                )
                token_rows.append(header_cols)
                token_rows.append(ft.Container(height=2))

                for k in sorted(mapping.keys()):
                    v = mapping[k]
                    token_rows.append(
                        ft.Row(
                            [
                                ft.Text(
                                    k,
                                    size=11,
                                    color=theme["text_primary"],
                                    width=220,
                                    no_wrap=False,
                                ),
                                ft.Text(
                                    v,
                                    size=11,
                                    color=theme["text_primary"],
                                    expand=True,
                                    no_wrap=False,
                                ),
                            ],
                            vertical_alignment=ft.CrossAxisAlignment.START,
                        )
                    )

                children.append(ft.Container(height=8))
                children.append(
                    ft.Container(
                        bgcolor=theme["surface_muted"],
                        border_radius=8,
                        padding=ft.padding.symmetric(8, 10),
                        content=ft.Column(token_rows, spacing=4),
                    )
                )

            card = ft.Container(
                bgcolor=theme["surface"],
                border_radius=10,
                padding=ft.padding.symmetric(10, 12),
                content=ft.Column(
                    children,
                    spacing=4,
                ),
            )
            sessions_col.controls.append(card)

        page.update()

    add_button = ft.FilledButton(
        add_label,
        icon=ft.Icons.ADD,
        on_click=handle_add_entry,
    )

    add_type_button = ft.OutlinedButton(
        add_type_label,
        icon=ft.Icons.ADD,
        on_click=handle_add_category,
    )

    add_row = ft.Column(
        [
            ft.Text(
                add_label,
                weight=ft.FontWeight.W_600,
                size=14,
                color=theme["text_secondary"],
            ),
            ft.Container(height=8),
            ft.Row(
                [
                    add_value_field,
                    add_type_dropdown,
                    add_button,
                ],
                spacing=8,
                alignment=ft.MainAxisAlignment.START,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            ft.Container(height=10),
            ft.Row(
                [
                    new_type_field,
                    add_type_button,
                ],
                spacing=8,
                alignment=ft.MainAxisAlignment.START,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        ],
        spacing=4,
    )

    header_row = ft.Row(
        [
            title,
        ],
        alignment=ft.MainAxisAlignment.START,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )

    refresh_type_options()
    build_token_rows()
    build_categories_rows()
    build_sessions_rows()

    content = ft.Column(
        [
            header_row,
            ft.Container(height=4),
            subtitle,
            ft.Container(height=20),
            add_row,
            ft.Container(height=20),
            categories_col,
            ft.Container(height=20),
            sessions_col,
            ft.Container(height=20),
            token_groups_col,
        ],
        spacing=8,
        expand=True,
        horizontal_alignment=ft.CrossAxisAlignment.START,
        scroll=ft.ScrollMode.AUTO,
    )

    return ft.Container(
        padding=24,
        expand=True,
        bgcolor=theme["background"],
        alignment=ft.alignment.top_left,
        content=content,
    )