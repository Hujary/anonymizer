from __future__ import annotations

import flet as ft
from detectors.ner.ner_core import set_spacy_model, get_current_model
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

    NER_TYPES = ["PER", "ORG", "LOC", "GPE", "DATE", "TIME", "MONEY", "PERCENT", "PRODUCT", "EVENT", "MISC"]
    NER_RECOMMENDED = ["PER", "ORG", "LOC", "GPE"]

    LABELS_DE = {
        "PER": "Person (PER)",
        "ORG": "Organisation (ORG)",
        "LOC": "Ort (LOC)",
        "GPE": "Staat/Gebiet (GPE)",
        "DATE": "Datum (DATE)",
        "TIME": "Uhrzeit (TIME)",
        "MONEY": "Geldbetrag (MONEY)",
        "PERCENT": "Prozentangabe (PERCENT)",
        "PRODUCT": "Produktname (PRODUCT)",
        "EVENT": "Ereignis (EVENT)",
        "MISC": "Sonstiges (MISC)",
    }
    LABELS_EN = {
        "PER": "Person name (PER)",
        "ORG": "Organization or company (ORG)",
        "LOC": "Physical location (LOC)",
        "GPE": "Country or region (GPE)",
        "DATE": "Date (DATE)",
        "TIME": "Time expression (TIME)",
        "MONEY": "Monetary amount (MONEY)",
        "PERCENT": "Percentage (PERCENT)",
        "PRODUCT": "Product name (PRODUCT)",
        "EVENT": "Event or occasion (EVENT)",
        "MISC": "Miscellaneous / other (MISC)",
    }

    REGEX_TYPES = ["E_MAIL", "TELEFON", "IBAN", "BIC", "URL", "USTID", "RECHNUNGS_NUMMER", "PLZ", "DATUM", "BETRAG"]
    RX_RECOMMENDED = list(REGEX_TYPES)

    R_LABELS_DE = {
        "E_MAIL": "E-Mail",
        "TELEFON": "Telefon",
        "IBAN": "IBAN",
        "BIC": "BIC",
        "URL": "URL",
        "USTID": "USt-ID",
        "RECHNUNGS_NUMMER": "Rechnungsnummer",
        "PLZ": "PLZ",
        "DATUM": "Datum",
        "BETRAG": "Geldbetrag",
    }
    R_LABELS_EN = {
        "E_MAIL": "Email",
        "TELEFON": "Phone",
        "IBAN": "IBAN",
        "BIC": "BIC",
        "URL": "URL",
        "USTID": "VAT ID",
        "RECHNUNGS_NUMMER": "Invoice no.",
        "PLZ": "ZIP",
        "DATUM": "Date",
        "BETRAG": "Amount",
    }

    def label_for(code: str, lng: str) -> str:
        return (LABELS_DE if lng == "de" else LABELS_EN).get(code, code)

    def rlabel_for(code: str, lng: str) -> str:
        return (R_LABELS_DE if lng == "de" else R_LABELS_EN).get(code, code)

    selected_ner: set[str] = set(
        config.get(
            "ner_labels",
            ["PER", "ORG", "LOC", "GPE", "DATE", "TIME", "MONEY", "PERCENT", "PRODUCT", "EVENT"],
        )
    )
    selected_rx: set[str] = set(config.get("regex_labels", REGEX_TYPES))

    saved_label = ft.Text(
        f"{t(lang, 'loaded')}: {config.get('spacy_model', '') or '-'}",
        size=12,
        color=theme["text_secondary"],
    )

    def _persist_flags_and_labels():
        use_regex = bool(selected_rx)
        use_ner = bool(selected_ner) and bool(installed_keys)
        current_flags = config.get_flags()
        config.set_flags(
            use_regex=use_regex,
            use_ner=use_ner,
            debug_mask=current_flags.get("debug_mask", False),
        )
        config.set("ner_labels", sorted(selected_ner))
        config.set("regex_labels", sorted(selected_rx))

    allowed = {x.upper() for x in (list(selected_rx) + list(selected_ner)) if isinstance(x, str) and x.strip()}

    if store is not None and hasattr(store, "session_mgr") and store.session_mgr is not None:
        store.session_mgr.prune_active_mapping_by_allowed_labels(allowed)

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
            _notify_saved(("Gespeichert" if cur_lang == "de" else "Saved"))
            page.update()

        dd.on_change = on_model_change
        return dd

    lang_host = ft.Container(content=make_lang_dropdown(lang), width=260)
    model_control = make_model_dropdown(lang, current_key)

    model_host = ft.Container(
        content=ft.Column([model_control, saved_label], spacing=6),
        width=420,
    )

    divider_color = theme.get("divider", theme.get("surface_muted"))

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
        _persist_flags_and_labels()
        _notify_saved(("Gespeichert" if lang == "de" else "Saved"))

    build_two_col_checkboxes(NER_TYPES, label_for, selected_ner, ner_col_left, ner_col_right, ner_cb_by_code, lang, _on_any_settings_change)
    build_two_col_checkboxes(REGEX_TYPES, rlabel_for, selected_rx, rx_col_left, rx_col_right, rx_cb_by_code, lang, _on_any_settings_change)

    def ner_select_all(_):
        selected_ner.clear()
        selected_ner.update(NER_TYPES)
        for cb in ner_cb_by_code.values():
            cb.value = True
        _on_any_settings_change()
        page.update()

    def ner_select_none(_):
        selected_ner.clear()
        for cb in ner_cb_by_code.values():
            cb.value = False
        _on_any_settings_change()
        page.update()

    def ner_select_recommended(_):
        selected_ner.clear()
        selected_ner.update(NER_RECOMMENDED)
        for code, cb in ner_cb_by_code.items():
            cb.value = code in selected_ner
        _on_any_settings_change()
        page.update()

    def rx_select_all(_):
        selected_rx.clear()
        selected_rx.update(REGEX_TYPES)
        for cb in rx_cb_by_code.values():
            cb.value = True
        _on_any_settings_change()
        page.update()

    def rx_select_none(_):
        selected_rx.clear()
        for cb in rx_cb_by_code.values():
            cb.value = False
        _on_any_settings_change()
        page.update()

    def rx_select_recommended(_):
        selected_rx.clear()
        selected_rx.update(RX_RECOMMENDED)
        for code, cb in rx_cb_by_code.items():
            cb.value = code in selected_rx
        _on_any_settings_change()
        page.update()

    top_bar = ft.Container(
        padding=ft.padding.symmetric(16, 16),
        content=ft.Column(
            [
                ft.Row(
                    [
                        lang_host,
                        ft.Container(width=20),
                        model_host,
                        ft.Container(width=40),
                        theme_switch,
                    ],
                    alignment=ft.MainAxisAlignment.START,
                    vertical_alignment=ft.CrossAxisAlignment.START,
                ),
            ],
            spacing=12,
        ),
    )

    sections = ft.ListView(spacing=16, padding=0, expand=True, auto_scroll=False)
    sections.controls.append(top_bar)
    sections.controls.append(ft.Divider(height=24, color=divider_color))

    sections.controls.append(
        ft.Row(
            [
                ft.Text("NER-Typen", weight=ft.FontWeight.W_600, color=theme["text_secondary"]),
                ft.Container(expand=True),
                ft.TextButton(t(lang, "settings.recommended"), on_click=ner_select_recommended),
                ft.TextButton(t(lang, "settings.all"), on_click=ner_select_all),
                ft.TextButton(t(lang, "settings.none"), on_click=ner_select_none),
            ],
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )
    )
    sections.controls.append(
        ft.Row(
            [ft.Container(ner_col_left, expand=1), ft.Container(ner_col_right, expand=1)],
            spacing=24,
        )
    )

    sections.controls.append(ft.Divider(height=24, color=divider_color))

    sections.controls.append(
        ft.Row(
            [
                ft.Text("Regex-Typen", weight=ft.FontWeight.W_600, color=theme["text_secondary"]),
                ft.Container(expand=True),
                ft.TextButton(t(lang, "settings.recommended"), on_click=rx_select_recommended),
                ft.TextButton(t(lang, "settings.all"), on_click=rx_select_all),
                ft.TextButton(t(lang, "settings.none"), on_click=rx_select_none),
            ],
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )
    )
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
        content=ft.Column([ft.Container(sections, expand=True)], spacing=12, expand=True),
    )
