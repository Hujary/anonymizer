###     Dashboard Masking Controller (Flet UI Actions + Token Editing + Debounce)
### __________________________________________________________________________
#
#  - Steuert Masking-Ablauf im Dashboard (Manual Tokens, Edit, Delete, Apply)
#  - Baut/aktualisiert Token-UI (Gruppierung, Search, Edit-States)
#  - Synchronisiert UI-State ↔ AppStore (last_mapping, last_hits, dash_* Felder)
#  - Schreibt reversible Mappings in SessionManager (falls aktiv)
#  - Implementiert Auto-Mask Debounce via threading.Timer
#  - Nutzt mask_with_mapping() für deterministisches Remasking nach Edits


from __future__ import annotations

from typing import Dict
import threading

import flet as ft

from ui.helpers.dashboard_context import DashboardContext, AUTO_MASK_DEBOUNCE_SECONDS
from ui.helpers.dashboard_helpers import typ_of, gen_token
from ui.helpers.dashboard_masking_engine import find_occurrences, mask_with_mapping
from ui.helpers.dashboard_token_renderer import build_token_rows
from ui.style.translations import t


# Zeigt Snackbar im aktuellen Theme (danger/warning/default)
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



# Aktualisiert Banner-Text basierend auf Anzahl Tokens und persistiert Dashboard-State
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



# Schreibt Mapping in SessionManager, aber nur bei reversibler Maskierung
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



# Ermittelt Quellenlabel pro Token anhand last_hits (NER/Regex/Manual)
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



# Synchronisiert ctx.token_vals + ctx.token_keys_order aus einem Mapping (deterministische Sortierung)
def _sync_ctx_token_state(ctx: DashboardContext, mapping: Dict[str, str]) -> None:
    ctx.token_vals.clear()
    ctx.token_keys_order.clear()

    for key, value in sorted((mapping or {}).items(), key=lambda kv: (typ_of(kv[0]), kv[0].lower())):
        ctx.token_vals[key] = value
        ctx.token_keys_order.append(key)



# Baut Token-UI neu (Renderer bekommt Callbacks und Source-Resolver)
def _rebuild_token_ui(ctx: DashboardContext, mapping: Dict[str, str]) -> None:
    build_token_rows(
        page=ctx.page,
        theme=ctx.theme,
        lang=ctx.lang,
        accent=ctx.accent,
        token_groups_col=ctx.token_groups_col,
        tokens_host=ctx.tokens_host,
        search_query=(ctx.search_box.value or ""),
        editing_keys=ctx.editing_keys,
        mapping=mapping,
        token_source_label=lambda k, v: token_source_label(ctx, k, v),
        on_start_edit=lambda k: _on_start_edit(ctx, k),
        on_cancel_edit=lambda k: _on_cancel_edit(ctx, k),
        on_save_edit=lambda k, v: _on_save_edit(ctx, k, v),
        on_delete_token=lambda k: _on_delete_token(ctx, k),
    )



# Lädt Tokens aus Store-Mapping und aktualisiert UI (Banner, Sichtbarkeit, Add-Button)
def refresh_tokens_from_store(ctx: DashboardContext) -> None:
    mapping = getattr(ctx.store, "last_mapping", None) or {}
    _sync_ctx_token_state(ctx, mapping)

    if mapping:
        _rebuild_token_ui(ctx, mapping)
        ctx.tokens_section.visible = True
        update_banner(ctx, mapping)
    else:
        ctx.token_groups_col.controls.clear()
        ctx.tokens_host.visible = False

    update_add_button_state(ctx)



# Aktiviert/Deaktiviert "Add Token" abhängig von Input + Token-Text
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



# Startet Edit-Mode für ein Token und rebuildet UI
def _on_start_edit(ctx: DashboardContext, key: str) -> None:
    ctx.editing_keys.add(key)
    mapping = {k: ctx.token_vals[k] for k in ctx.token_keys_order if k in ctx.token_vals}
    _rebuild_token_ui(ctx, mapping)



# Bricht Edit-Mode ab und rebuildet UI
def _on_cancel_edit(ctx: DashboardContext, key: str) -> None:
    ctx.editing_keys.discard(key)
    mapping = {k: ctx.token_vals[k] for k in ctx.token_keys_order if k in ctx.token_vals}
    _rebuild_token_ui(ctx, mapping)



# Validiert und speichert Token-Edit (nur Erweiterung erlaubt), danach Remasking
def _on_save_edit(ctx: DashboardContext, key: str, new_val: str) -> None:
    src_text = ctx.input_field.value or ""
    old_val = ctx.token_vals.get(key, "")
    new_val = (new_val or "").strip()

    if not new_val:
        msg = "Der Wert darf nicht leer sein." if ctx.lang == "de" else "Value must not be empty."
        show_snack(ctx, msg, "danger")
        return

    if not find_occurrences(src_text, new_val):
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
        mapping = {k: ctx.token_vals[k] for k in ctx.token_keys_order if k in ctx.token_vals}
        _rebuild_token_ui(ctx, mapping)
        return

    new_token = gen_token(typ_of(key), new_val)

    if new_token not in ctx.token_vals:
        ctx.token_vals[new_token] = new_val
        ctx.token_keys_order.append(new_token)

    ctx.token_vals[key] = old_val
    ctx.editing_keys.discard(key)

    apply_current_edits(ctx)



