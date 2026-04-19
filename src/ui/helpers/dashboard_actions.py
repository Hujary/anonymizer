from __future__ import annotations

from typing import Dict, List, Set
import threading

import flet as ft

from core import config
from pipeline.validation import filter_effective_hits_for_masking
from ui.helpers.dashboard_context import DashboardContext, AUTO_MASK_DEBOUNCE_SECONDS, OccurrenceRow
from ui.helpers.dashboard_helpers import gen_token
from ui.helpers.dashboard_masking_engine import (
    MaskSpan,
    apply_spans,
    find_best_occurrence,
    find_occurrences,
    mapping_from_spans,
    select_non_overlapping_spans,
)
from ui.helpers.dashboard_token_renderer import build_token_rows
from ui.style.translations import t


def _active_session_secret(ctx: DashboardContext) -> str:
    mgr = getattr(ctx.store, "session_mgr", None)
    if mgr is None:
        raise RuntimeError("SessionManager nicht verfügbar.")
    return mgr.get_or_create_active_session_secret()


def _allowed_token_types_from_config() -> Set[str]:
    flags = config.get_flags() or {}

    allowed: Set[str] = set()

    if flags.get("use_regex", True):
        rx = config.get("regex_labels", []) or []
        for x in rx:
            s = str(x).strip().upper()
            if s:
                allowed.add(s)

    if flags.get("use_ner", True):
        ner = config.get("ner_labels", []) or []
        for x in ner:
            s = str(x).strip().upper()
            if s:
                allowed.add(s)

    return allowed


def _filter_session_mapping_to_allowed_types(
    session_mapping: Dict[str, str],
    allowed_types: Set[str],
) -> Dict[str, str]:
    if not session_mapping:
        return {}
    if not allowed_types:
        return {}

    out: Dict[str, str] = {}
    for token, value in session_mapping.items():
        if not token or not value:
            continue

        label = ""
        if token.startswith("[") and "_" in token:
            label = token[1:].split("_", 1)[0].strip().upper()

        if label not in allowed_types:
            continue

        out[token] = value

    return out


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


def _source_label_for_hit(hit) -> str:
    has_ner = bool(getattr(hit, "from_ner", False))
    has_regex = bool(getattr(hit, "from_regex", False))
    source = getattr(hit, "source", "")

    if has_ner and has_regex:
        return "NER + Regex"
    if has_ner:
        return "NER"
    if has_regex:
        return "Regex"
    if source == "dict":
        return "Manual"
    return "Manual"


def _row_id_for_hit(hit) -> str:
    label = str(getattr(hit, "label", "")).upper()
    source = str(getattr(hit, "source", "")).lower()
    start = int(getattr(hit, "start"))
    ende = int(getattr(hit, "ende"))
    return f"{label}:{source}:{start}:{ende}"


def _row_should_mask(row: OccurrenceRow) -> bool:
    if not row.enabled:
        return False

    if row.label == "PLZ" and row.validation_source == "postcode_ml":
        return row.validation_status == "accepted"

    return True


def _build_occurrence_rows_from_hits(ctx: DashboardContext, hits: List) -> List[OccurrenceRow]:
    src = ctx.input_field.value or ""
    session_secret = _active_session_secret(ctx)

    rows: List[OccurrenceRow] = []

    for hit in sorted(hits or [], key=lambda h: (getattr(h, "start", 0), getattr(h, "ende", 0))):
        start = int(getattr(hit, "start"))
        ende = int(getattr(hit, "ende"))
        label = str(getattr(hit, "label")).upper()
        value = src[start:ende] if src else getattr(hit, "text", "") or ""
        token = gen_token(label, value, session_secret=session_secret)

        rows.append(
            OccurrenceRow(
                row_id=_row_id_for_hit(hit),
                token=token,
                label=label,
                value=value,
                original_value=value,
                start=start,
                ende=ende,
                source=str(getattr(hit, "source", "")),
                source_label=_source_label_for_hit(hit),
                validation_source=getattr(hit, "validation_source", None),
                validation_status=getattr(hit, "validation_status", None),
                validation_score=getattr(hit, "validation_score", None),
                validation_threshold=getattr(hit, "validation_threshold", None),
                validation_reason=getattr(hit, "validation_reason", None),
                enabled=True,
            )
        )

    return rows


