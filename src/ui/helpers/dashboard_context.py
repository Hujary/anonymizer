from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Callable, Optional
import threading

import flet as ft


AUTO_MASK_DEBOUNCE_SECONDS = 0.3


@dataclass
class OccurrenceRow:
    row_id: str
    token: str
    label: str
    value: str
    original_value: str
    start: int
    ende: int
    source: str
    source_label: str
    validation_source: Optional[str] = None
    validation_status: Optional[str] = None
    validation_score: Optional[float] = None
    validation_threshold: Optional[float] = None
    validation_reason: Optional[str] = None
    enabled: bool = True


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

    occurrence_rows: List[OccurrenceRow] = field(default_factory=list)
    editing_row_ids: set[str] = field(default_factory=set)

    debounce_timer: threading.Timer | None = None

    on_masking_state: Optional[Callable[[bool], None]] = None
    on_masking_phase: Optional[Callable[[str], None]] = None

    masking_lock: threading.Lock = field(default_factory=threading.Lock)
    masking_in_progress: bool = False