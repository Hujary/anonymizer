from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class ValidationDecision:
    validator_name: str
    label: str
    candidate: str
    accepted: bool
    score: float
    threshold: float
    reason: str
    raw_score: float
    adjustment: float
    reference_hit: Optional[bool] = None

    context_text: Optional[str] = None
    model_input: Optional[str] = None
    context_start: Optional[int] = None
    context_end: Optional[int] = None

    @property
    def status(self) -> str:
        return "accepted" if self.accepted else "declined"