def _manual_row_id(label: str, start: int, ende: int, idx: int) -> str:
    return f"{label}:manual:{start}:{ende}:{idx}"


def _find_row(ctx: DashboardContext, row_id: str) -> OccurrenceRow | None:
    for row in ctx.occurrence_rows:
        if row.row_id == row_id:
            return row
    return None


def _rebuild_output_from_occurrences(ctx: DashboardContext) -> None:
    src = ctx.input_field.value or ""
    spans: List[MaskSpan] = []

    for row in ctx.occurrence_rows:
        if not _row_should_mask(row):
            continue

        spans.append(
            MaskSpan(
                row_id=row.row_id,
                start=row.start,
                end=row.ende,
                token=row.token,
                value=row.value,
            )
        )

    chosen = select_non_overlapping_spans(spans, len(src))
    masked_text = apply_spans(src, chosen)
    used_mapping = mapping_from_spans(chosen)

    ctx.output_field.value = masked_text
    ctx.store.set_mapping(used_mapping, getattr(ctx.store, "last_hits", []) or [], src, masked_text)
    _push_mapping_into_session(ctx, used_mapping)
    update_banner(ctx, used_mapping)
    ctx.sync_equal_height()


def _rebuild_token_ui(ctx: DashboardContext) -> None:
    build_token_rows(
        page=ctx.page,
        theme=ctx.theme,
        lang=ctx.lang,
        accent=ctx.accent,
        token_groups_col=ctx.token_groups_col,
        tokens_host=ctx.tokens_host,
        search_query=(ctx.search_box.value or ""),
        editing_row_ids=ctx.editing_row_ids,
        rows=ctx.occurrence_rows,
        on_start_edit=lambda row_id: _on_start_edit(ctx, row_id),
        on_cancel_edit=lambda row_id: _on_cancel_edit(ctx, row_id),
        on_save_edit=lambda row_id, value: _on_save_edit(ctx, row_id, value),
        on_delete_row=lambda row_id: _on_delete_row(ctx, row_id),
    )


def refresh_tokens_from_store(ctx: DashboardContext) -> None:
    if not ctx.occurrence_rows:
        hits = getattr(ctx.store, "last_hits", []) or []
        ctx.occurrence_rows = _build_occurrence_rows_from_hits(ctx, hits)

    if ctx.occurrence_rows:
        _rebuild_token_ui(ctx)
        ctx.tokens_section.visible = True
        update_banner(ctx, getattr(ctx.store, "last_mapping", {}) or {})
    else:
        ctx.token_groups_col.controls.clear()
        ctx.tokens_host.visible = False

    update_add_button_state(ctx)


def update_add_button_state(ctx: DashboardContext) -> None:
    src = (ctx.input_field.value or "").strip()
    val = (ctx.manual_token_text.value or "").strip()

    enabled = bool(src and val)

    ctx.add_button.disabled = not enabled
    if enabled:
        ctx.add_button.bgcolor = ctx.accent
        ctx.add_button.color = ft.Colors.WHITE
    else:
        ctx.add_button.bgcolor = None
        ctx.add_button.color = None

    ctx.page.update()


def _on_start_edit(ctx: DashboardContext, row_id: str) -> None:
    ctx.editing_row_ids.add(row_id)
    _rebuild_token_ui(ctx)


def _on_cancel_edit(ctx: DashboardContext, row_id: str) -> None:
    ctx.editing_row_ids.discard(row_id)
    _rebuild_token_ui(ctx)


