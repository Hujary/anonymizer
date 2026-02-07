from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple
import threading
import re

import flet as ft

from ui.helpers.dashboard_helpers import (
    typ_of,
    gen_token,
    type_label,
    group_sort_key,
)
from ui.style.translations import t

AUTO_MASK_DEBOUNCE_SECONDS = 0.3


@dataclass
class DashboardContext:
    page: ft.Page
    theme: Dict[str, Any]
    store: Any
    lang: str
    accent: str

    input_title: str
    input_sub: str

    input_field: ft.TextField
    output_field: ft.TextField

    results_text: ft.Text
    results_banner: ft.Container

    token_groups_col: ft.Column
    tokens_host: ft.Container
    tokens_section: ft.Column

    search_box: ft.TextField
    manual_token_text: ft.TextField
    manual_token_type: ft.Dropdown
    manual_token_type_values: List[str]
    manual_token_type_value: List[str]
    add_button: ft.FilledButton

    sync_equal_height: Any
    update_placeholder: Any

    token_vals: Dict[str, str] = field(default_factory=dict)
    token_keys_order: List[str] = field(default_factory=list)
    editing_keys: set[str] = field(default_factory=set)

    debounce_timer: threading.Timer | None = None


def show_snack(ctx: DashboardContext, message: str, kind: str) -> None:
    if kind == "danger":
        bg = ctx.theme["danger"]
    elif kind == "warning":
        bg = ctx.theme["warning"]
    else:
        bg = ctx.theme["surface_muted"]

    ctx.page.snack_bar = ft.SnackBar(ft.Text(message), bgcolor=bg)
    ctx.page.snack_bar.open = True
    ctx.page.update()


def token_source_label(ctx: DashboardContext, key: str, value: str) -> str:
    hits = getattr(ctx.store, "last_hits", []) or []
    src = ctx.input_field.value or ""
    typ = typ_of(key)

    has_ner = False
    has_regex = False

    for hit in hits:
        label = None
        source = None
        start = None
        ende = None

        if hasattr(hit, "__dict__"):
            label = getattr(hit, "label", None)
            source = getattr(hit, "source", None)
            start = getattr(hit, "start", None)
            ende = getattr(hit, "ende", None)
        elif isinstance(hit, dict):
            label = hit.get("label")
            source = hit.get("source")
            start = hit.get("start")
            ende = hit.get("end")
        else:
            continue

        if label != typ:
            continue
        if start is None or ende is None:
            continue
        if src[start:ende] != value:
            continue

        if source == "ner":
            has_ner = True
        elif source == "regex":
            has_regex = True

    if has_ner and has_regex:
        return "NER + Regex"
    if has_ner:
        return "NER"
    if has_regex:
        return "Regex"
    return "Manual"


def update_banner(ctx: DashboardContext, mapping: Dict[str, str]) -> None:
    total_tokens = len(mapping or {})

    if total_tokens == 0:
        ctx.results_text.value = t(ctx.lang, "status.banner.none")
    elif total_tokens == 1:
        ctx.results_text.value = t(ctx.lang, "status.banner.one")
    else:
        ctx.results_text.value = t(ctx.lang, "status.banner.some", total=total_tokens)

    ctx.results_banner.visible = True
    ctx.store.set_dash(
        output_text=ctx.output_field.value or "",
        status_text=ctx.results_text.value,
    )


def _push_mapping_into_session(ctx: DashboardContext, mapping: Dict[str, str]) -> None:
    if not mapping:
        return
    if not getattr(ctx.store, "reversible", True):
        return
    if hasattr(ctx.store, "add_session_mapping"):
        try:
            ctx.store.add_session_mapping(mapping)
        except Exception:
            pass


