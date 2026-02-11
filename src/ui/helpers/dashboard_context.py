from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Callable, Optional
import threading

import flet as ft


AUTO_MASK_DEBOUNCE_SECONDS = 0.3


# Zentrales Kontext-Objekt: bündelt Page/Theme/Store + Controls + lokaler UI-State.
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

    # token -> originaler Wert
    token_vals: Dict[str, str] = field(default_factory=dict)
    # stabile Reihenfolge für UI + Persistenz
    token_keys_order: List[str] = field(default_factory=list)

    # Tokens, die im Inline-Edit-Modus sind
    editing_keys: set[str] = field(default_factory=set)

    # Debounce-Timer für Auto-Mask
    debounce_timer: threading.Timer | None = None

    # Optionaler Callback zum Sperren/Entsperren der UI während Maskierung
    on_masking_state: Optional[Callable[[bool], None]] = None