def _on_save_edit(ctx: DashboardContext, row_id: str, new_val: str) -> None:
    src_text = ctx.input_field.value or ""
    row = _find_row(ctx, row_id)
    if row is None:
        return

    new_val = (new_val or "").strip()

    if not new_val:
        msg = "Der Wert darf nicht leer sein." if ctx.lang == "de" else "Value must not be empty."
        show_snack(ctx, msg, "danger")
        return

    best = find_best_occurrence(src_text, new_val, row.start, row.ende)
    if best is None:
        msg = (
            "Der angegebene Text wurde im Eingabetext nicht gefunden."
            if ctx.lang == "de"
            else "The given text was not found in the input."
        )
        show_snack(ctx, msg, "danger")
        return

    new_start, new_ende = best
    session_secret = _active_session_secret(ctx)
    new_token = gen_token(row.label, new_val, session_secret=session_secret)

    row.value = new_val
    row.start = new_start
    row.ende = new_ende
    row.token = new_token
    row.source = "manual"
    row.source_label = "Manual"
    row.validation_source = None
    row.validation_status = None
    row.validation_score = None
    row.validation_threshold = None
    row.validation_reason = "Manuell bearbeitet"
    row.enabled = True

    ctx.editing_row_ids.discard(row_id)

    _rebuild_output_from_occurrences(ctx)
    _rebuild_token_ui(ctx)
    ctx.page.update()


def _on_delete_row(ctx: DashboardContext, row_id: str) -> None:
    new_rows: List[OccurrenceRow] = []
    for row in ctx.occurrence_rows:
        if row.row_id != row_id:
            new_rows.append(row)

    ctx.occurrence_rows = new_rows
    ctx.editing_row_ids.discard(row_id)

    _rebuild_output_from_occurrences(ctx)

    if ctx.occurrence_rows:
        _rebuild_token_ui(ctx)
        ctx.tokens_section.visible = True
    else:
        ctx.token_groups_col.controls.clear()
        ctx.tokens_host.visible = False

    ctx.page.update()


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

    occurrences = find_occurrences(src, val)
    if not occurrences:
        msg = (
            "Der angegebene Text wurde im Eingabetext nicht als eigenständiger Treffer gefunden."
            if ctx.lang == "de"
            else "The given text was not found as a standalone match in the input."
        )
        show_snack(ctx, msg, "danger")
        return

    label = (ctx.manual_token_type_value[0] or "MISC").upper()
    session_secret = _active_session_secret(ctx)
    token = gen_token(label, val, session_secret=session_secret)

    existing_ids = {row.row_id for row in ctx.occurrence_rows}
    idx = 0

    for start, ende in occurrences:
        row_id = _manual_row_id(label, start, ende, idx)
        while row_id in existing_ids:
            idx += 1
            row_id = _manual_row_id(label, start, ende, idx)
        existing_ids.add(row_id)

        ctx.occurrence_rows.append(
            OccurrenceRow(
                row_id=row_id,
                token=token,
                label=label,
                value=val,
                original_value=val,
                start=start,
                ende=ende,
                source="manual",
                source_label="Manual",
                validation_source=None,
                validation_status=None,
                validation_score=None,
                validation_threshold=None,
                validation_reason="Manuell hinzugefügt",
                enabled=True,
            )
        )
        idx += 1

    ctx.occurrence_rows.sort(key=lambda row: (row.start, row.ende, row.row_id))
    ctx.manual_token_text.value = ""

    _rebuild_output_from_occurrences(ctx)
    _rebuild_token_ui(ctx)
    update_add_button_state(ctx)

    ctx.tokens_section.visible = True
    ctx.page.update()


def apply_current_edits(ctx: DashboardContext) -> None:
    _rebuild_output_from_occurrences(ctx)
    _rebuild_token_ui(ctx)
    ctx.page.update()


