from __future__ import annotations

import flet as ft
from detectors.ner.ner_core import get_current_model, set_spacy_model
from ui.style.translations import t
from core import config


def view(
    page: ft.Page,
    theme_name: str,
    on_toggle_theme,
    theme: dict,
    on_lang_changed=None,
    store=None,
) -> ft.Control:
    lang = config.get("lang", "de")
    if lang not in ("de", "en"):
        lang = "de"

    model_map = {"fast": "de_core_news_md", "large": "de_core_news_lg"}

    def _installed_models() -> list[tuple[str, str]]:
        try:
            from spacy.util import is_package
        except Exception:
            return []

        out: list[tuple[str, str]] = []
        fast = model_map["fast"]
        large = model_map["large"]

        try:
            if is_package(fast):
                out.append(("fast", fast))
        except Exception:
            pass

        try:
            if is_package(large):
                out.append(("large", large))
        except Exception:
            pass

        return out

    installed = _installed_models()
    installed_keys = [k for k, _ in installed]

    cfg_model = config.get("spacy_model", None)
    cfg_model = cfg_model.strip() if isinstance(cfg_model, str) else ""
    runtime_current_model = get_current_model()
    runtime_current_model = str(runtime_current_model) if runtime_current_model else ""

    current_model_name = runtime_current_model or cfg_model
    if current_model_name in model_map.values():
        current_key = "large" if current_model_name.endswith("_lg") else "fast"
    else:
        current_key = "large"

    if installed_keys:
        if current_key not in installed_keys:
            current_key = installed_keys[0]
        current_model = model_map[current_key]
        config.set("spacy_model", current_model)
    else:
        config.set("spacy_model", "")

    def ner_options(for_lang: str) -> list[ft.dropdown.Option]:
        opts: list[ft.dropdown.Option] = []
        for key in installed_keys:
            label = t(for_lang, "ner_model.fast") if key == "fast" else t(for_lang, "ner_model.large")
            opts.append(ft.dropdown.Option(key=key, text=label))
        return opts

    model_ref = ft.Ref[ft.Dropdown]()
    lang_ref = ft.Ref[ft.Dropdown]()

    NER_UI_TYPES = ["PER", "ORG", "LOC", "STRASSE"]
    NER_MINIMAL = {"PER", "STRASSE"}

    LABELS_DE = {
        "PER": "Person (PER)",
        "ORG": "Organisation (ORG)",
        "LOC": "Ort / Ortseinheit (LOC)",
        "STRASSE": "Straße / Hausnummer (STRASSE)",
    }

    LABELS_EN = {
        "PER": "Person (PER)",
        "ORG": "Organization (ORG)",
        "LOC": "Location / place entity (LOC)",
        "STRASSE": "Street / house number (STRASSE)",
    }

    REGEX_TYPES = ["E_MAIL", "TELEFON", "IBAN", "URL", "PLZ", "STRASSE", "DATUM", "IP_ADRESSE"]
    RX_MINIMAL = {"E_MAIL", "TELEFON", "IBAN", "IP_ADRESSE", "STRASSE"}

    R_LABELS_DE = {
        "E_MAIL": "E-Mail",
        "TELEFON": "Telefon",
        "IBAN": "IBAN",
        "URL": "URL",
        "PLZ": "Postleitzahl (PLZ)",
        "STRASSE": "Straße / Hausnummer (STRASSE)",
        "DATUM": "Datum",
        "IP_ADRESSE": "IP-Adresse",
    }

    R_LABELS_EN = {
        "E_MAIL": "Email",
        "TELEFON": "Phone",
        "IBAN": "IBAN",
        "URL": "URL",
        "PLZ": "Postal code (PLZ)",
        "STRASSE": "Street / house number (STRASSE)",
        "DATUM": "Date",
        "IP_ADRESSE": "IP address",
    }

    def label_for(code: str, lng: str) -> str:
        return (LABELS_DE if lng == "de" else LABELS_EN).get(code, code)

    def rlabel_for(code: str, lng: str) -> str:
        return (R_LABELS_DE if lng == "de" else R_LABELS_EN).get(code, code)

    selected_ner: set[str] = set(config.get("ner_labels", list(NER_UI_TYPES)))
    selected_rx: set[str] = set(config.get("regex_labels", REGEX_TYPES))

    selected_ner = {x.upper() for x in selected_ner if isinstance(x, str)}
    selected_rx = {x.upper() for x in selected_rx if isinstance(x, str)}

    selected_ner.intersection_update(set(NER_UI_TYPES))
    selected_rx.intersection_update(set(REGEX_TYPES))

    divider_color = theme.get("divider", theme.get("surface_muted"))

    saved_label = ft.Text(
        f"{t(lang, 'loaded')}: {config.get('spacy_model', '') or '-'}",
        size=12,
        color=theme["text_secondary"],
    )

    def _prune_mapping():
        allowed = {x.upper() for x in (list(selected_rx) + list(selected_ner)) if isinstance(x, str) and x.strip()}
        if store is not None and hasattr(store, "session_mgr") and store.session_mgr is not None:
            store.session_mgr.prune_active_mapping_by_allowed_labels(allowed)

    def _persist_flags_and_labels():
        use_regex = bool(selected_rx)
        use_ner = bool(selected_ner) and bool(installed_keys)
        current_flags = config.get_flags()
        config.set_flags(
            use_regex=use_regex,
            use_ner=use_ner,
            debug_mask=current_flags.get("debug_mask", False),
        )
        config.set("ner_labels", sorted(set(selected_ner).intersection(set(NER_UI_TYPES))))
        config.set("regex_labels", sorted(set(selected_rx).intersection(set(REGEX_TYPES))))
        _prune_mapping()

    def _notify_saved(msg: str):
        page.snack_bar = ft.SnackBar(ft.Text(msg), bgcolor=theme["success"])
        page.snack_bar.open = True
        page.update()

    def handle_lang_change(e: ft.ControlEvent):
        new_lang = e.control.value or "de"
        config.set("lang", new_lang)
        if on_lang_changed:
            on_lang_changed(new_lang)

    def make_lang_dropdown(cur_lang: str) -> ft.Dropdown:
        return ft.Dropdown(
            ref=lang_ref,
            label=t(cur_lang, "language"),
            options=[
                ft.dropdown.Option(text=t(cur_lang, "lang.de"), key="de"),
                ft.dropdown.Option(text=t(cur_lang, "lang.en"), key="en"),
            ],
            value=cur_lang,
            width=260,
            on_change=handle_lang_change,
        )

    theme_switch = ft.Switch(label=t(lang, "dark_mode"), value=(theme_name == "dark"))

    def toggle_theme(_):
        on_toggle_theme("dark" if theme_switch.value else "light")

    theme_switch.on_change = toggle_theme

    ner_post_switch = ft.Switch(
        label=t(lang, "ner_postprocessing"),
        value=bool(config.get("use_ner_postprocessing", False)),
    )

    def toggle_ner_postprocessing(e: ft.ControlEvent):
        config.set("use_ner_postprocessing", bool(e.control.value))
        _notify_saved("Gespeichert" if lang == "de" else "Saved")

    ner_post_switch.on_change = toggle_ner_postprocessing

    copy_ai_prompt_switch = ft.Switch(
        label=("KI Prompt Ergänzung bei Kopieren" if lang == "de" else "Add AI prompt when copying"),
        value=bool(config.get("copy_ai_prompt_enabled", False)),
    )

    def toggle_copy_ai_prompt(e: ft.ControlEvent):
        config.set("copy_ai_prompt_enabled", bool(e.control.value))
        _notify_saved("Gespeichert" if lang == "de" else "Saved")

    copy_ai_prompt_switch.on_change = toggle_copy_ai_prompt

    def make_model_dropdown(cur_lang: str, value_key: str) -> ft.Control:
        if not installed_keys:
            return ft.Container(
                content=ft.Text(
                    "Kein spaCy-NER-Modell installiert (pip install de_core_news_md oder de_core_news_lg)"
                    if cur_lang == "de"
                    else "No spaCy NER model installed (pip install de_core_news_md or de_core_news_lg)",
                    size=12,
                    color=theme["text_secondary"],
                ),
                width=420,
            )

        dd = ft.Dropdown(
            ref=model_ref,
            label=t(cur_lang, "ner_model"),
            options=ner_options(cur_lang),
            value=value_key,
            width=420,
        )

        def on_model_change(e: ft.ControlEvent):
            key = e.control.value
            if not key or key not in installed_keys:
                return

            target = model_map.get(key, model_map["large"])

            try:
                eff = set_spacy_model(target)
            except Exception as ex:
                page.snack_bar = ft.SnackBar(
                    ft.Text(
                        f"NER-Modell konnte nicht geladen werden: {ex}"
                        if cur_lang == "de"
                        else f"Failed to load NER model: {ex}"
                    ),
                    bgcolor=theme.get("danger", ft.Colors.RED),
                )
                page.snack_bar.open = True
                page.update()
                return

            config.set("spacy_model", eff)
            saved_label.value = f"{t(cur_lang, 'loaded')}: {eff}"
            _persist_flags_and_labels()
            _notify_saved("Gespeichert" if cur_lang == "de" else "Saved")
            page.update()

        dd.on_change = on_model_change
        return dd

    lang_host = ft.Container(content=make_lang_dropdown(lang), width=260)
    model_control = make_model_dropdown(lang, current_key)

    model_host = ft.Container(
        content=ft.Column([model_control, saved_label], spacing=6),
        width=420,
    )

    ner_col_left = ft.Column(spacing=6)
    ner_col_right = ft.Column(spacing=6)
    ner_cb_by_code: dict[str, ft.Checkbox] = {}

    rx_col_left = ft.Column(spacing=6)
    rx_col_right = ft.Column(spacing=6)
    rx_cb_by_code: dict[str, ft.Checkbox] = {}

    def build_two_col_checkboxes(
        codes: list[str],
        label_func,
        selected: set[str],
        col_left: ft.Column,
        col_right: ft.Column,
        store_dict: dict[str, ft.Checkbox],
        lang_code: str,
        on_any_change,
        clamp_allowed: set[str] | None = None,
    ):
        col_left.controls = []
        col_right.controls = []
        store_dict.clear()

        half = (len(codes) + 1) // 2
        left_codes = codes[:half]
        right_codes = codes[half:]

        def make_cb(code: str) -> ft.Checkbox:
            def _changed(e: ft.ControlEvent):
                if e.control.value:
                    selected.add(code)
                else:
                    selected.discard(code)

                if clamp_allowed is not None:
                    selected.intersection_update(clamp_allowed)

                on_any_change()

            return ft.Checkbox(
                label=label_func(code, lang_code),
                value=(code in selected),
                on_change=_changed,
            )

        for code in left_codes:
            cb = make_cb(code)
            store_dict[code] = cb
            col_left.controls.append(cb)

        for code in right_codes:
            cb = make_cb(code)
            store_dict[code] = cb
            col_right.controls.append(cb)

    def _on_any_settings_change():
        selected_ner.intersection_update(set(NER_UI_TYPES))
        selected_rx.intersection_update(set(REGEX_TYPES))
        _persist_flags_and_labels()
        _notify_saved("Gespeichert" if lang == "de" else "Saved")

    build_two_col_checkboxes(
        NER_UI_TYPES,
        label_for,
        selected_ner,
        ner_col_left,
        ner_col_right,
        ner_cb_by_code,
        lang,
        _on_any_settings_change,
        clamp_allowed=set(NER_UI_TYPES),
    )

    build_two_col_checkboxes(
        REGEX_TYPES,
        rlabel_for,
        selected_rx,
        rx_col_left,
        rx_col_right,
        rx_cb_by_code,
        lang,
        _on_any_settings_change,
        clamp_allowed=set(REGEX_TYPES),
    )

    def ner_select_all(_):
        selected_ner.clear()
        selected_ner.update(NER_UI_TYPES)
        for code, cb in ner_cb_by_code.items():
            cb.value = code in selected_ner
        _on_any_settings_change()
        page.update()

    def ner_select_minimal(_):
        selected_ner.clear()
        selected_ner.update(NER_MINIMAL)
        selected_ner.intersection_update(set(NER_UI_TYPES))
        for code, cb in ner_cb_by_code.items():
            cb.value = code in selected_ner
        _on_any_settings_change()
        page.update()

    def ner_select_none(_):
        selected_ner.clear()
        for cb in ner_cb_by_code.values():
            cb.value = False
        _on_any_settings_change()
        page.update()

    def rx_select_all(_):
        selected_rx.clear()
        selected_rx.update(REGEX_TYPES)
        for cb in rx_cb_by_code.values():
            cb.value = True
        _on_any_settings_change()
        page.update()

    def rx_select_minimal(_):
        selected_rx.clear()
        selected_rx.update(RX_MINIMAL)
        selected_rx.intersection_update(set(REGEX_TYPES))
        for code, cb in rx_cb_by_code.items():
            cb.value = code in selected_rx
        _on_any_settings_change()
        page.update()

    def rx_select_none(_):
        selected_rx.clear()
        for cb in rx_cb_by_code.values():
            cb.value = False
        _on_any_settings_change()
        page.update()

    def section_divider() -> ft.Control:
        return ft.Divider(height=1, thickness=1, color=divider_color)

    sections = ft.ListView(spacing=0, padding=0, expand=True, auto_scroll=False)

    sections.controls.append(
        ft.Row(
            [
                lang_host,
                ft.Container(width=20),
                model_host,
            ],
            alignment=ft.MainAxisAlignment.START,
            vertical_alignment=ft.CrossAxisAlignment.START,
        )
    )

    sections.controls.append(ft.Container(height=16))
    sections.controls.append(section_divider())
    sections.controls.append(ft.Container(height=16))

    sections.controls.append(
        ft.Row(
            [
                ft.Text(
                    "Allgemeine Einstellungen" if lang == "de" else "General settings",
                    weight=ft.FontWeight.W_600,
                    color=theme["text_secondary"],
                ),
                ft.Container(expand=True),
            ],
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )
    )

    sections.controls.append(ft.Container(height=10))

    sections.controls.append(
        ft.Row(
            [
                theme_switch,
                ft.Container(width=32),
                ner_post_switch,
                ft.Container(width=32),
                copy_ai_prompt_switch,
            ],
            alignment=ft.MainAxisAlignment.START,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )
    )

    sections.controls.append(ft.Container(height=16))
    sections.controls.append(section_divider())
    sections.controls.append(ft.Container(height=16))

    sections.controls.append(
        ft.Row(
            [
                ft.Text("NER-basiert", weight=ft.FontWeight.W_600, color=theme["text_secondary"]),
                ft.Container(expand=True),
                ft.TextButton(t(lang, "settings.all"), on_click=ner_select_all),
                ft.TextButton("Minimal" if lang == "de" else "Minimal", on_click=ner_select_minimal),
                ft.TextButton(t(lang, "settings.none"), on_click=ner_select_none),
            ],
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )
    )

    sections.controls.append(ft.Container(height=10))
    sections.controls.append(
        ft.Row(
            [ft.Container(ner_col_left, expand=1), ft.Container(ner_col_right, expand=1)],
            spacing=24,
        )
    )

    sections.controls.append(ft.Container(height=16))
    sections.controls.append(section_divider())
    sections.controls.append(ft.Container(height=16))

    sections.controls.append(
        ft.Row(
            [
                ft.Text("Regex-basiert", weight=ft.FontWeight.W_600, color=theme["text_secondary"]),
                ft.Container(expand=True),
                ft.TextButton(t(lang, "settings.all"), on_click=rx_select_all),
                ft.TextButton("Minimal" if lang == "de" else "Minimal", on_click=rx_select_minimal),
                ft.TextButton(t(lang, "settings.none"), on_click=rx_select_none),
            ],
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )
    )

    sections.controls.append(ft.Container(height=10))
    sections.controls.append(
        ft.Row(
            [ft.Container(rx_col_left, expand=1), ft.Container(rx_col_right, expand=1)],
            spacing=24,
        )
    )

    return ft.Container(
        padding=24,
        expand=True,
        bgcolor=theme["background"],
        content=sections,
    )