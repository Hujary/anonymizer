from __future__ import annotations

import flet as ft
from detectors.ner.ner_core import set_spacy_model, get_current_model
from ui.style.components import pill_button, pill_switch
from core import config
from ui.style.translations import t


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
    current_model = get_current_model() or model_map["large"]
    current_key = "large" if str(current_model).endswith("_lg") else "fast"

    def ner_options(for_lang: str) -> list[ft.dropdown.Option]:
        return [
            ft.dropdown.Option(key="fast", text=t(for_lang, "ner_model.fast")),
            ft.dropdown.Option(key="large", text=t(for_lang, "ner_model.large")),
        ]

    title_text = ft.Text(
        t(lang, "settings.title"),
        size=22,
        weight=ft.FontWeight.W_700,
        color=theme["text_primary"],
    )

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

    reversible_initial = config.get("reversible_masking", True)
    auto_mask_initial = config.get("auto_mask_enabled", True)
    auto_demask_initial = config.get("auto_demask_enabled", True)

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

    def make_model_dropdown(cur_lang: str, value_key: str) -> ft.Dropdown:
        return ft.Dropdown(
            ref=model_ref,
            label=t(cur_lang, "ner_model"),
            options=ner_options(cur_lang),
            value=value_key,
            width=420,
        )

    lang_host = ft.Container(content=make_lang_dropdown(lang), width=260)
    model_dropdown = make_model_dropdown(lang, current_key)
    saved_label = ft.Text(f"{t(lang, 'loaded')}: {current_model}", size=12, color=theme["text_secondary"])
    model_host = ft.Container(content=ft.Column([model_dropdown, saved_label], spacing=6), width=420)

    theme_switch = ft.Switch(label=t(lang, "dark_mode"), value=(theme_name == "dark"))

    def toggle_theme(_):
        on_toggle_theme("dark" if theme_switch.value else "light")

    theme_switch.on_change = toggle_theme

    def on_reversible_changed(value: bool):
        config.set("reversible_masking", bool(value))
        if store is not None:
            setattr(store, "reversible", bool(value))

    def on_auto_mask_changed(value: bool):
        config.set("auto_mask_enabled", bool(value))
        if store is not None:
            setattr(store, "auto_mask_enabled", bool(value))

    def on_auto_demask_changed(value: bool):
        config.set("auto_demask_enabled", bool(value))
        if store is not None:
            setattr(store, "auto_demask_enabled", bool(value))

    masking_switches_row = ft.Row(
        [
            pill_switch(
                t(lang, "reversible"),
                reversible_initial,
                on_reversible_changed,
                theme,
                scale=1.05,
            ),
            pill_switch(
                "Automatisch maskieren" if lang == "de" else "Auto mask",
                auto_mask_initial,
                on_auto_mask_changed,
                theme,
                scale=1.05,
            ),
            pill_switch(
                t(lang, "vault.live_demask"),
                auto_demask_initial,
                on_auto_demask_changed,
                theme,
                scale=1.05,
            ),
        ],
        spacing=12,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )

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
                ft.Container(height=16),
                masking_switches_row,
            ],
            spacing=12,
        ),
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
    ):
        col_left.controls = []
        col_right.controls = []
        store_dict.clear()
        half = (len(codes) + 1) // 2
        left_codes = codes[:half]
        right_codes = codes[half:]

        def make_cb(code: str) -> ft.Checkbox:
            return ft.Checkbox(
                label=label_func(code, lang_code),
                value=(code in selected),
                on_change=lambda e, c=code: (selected.add(c) if e.control.value else selected.discard(c)),
            )

        for code in left_codes:
            cb = make_cb(code)
            store_dict[code] = cb
            col_left.controls.append(cb)

        for code in right_codes:
            cb = make_cb(code)
            store_dict[code] = cb
            col_right.controls.append(cb)

    build_two_col_checkboxes(NER_TYPES, label_for, selected_ner, ner_col_left, ner_col_right, ner_cb_by_code, lang)
    build_two_col_checkboxes(REGEX_TYPES, rlabel_for, selected_rx, rx_col_left, rx_col_right, rx_cb_by_code, lang)

    def ner_select_all(_):
        selected_ner.clear()
        selected_ner.update(NER_TYPES)
        for cb in ner_cb_by_code.values():
            cb.value = True
        page.update()

    def ner_select_none(_):
        selected_ner.clear()
        for cb in ner_cb_by_code.values():
            cb.value = False
        page.update()

    def ner_select_recommended(_):
        selected_ner.clear()
        selected_ner.update(NER_RECOMMENDED)
        for code, cb in ner_cb_by_code.items():
            cb.value = code in selected_ner
        page.update()

    def rx_select_all(_):
        selected_rx.clear()
        selected_rx.update(REGEX_TYPES)
        for cb in rx_cb_by_code.values():
            cb.value = True
        page.update()

    def rx_select_none(_):
        selected_rx.clear()
        for cb in rx_cb_by_code.values():
            cb.value = False
        page.update()

    def rx_select_recommended(_):
        selected_rx.clear()
        selected_rx.update(RX_RECOMMENDED)
        for code, cb in rx_cb_by_code.items():
            cb.value = code in selected_rx
        page.update()

    save_btn = pill_button(t(lang, "save"), icon=ft.Icons.SAVE_OUTLINED, on_click=None, theme=theme)

    def save_flags(_):
        use_regex = bool(selected_rx)
        use_ner = bool(selected_ner)
        current_flags = config.get_flags()
        config.set_flags(
            use_regex=use_regex,
            use_ner=use_ner,
            debug_mask=current_flags.get("debug_mask", False),
        )
        config.set("ner_labels", sorted(selected_ner))
        config.set("regex_labels", sorted(selected_rx))
        key = model_ref.current.value if model_ref.current else current_key
        target = model_map.get(key, model_map["large"])
        eff = set_spacy_model(target)
        config.set("spacy_model", eff)
        page.snack_bar = ft.SnackBar(ft.Text(f"Gespeichert – Modell: {eff}"), bgcolor=theme["success"])
        page.snack_bar.open = True
        page.update()

    save_btn.on_click = save_flags

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

    sections.controls.append(ft.Container(height=8))
    sections.controls.append(ft.Row([save_btn], spacing=10))

    return ft.Container(
        padding=24,
        expand=True,
        bgcolor=theme["background"],
        content=ft.Column(
            [ft.Container(sections, expand=True)],
            spacing=12,
            expand=True,
        ),
    )