def run_masking_internal(ctx: DashboardContext, auto: bool = False) -> None:
    with ctx.masking_lock:
        if ctx.masking_in_progress:
            return
        ctx.masking_in_progress = True

    if ctx.on_masking_state is not None:
        try:
            ctx.on_masking_state(True)
        except Exception:
            pass

    try:
        from services.anonymizer import anonymize

        text = ctx.input_field.value or ""
        if not text.strip():
            if auto:
                ctx.output_field.value = ""
                ctx.store.set_mapping({}, [], "", "")
                ctx.store.set_dash(output_text="", status_text=ctx.results_text.value or "")
                ctx.occurrence_rows = []
                ctx.sync_equal_height()
                ctx.page.update()
                return

            msg = t(ctx.lang, "status.no_input")
            show_snack(ctx, msg, "warning")
            return

        try:
            _, used_mapping, hits = anonymize(
                text,
                reversible=getattr(ctx.store, "reversible", True),
                session_mgr=getattr(ctx.store, "session_mgr", None),
                on_phase=getattr(ctx, "on_masking_phase", None),
            )
        except Exception as e:
            show_snack(ctx, f"Masking failed: {e}", "danger")
            return

        session_mapping: Dict[str, str] = {}
        mgr = getattr(ctx.store, "session_mgr", None)
        if mgr is not None and getattr(ctx.store, "reversible", True):
            try:
                session_mapping = mgr.get_active_mapping()
            except Exception:
                session_mapping = {}

        allowed_types = _allowed_token_types_from_config()
        session_mapping = _filter_session_mapping_to_allowed_types(session_mapping, allowed_types)

        ctx.occurrence_rows = _build_occurrence_rows_from_hits(ctx, hits)
        ctx.occurrence_rows.sort(key=lambda row: (row.start, row.ende, row.row_id))

        _rebuild_output_from_occurrences(ctx)

        if session_mapping and not used_mapping:
            current_mapping = getattr(ctx.store, "last_mapping", {}) or {}
            merged = dict(current_mapping)
            for token, value in session_mapping.items():
                if token not in merged:
                    merged[token] = value
            ctx.store.set_mapping(merged, hits, text, ctx.output_field.value or "")

        ctx.store.set_mapping(getattr(ctx.store, "last_mapping", {}) or {}, hits, text, ctx.output_field.value or "")

        ctx.tokens_section.visible = True
        ctx.editing_row_ids.clear()

        if ctx.occurrence_rows:
            _rebuild_token_ui(ctx)
        else:
            ctx.token_groups_col.controls.clear()
            ctx.tokens_host.visible = False

        update_banner(ctx, getattr(ctx.store, "last_mapping", {}) or {})
        ctx.page.update()
    finally:
        if ctx.on_masking_phase is not None:
            try:
                ctx.on_masking_phase("")
            except Exception:
                pass

        if ctx.on_masking_state is not None:
            try:
                ctx.on_masking_state(False)
            except Exception:
                pass

        with ctx.masking_lock:
            ctx.masking_in_progress = False


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
    ctx.occurrence_rows.clear()
    ctx.editing_row_ids.clear()
    ctx.token_groups_col.controls.clear()
    ctx.search_box.value = ""
    ctx.manual_token_text.value = ""
    ctx.manual_token_type_value[0] = "MISC" if "MISC" in ctx.manual_token_type_values else ctx.manual_token_type_values[0]
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

        ctx.occurrence_rows.clear()
        ctx.editing_row_ids.clear()
        ctx.token_groups_col.controls.clear()
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

    if ctx.masking_in_progress:
        return

    _cancel_debounce(ctx)

    def _run() -> None:
        def _worker() -> None:
            try:
                run_masking_internal(ctx, auto=True)
            except Exception:
                import traceback
                traceback.print_exc()

        if not ctx.masking_in_progress:
            ctx.page.run_thread(_worker)

    timer = threading.Timer(AUTO_MASK_DEBOUNCE_SECONDS, _run)
    timer.daemon = True
    ctx.debounce_timer = timer
    timer.start()