def build_token_rows(ctx: DashboardContext, mapping: Dict[str, str]) -> None:
    ctx.token_groups_col.controls.clear()
    ctx.token_vals.clear()
    ctx.token_keys_order.clear()

    q = (ctx.search_box.value or "").strip().lower()

    def match_filter(k: str, v: str) -> bool:
        if not q:
            return True
        return (q in k.lower()) or (q in (v or "").lower()) or (q in typ_of(k).lower())

    items_all = [(k, v) for k, v in mapping.items() if match_filter(k, v)]

    if not items_all:
        ctx.tokens_host.visible = False
        ctx.page.update()
        return

    for key, value in sorted(items_all, key=lambda kv: (typ_of(kv[0]), kv[0].lower())):
        ctx.token_vals[key] = value
        ctx.token_keys_order.append(key)

    groups: Dict[str, List[tuple[str, str]]] = {}
    for key, value in items_all:
        typ = typ_of(key)
        groups.setdefault(typ, []).append((key, value))

    ordered_types = sorted(groups.keys(), key=group_sort_key)

    def make_token_row(key: str, value: str) -> ft.Control:
        type_badge = ft.Container(
            padding=ft.padding.symmetric(2, 8),
            bgcolor=ctx.theme["surface_muted"],
            border_radius=20,
            content=ft.Text(typ_of(key), size=11, color=ctx.theme["text_secondary"]),
        )

        src_label = token_source_label(ctx, key, value)
        src_badge = ft.Container(
            padding=ft.padding.symmetric(2, 8),
            bgcolor=ctx.theme["surface_muted"],
            border_radius=20,
            content=ft.Text(src_label, size=11, color=ctx.theme["text_secondary"]),
        )

        head = ft.Row(
            [
                ft.Text(key, size=12, color=ctx.theme["text_secondary"]),
                type_badge,
                src_badge,
                ft.Container(expand=True),
            ],
            spacing=8,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        if key in ctx.editing_keys:
            tf_ref = ft.Ref[ft.TextField]()
            tf = ft.TextField(
                ref=tf_ref,
                value=value,
                autofocus=True,
                dense=False,
                multiline=False,
                bgcolor=ctx.theme["background"],
                filled=True,
                border_radius=8,
                border=ft.InputBorder.OUTLINE,
                border_color=ctx.accent,
                focused_border_color=ctx.accent,
                content_padding=ft.padding.symmetric(10, 12),
            )

            def cancel_edit(_: ft.ControlEvent):
                if key in ctx.editing_keys:
                    ctx.editing_keys.remove(key)
                    build_token_rows(
                        ctx,
                        {k: ctx.token_vals[k] for k in ctx.token_keys_order},
                    )

            def save_edit_local(_: ft.ControlEvent):
                src_text = ctx.input_field.value or ""
                old_val = ctx.token_vals.get(key, "")
                new_val = tf_ref.current.value or ""

                if not new_val:
                    msg = (
                        "Der Wert darf nicht leer sein."
                        if ctx.lang == "de"
                        else "Value must not be empty."
                    )
                    show_snack(ctx, msg, "danger")
                    return

                if not _find_occurrences(src_text, new_val):
                    msg = (
                        "Der angegebene Text wurde im Eingabetext nicht als eigenständiger Treffer gefunden."
                        if ctx.lang == "de"
                        else "The given text was not found as a standalone match in the input."
                    )
                    show_snack(ctx, msg, "danger")
                    return

                if len(new_val) < len(old_val) or old_val not in new_val:
                    msg = (
                        "Bearbeiten darf den Treffer nur erweitern, nicht verkürzen. "
                        "Beispiel: 'Briachstraße' → 'Briachstraße 2' ist erlaubt, "
                        "aber nicht 'Briachstraße' → 'Briach'."
                        if ctx.lang == "de"
                        else "Editing may only extend the match, not shorten it. "
                             "Example: 'Briachstraße' → 'Briachstraße 2' is allowed, "
                             "but not 'Briachstraße' → 'Briach'."
                    )
                    show_snack(ctx, msg, "warning")
                    return

                if new_val == old_val:
                    ctx.editing_keys.discard(key)
                    build_token_rows(
                        ctx,
                        {k: ctx.token_vals[k] for k in ctx.token_keys_order},
                    )
                    return

                typ = typ_of(key)
                new_token = gen_token(typ, new_val)

                if new_token not in ctx.token_vals:
                    ctx.token_vals[new_token] = new_val
                    ctx.token_keys_order.append(new_token)

                ctx.token_vals[key] = old_val

                ctx.editing_keys.discard(key)

                new_mapping = {k: ctx.token_vals[k] for k in ctx.token_keys_order}
                ctx.store.set_mapping(
                    new_mapping,
                    getattr(ctx.store, "last_hits", []) or [],
                    src_text,
                    ctx.output_field.value or "",
                )
                _push_mapping_into_session(ctx, new_mapping)

                build_token_rows(ctx, new_mapping)
                apply_current_edits(ctx)

            def delete_token_local(_: ft.ControlEvent):
                current_map = dict(getattr(ctx.store, "last_mapping", {}) or {})
                hits = list(getattr(ctx.store, "last_hits", []) or [])

                original_value = ctx.token_vals.get(key, "")

                if original_value:
                    ctx.output_field.value = (
                        ctx.output_field.value or ""
                    ).replace(key, original_value)

                if key in ctx.token_vals:
                    ctx.token_vals.pop(key)
                if key in ctx.editing_keys:
                    ctx.editing_keys.remove(key)
                if key in ctx.token_keys_order:
                    ctx.token_keys_order.remove(key)

                if key in current_map:
                    current_map.pop(key)

                mgr = getattr(ctx.store, "session_mgr", None)
                if mgr is not None:
                    try:
                        mgr.remove_from_active_mapping(key)
                    except Exception:
                        pass

                src_text = ctx.input_field.value or ""
                masked_text = ctx.output_field.value or ""
                ctx.store.set_mapping(current_map, hits, src_text, masked_text)
                _push_mapping_into_session(ctx, current_map)

                ctx.tokens_section.visible = True
                build_token_rows(ctx, current_map)
                update_banner(ctx, current_map)
                ctx.sync_equal_height()
                ctx.page.update()

            actions = ft.Row(
                [
                    ft.Container(expand=True),
                    ft.TextButton(
                        "Löschen" if ctx.lang == "de" else "Delete",
                        style=ft.ButtonStyle(
                            color=ctx.theme["danger"]
                        ),
                        on_click=delete_token_local,
                    ),
                    ft.TextButton(
                        "Abbrechen" if ctx.lang == "de" else "Cancel",
                        style=ft.ButtonStyle(
                            color=ctx.theme["text_secondary"]
                        ),
                        on_click=cancel_edit,
                    ),
                    ft.FilledButton(
                        "Übernehmen" if ctx.lang == "de" else "Apply",
                        on_click=save_edit_local,
                        bgcolor=ctx.accent,
                        color=ft.Colors.WHITE,
                    ),
                ],
                spacing=8,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            )

            body = ft.Column([tf, actions], spacing=8)
        else:

            def start_edit_local(_: ft.ControlEvent):
                ctx.editing_keys.add(key)
                build_token_rows(
                    ctx,
                    {k: ctx.token_vals[k] for k in ctx.token_keys_order},
                )

            body = ft.Container(
                bgcolor=ctx.theme["surface_muted"],
                border_radius=8,
                border=ft.border.all(1, ctx.theme["divider"]),
                padding=ft.padding.symmetric(10, 12),
                content=ft.Row(
                    [
                        ft.Text(
                            value or "—",
                            selectable=False,
                            color=ctx.theme["text_primary"],
                            expand=True,
                        ),
                        ft.IconButton(
                            icon=ft.Icons.EDIT,
                            icon_color=ctx.theme["text_secondary"],
                            tooltip="Bearbeiten" if ctx.lang == "de" else "Edit",
                            on_click=start_edit_local,
                        ),
                    ],
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                on_click=start_edit_local,
            )

        return ft.Column([head, body], spacing=6)

    def group_header(typ: str, count: int) -> ft.Control:
        badge = ft.Container(
            padding=ft.padding.symmetric(2, 8),
            bgcolor=ctx.theme["surface_muted"],
            border_radius=20,
            content=ft.Text(str(count), size=12, color=ctx.theme["text_secondary"]),
        )
        title = ft.Text(
            type_label(ctx.lang, typ),
            weight=ft.FontWeight.W_600,
            color=ctx.theme["text_primary"],
        )
        return ft.Row(
            [title, badge],
            spacing=8,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

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
        ctx.token_groups_col.controls.append(grp)
        if i < len(ordered_types) - 1:
            ctx.token_groups_col.controls.append(ft.Container(height=16))

    ctx.tokens_host.visible = True
    ctx.page.update()


def update_add_button_state(ctx: DashboardContext) -> None:
    src = (ctx.input_field.value or "").strip()
    val = (ctx.manual_token_text.value or "").strip()

    if not src or not val:
        enabled = False
    else:
        enabled = True

    ctx.add_button.disabled = not enabled
    if enabled:
        ctx.add_button.bgcolor = ctx.accent
        ctx.add_button.color = ft.Colors.WHITE
    else:
        ctx.add_button.bgcolor = None
        ctx.add_button.color = None

    ctx.page.update()


def _find_occurrences(text: str, value: str) -> List[Tuple[int, int]]:
    if not value:
        return []
    if re.fullmatch(r"\w+", value):
        pattern = r"\b" + re.escape(value) + r"\b"
        res: List[Tuple[int, int]] = []
        for m in re.finditer(pattern, text):
            res.append((m.start(), m.end()))
        return res
    res: List[Tuple[int, int]] = []
    start = 0
    n = len(value)
    while True:
        idx = text.find(value, start)
        if idx == -1:
            break
        res.append((idx, idx + n))
        start = idx + 1
    return res


@dataclass
class MaskSpan:
    start: int
    end: int
    token: str
    value: str


def _build_spans(text: str, mapping: Dict[str, str]) -> List[MaskSpan]:
    spans: List[MaskSpan] = []
    for token, value in mapping.items():
        if not value:
            continue
        for start, end in _find_occurrences(text, value):
            spans.append(MaskSpan(start=start, end=end, token=token, value=value))
    return spans


def _select_non_overlapping_spans(spans: List[MaskSpan], text_len: int) -> List[MaskSpan]:
    spans_sorted = sorted(spans, key=lambda s: (-(s.end - s.start), s.start))
    used = [False] * text_len
    chosen: List[MaskSpan] = []
    for span in spans_sorted:
        overlap = any(used[i] for i in range(span.start, span.end))
        if overlap:
            continue
        for i in range(span.start, span.end):
            used[i] = True
        chosen.append(span)
    chosen.sort(key=lambda s: s.start)
    return chosen


def _apply_spans(text: str, spans: List[MaskSpan]) -> str:
    if not spans:
        return text
    parts: List[str] = []
    pos = 0
    for span in spans:
        if span.start > pos:
            parts.append(text[pos:span.start])
        parts.append(span.token)
        pos = span.end
    if pos < len(text):
        parts.append(text[pos:])
    return "".join(parts)


def _mask_with_mapping(text: str, mapping: Dict[str, str]) -> Tuple[str, Dict[str, str]]:
    if not mapping:
        return text, {}
    spans = _build_spans(text, mapping)
    if not spans:
        return text, {}
    chosen = _select_non_overlapping_spans(spans, len(text))
    masked = _apply_spans(text, chosen)
    used_mapping: Dict[str, str] = {}
    for span in chosen:
        used_mapping[span.token] = span.value
    return masked, used_mapping


def add_manual_token(ctx: DashboardContext) -> None:
    src = ctx.input_field.value or ""
    if not src.strip():
        msg = t(ctx.lang, "status.no_input")
        show_snack(ctx, msg, "danger")
        return

    val = (ctx.manual_token_text.value or "").strip()
    if not val:
        msg = (
            "Bitte Text für den Token eingeben oder einfügen."
            if ctx.lang == "de"
            else "Please enter or paste text for the token."
        )
        show_snack(ctx, msg, "danger")
        return

    if not _find_occurrences(src, val):
        msg = (
            "Der angegebene Text wurde im Eingabetext nicht als eigenständiger Treffer gefunden."
            if ctx.lang == "de"
            else "The given text was not found as a standalone match in the input."
        )
        show_snack(ctx, msg, "danger")
        return

    typ = ctx.manual_token_type_value[0] or "MISC"

    current_map = dict(getattr(ctx.store, "last_mapping", {}) or {})
    hits = list(getattr(ctx.store, "last_hits", []) or [])

    to_delete = [k for k, v in current_map.items() if v == val]
    for k in to_delete:
        current_map.pop(k, None)

    token = gen_token(typ, val)
    candidate_map = dict(current_map)
    candidate_map[token] = val

    masked_text, used_mapping = _mask_with_mapping(src, candidate_map)

    if token not in used_mapping:
        msg = (
            "Der neue Token überschneidet sich vollständig mit längeren Treffern "
            "oder wird durch die Maskierungslogik nicht verwendet."
            if ctx.lang == "de"
            else "The new token is fully overlapped by longer matches or is not used by the masking logic."
        )
        show_snack(ctx, msg, "warning")
        return

    ctx.output_field.value = masked_text
    ctx.input_field.value = src
    ctx.store.set_dash(input_text=src)
    ctx.store.set_mapping(used_mapping, hits, src, masked_text)
    _push_mapping_into_session(ctx, used_mapping)

    ctx.search_box.value = ""
    build_token_rows(ctx, used_mapping)
    update_banner(ctx, used_mapping)

    ctx.manual_token_text.value = ""
    update_add_button_state(ctx)
    ctx.page.update()


def apply_current_edits(ctx: DashboardContext) -> None:
    src = ctx.input_field.value or ""
    if not src:
        ctx.output_field.value = ""
        ctx.store.set_dash(
            output_text="", status_text=ctx.results_text.value or ""
        )
        ctx.sync_equal_height()
        ctx.page.update()
        return

    if not ctx.token_vals:
        ctx.output_field.value = src
        ctx.store.set_dash(
            output_text=src, status_text=ctx.results_text.value or ""
        )
        ctx.sync_equal_height()
        ctx.page.update()
        return

    edits = {k: (ctx.token_vals.get(k, "") or "") for k in ctx.token_keys_order}
    for k, v in list(edits.items()):
        if not v:
            continue
        if not _find_occurrences(src, v):
            msg = (
                f"'{k}' nicht (mehr) als eigenständiger Treffer im Text gefunden. Prüfe die Werte."
                if ctx.lang == "de"
                else f"'{k}' no longer found as a standalone match in text. Please check the values."
            )
            show_snack(ctx, msg, "warning")
            return

    masked_text, used_mapping = _mask_with_mapping(src, edits)

    ctx.output_field.value = masked_text

    hits = list(getattr(ctx.store, "last_hits", []) or [])
    ctx.store.set_mapping(used_mapping, hits, src, masked_text)
    _push_mapping_into_session(ctx, used_mapping)
    update_banner(ctx, used_mapping)

    ctx.sync_equal_height()
    ctx.page.update()


def run_masking_internal(ctx: DashboardContext, auto: bool = False) -> None:
    from services.anonymizer import anonymize

    text = ctx.input_field.value or ""
    if not text.strip():
        if auto:
            ctx.output_field.value = ""
            ctx.store.set_mapping({}, [], "", "")
            ctx.store.set_dash(output_text="", status_text=ctx.results_text.value or "")
            ctx.sync_equal_height()
            ctx.page.update()
            return
        msg = t(ctx.lang, "status.no_input")
        show_snack(ctx, msg, "warning")
        return

    try:
        _, base_mapping, hits = anonymize(
            text, reversible=getattr(ctx.store, "reversible", True)
        )
    except Exception as e:
        show_snack(ctx, f"Masking failed: {e}", "danger")
        return

    merged_mapping: Dict[str, str] = dict(base_mapping or {})

    session_mapping: Dict[str, str] = {}
    mgr = getattr(ctx.store, "session_mgr", None)
    if mgr is not None and getattr(ctx.store, "reversible", True):
        try:
            session_mapping = mgr.get_active_mapping()
        except Exception:
            session_mapping = {}

    if session_mapping:
        for token, value in session_mapping.items():
            if not value:
                continue
            if not _find_occurrences(text, value):
                continue
            if token in merged_mapping and merged_mapping[token] == value:
                continue
            merged_mapping[token] = value

    masked_text, used_mapping = _mask_with_mapping(text, merged_mapping)

    ctx.output_field.value = masked_text
    ctx.sync_equal_height()
    ctx.store.set_mapping(used_mapping, hits, text, masked_text)

    if getattr(ctx.store, "reversible", True) and used_mapping:
        if hasattr(ctx.store, "add_session_mapping"):
            ctx.store.add_session_mapping(used_mapping)

    ctx.tokens_section.visible = True
    ctx.editing_keys.clear()
    if used_mapping:
        build_token_rows(ctx, used_mapping)
    else:
        ctx.token_groups_col.controls.clear()
        ctx.tokens_host.visible = False

    update_banner(ctx, used_mapping)
    ctx.page.update()


def _cancel_debounce(ctx: DashboardContext) -> None:
    if ctx.debounce_timer is not None:
        try:
            ctx.debounce_timer.cancel()
        except Exception:
            pass
        ctx.debounce_timer = None


def clear_both(ctx: DashboardContext) -> None:
    _cancel_debounce(ctx)

    ctx.input_field.value = ""
    ctx.output_field.value = ""
    ctx.results_text.value = ""
    ctx.results_banner.visible = False
    ctx.token_vals.clear()
    ctx.token_keys_order.clear()
    ctx.token_groups_col.controls.clear()
    ctx.editing_keys.clear()
    ctx.search_box.value = ""
    ctx.manual_token_text.value = ""
    ctx.manual_token_type_value[0] = (
        "MISC"
        if "MISC" in ctx.manual_token_type_values
        else ctx.manual_token_type_values[0]
    )
    ctx.manual_token_type.value = ctx.manual_token_type_value[0]
    ctx.tokens_section.visible = False
    ctx.tokens_host.visible = False
    ctx.store.set_mapping({}, [], "", "")
    ctx.store.set_dash(input_text="", output_text="", status_text="")

    if hasattr(ctx.store, "close_active_session"):
        ctx.store.close_active_session()

    ctx.update_placeholder()
    ctx.sync_equal_height()
    update_add_button_state(ctx)
    ctx.page.update()


def handle_input_change(ctx: DashboardContext) -> None:
    text = ctx.input_field.value or ""
    ctx.store.set_dash(input_text=text)
    ctx.update_placeholder()

    if not text.strip():
        _cancel_debounce(ctx)

        if hasattr(ctx.store, "close_active_session"):
            ctx.store.close_active_session()

        ctx.token_vals.clear()
        ctx.token_keys_order.clear()
        ctx.token_groups_col.controls.clear()
        ctx.editing_keys.clear()
        ctx.results_text.value = ""
        ctx.results_banner.visible = False
        ctx.tokens_section.visible = False
        ctx.tokens_host.visible = False
        ctx.output_field.value = ""
        ctx.store.set_mapping({}, [], "", "")
        ctx.store.set_dash(status_text="")
        ctx.sync_equal_height()
        update_add_button_state(ctx)
        ctx.page.update()
        return

    ctx.sync_equal_height()
    update_add_button_state(ctx)
    ctx.page.update()

    auto_enabled = getattr(ctx.store, "auto_mask_enabled", False)
    if not auto_enabled:
        _cancel_debounce(ctx)
        return

    _cancel_debounce(ctx)

    def _run():
        try:
            run_masking_internal(ctx, auto=True)
        except Exception:
            pass

    timer = threading.Timer(AUTO_MASK_DEBOUNCE_SECONDS, _run)
    timer.daemon = True
    ctx.debounce_timer = timer
    timer.start()


def refresh_tokens_from_store(ctx: DashboardContext) -> None:
    mapping = getattr(ctx.store, "last_mapping", None) or {}
    if mapping:
        build_token_rows(ctx, mapping)
        ctx.tokens_section.visible = True
        update_banner(ctx, mapping)
    else:
        ctx.token_groups_col.controls.clear()
        ctx.tokens_host.visible = False
    update_add_button_state(ctx)