# Löscht Token aus UI-State + Store-Mapping + aktiver Session; ersetzt Token im Output zurück
def _on_delete_token(ctx: DashboardContext, key: str) -> None:
    current_map = dict(getattr(ctx.store, "last_mapping", {}) or {})
    hits = list(getattr(ctx.store, "last_hits", []) or [])

    original_value = ctx.token_vals.get(key, "")

    if original_value:
        ctx.output_field.value = (ctx.output_field.value or "").replace(key, original_value)

    if key in ctx.token_vals:
        ctx.token_vals.pop(key)
    ctx.editing_keys.discard(key)
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
    _sync_ctx_token_state(ctx, current_map)
    _rebuild_token_ui(ctx, current_map)
    update_banner(ctx, current_map)
    ctx.sync_equal_height()
    ctx.page.update()



# Fügt manuell einen Token hinzu (validiert Standalone-Match, baut Mapping, remaskt deterministisch)
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

    if not find_occurrences(src, val):
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

    masked_text, used_mapping = mask_with_mapping(src, candidate_map)

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
    ctx.editing_keys.clear()
    _sync_ctx_token_state(ctx, used_mapping)
    _rebuild_token_ui(ctx, used_mapping)
    update_banner(ctx, used_mapping)

    ctx.manual_token_text.value = ""
    update_add_button_state(ctx)
    ctx.page.update()



# Wendet aktuell editierte Tokens auf den Input an und setzt Output + Store-State konsistent
def apply_current_edits(ctx: DashboardContext) -> None:
    src = ctx.input_field.value or ""
    if not src:
        ctx.output_field.value = ""
        ctx.store.set_dash(output_text="", status_text=ctx.results_text.value or "")
        ctx.sync_equal_height()
        ctx.page.update()
        return

    if not ctx.token_vals:
        ctx.output_field.value = src
        ctx.store.set_dash(output_text=src, status_text=ctx.results_text.value or "")
        ctx.sync_equal_height()
        ctx.page.update()
        return

    edits = {k: (ctx.token_vals.get(k, "") or "") for k in ctx.token_keys_order if k in ctx.token_vals}
    for k, v in edits.items():
        if not v:
            continue
        if not find_occurrences(src, v):
            msg = (
                f"'{k}' nicht (mehr) als eigenständiger Treffer im Text gefunden. Prüfe die Werte."
                if ctx.lang == "de"
                else f"'{k}' no longer found as a standalone match in text. Please check the values."
            )
            show_snack(ctx, msg, "warning")
            return

    masked_text, used_mapping = mask_with_mapping(src, edits)

    ctx.output_field.value = masked_text

    hits = list(getattr(ctx.store, "last_hits", []) or [])
    ctx.store.set_mapping(used_mapping, hits, src, masked_text)
    _push_mapping_into_session(ctx, used_mapping)
    update_banner(ctx, used_mapping)

    ctx.editing_keys.clear()
    _sync_ctx_token_state(ctx, used_mapping)
    if used_mapping:
        _rebuild_token_ui(ctx, used_mapping)
    else:
        ctx.token_groups_col.controls.clear()
        ctx.tokens_host.visible = False

    ctx.sync_equal_height()
    ctx.page.update()



# Führt Masking über Service aus, merged Session-Mapping, setzt UI/Store-State (auto/manual)
def run_masking_internal(ctx: DashboardContext, auto: bool = False) -> None:
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
                ctx.sync_equal_height()
                ctx.page.update()
                return
            msg = t(ctx.lang, "status.no_input")
            show_snack(ctx, msg, "warning")
            return

        try:
            _, base_mapping, hits = anonymize(text, reversible=getattr(ctx.store, "reversible", True))
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
                if not find_occurrences(text, value):
                    continue
                if token in merged_mapping and merged_mapping[token] == value:
                    continue
                merged_mapping[token] = value

        masked_text, used_mapping = mask_with_mapping(text, merged_mapping)

        ctx.output_field.value = masked_text
        ctx.sync_equal_height()
        ctx.store.set_mapping(used_mapping, hits, text, masked_text)

        if getattr(ctx.store, "reversible", True) and used_mapping:
            if hasattr(ctx.store, "add_session_mapping"):
                ctx.store.add_session_mapping(used_mapping)

        ctx.tokens_section.visible = True
        ctx.editing_keys.clear()
        _sync_ctx_token_state(ctx, used_mapping)

        if used_mapping:
            _rebuild_token_ui(ctx, used_mapping)
        else:
            ctx.token_groups_col.controls.clear()
            ctx.tokens_host.visible = False

        update_banner(ctx, used_mapping)
        ctx.page.update()
    finally:
        if ctx.on_masking_state is not None:
            try:
                ctx.on_masking_state(False)
            except Exception:
                pass



# Bricht einen laufenden Debounce-Timer ab (wenn vorhanden)
def _cancel_debounce(ctx: DashboardContext) -> None:
    if ctx.debounce_timer is not None:
        try:
            ctx.debounce_timer.cancel()
        except Exception:
            pass
        ctx.debounce_timer = None



# Hard-Reset: Input/Output/Token-UI/Store-State + schließt aktive Session
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



# Reagiert auf Input-Änderungen: persistiert Draft, optional Auto-Mask mit Debounce
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