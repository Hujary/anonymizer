from __future__ import annotations

from typing import List

from core import config
from core.typen import Treffer
from validation.registry import get_postcode_validator


def _get_manual_threshold_override() -> float | None:
    enabled = bool(config.get("postcode_manual_threshold_enabled", False))
    if not enabled:
        return None

    raw_value = config.get("postcode_manual_threshold", None)
    if raw_value is None:
        return None

    try:
        value = float(raw_value)
    except Exception:
        return None

    if value < 0.0:
        value = 0.0
    if value > 1.0:
        value = 1.0

    return value


def validate_regex_hits(text: str, hits: List[Treffer]) -> List[Treffer]:
    if not hits:
        return []

    use_postcode_ml_validator = bool(config.get("use_postcode_ml_validator", True))
    if not use_postcode_ml_validator:
        return hits

    out: List[Treffer] = []
    postcode_validator = None
    threshold_override = _get_manual_threshold_override()

    for hit in hits:
        if hit.label != "PLZ":
            out.append(hit)
            continue

        if postcode_validator is None:
            postcode_validator = get_postcode_validator()

        candidate = text[hit.start:hit.ende]

        try:
            decision = postcode_validator.validate(
                text,
                candidate,
                start=hit.start,
                end=hit.ende,
                threshold_override=threshold_override,
            )
            out.append(
                hit.with_validation(
                    source=decision.validator_name,
                    status=decision.status,
                    score=decision.score,
                    threshold=decision.threshold,
                    reason=decision.reason,
                    raw_score=decision.raw_score,
                    adjustment=decision.adjustment,
                )
            )
        except Exception as e:
            out.append(
                hit.with_validation(
                    source="postcode_ml",
                    status="error",
                    score=None,
                    threshold=None,
                    reason=str(e),
                    raw_score=None,
                    adjustment=None,
                )
            )

    return out


def filter_effective_hits_for_masking(hits: List[Treffer]) -> List[Treffer]:
    if not hits:
        return []

    out: List[Treffer] = []

    for hit in hits:
        if hit.label == "PLZ" and hit.validation_source == "postcode_ml":
            if hit.validation_status != "accepted":
                continue
        out.append(hit)

    return out