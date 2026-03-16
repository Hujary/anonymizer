from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from core import config
from pipeline.anonymisieren import erkenne


POLICY_SPECS: Dict[str, Dict[str, List[str]]] = {
    "minimal": {
        "ner_labels": ["PER", "STRASSE"],
        "regex_labels": ["E_MAIL", "TELEFON", "IBAN", "IP_ADRESSE", "STRASSE"],
    },
    "secure": {
        "ner_labels": ["PER", "ORG", "LOC", "STRASSE"],
        "regex_labels": ["DATUM", "E_MAIL", "IBAN", "IP_ADRESSE", "PLZ", "STRASSE", "TELEFON", "URL"],
    },
}


@dataclass(frozen=True)
class Span:
    start: int
    end: int
    label: str
    source: str

    def key(self) -> Tuple[int, int, str]:
        return (self.start, self.end, self.label)


@dataclass(frozen=True)
class GoldCandidate:
    start: int
    end: int
    text: str
    expected_sources: Set[str]


@dataclass(frozen=True)
class GoldEntity:
    primary_label: str
    acceptable_labels: Set[str]
    candidates: List[GoldCandidate]
    expected_sources: Set[str]


@dataclass
class EvalCounts:
    tp: int = 0
    fp: int = 0
    fn: int = 0

    def precision(self) -> float:
        d = self.tp + self.fp
        return (self.tp / d) if d else 0.0

    def recall(self) -> float:
        d = self.tp + self.fn
        return (self.tp / d) if d else 0.0

    def f1(self) -> float:
        p = self.precision()
        r = self.recall()
        d = p + r
        return (2.0 * p * r / d) if d else 0.0


@dataclass(frozen=True)
class Miss:
    kind: str
    label: str
    start: int
    end: int
    source: str
    text: str
    pred_start: Optional[int] = None
    pred_end: Optional[int] = None
    pred_source: Optional[str] = None
    pred_text: Optional[str] = None


def _read_text(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def _read_json(p: Path) -> Dict[str, Any]:
    return json.loads(p.read_text(encoding="utf-8"))


def _norm_source(s: Any) -> str:
    x = str(s or "").strip().lower()
    if x in ("ner", "regex", "dict", "manual"):
        return x
    if x == "dictionary":
        return "dict"
    return x or "?"


def _norm_label(s: Any) -> str:
    return str(s or "").strip().upper()


def _normalize_label_list(values: List[str]) -> List[str]:
    out: List[str] = []
    seen: Set[str] = set()

    for value in values:
        label = _norm_label(value)
        if not label:
            continue
        if label in seen:
            continue
        seen.add(label)
        out.append(label)

    return out


def _apply_policy(policy_name: str) -> None:
    policy_key = str(policy_name or "").strip().lower()

    if policy_key not in POLICY_SPECS:
        raise ValueError(f"Unknown policy: {policy_name}")

    spec = POLICY_SPECS[policy_key]
    config.set("ner_labels", _normalize_label_list(spec.get("ner_labels", [])))
    config.set("regex_labels", _normalize_label_list(spec.get("regex_labels", [])))
    config.set_flags(
        use_regex=True,
        use_ner=True,
        debug_mask=bool(config.get("debug_mask", False)),
    )


def _policy_labels(policy_name: str) -> Set[str]:
    policy_key = str(policy_name or "").strip().lower()

    if policy_key not in POLICY_SPECS:
        raise ValueError(f"Unknown policy: {policy_name}")

    spec = POLICY_SPECS[policy_key]
    ner_labels = set(_normalize_label_list(spec.get("ner_labels", [])))
    regex_labels = set(_normalize_label_list(spec.get("regex_labels", [])))
    return ner_labels.union(regex_labels)


def _extract_spans(text: str) -> List[Span]:
    hits = erkenne(text) or []
    out: List[Span] = []

    for h in hits:
        start = getattr(h, "start", None)
        end = getattr(h, "ende", None)
        label = getattr(h, "label", None)

        src = getattr(h, "source", None)
        if src is None:
            src = getattr(h, "quelle", None)

        if not isinstance(start, int) or not isinstance(end, int):
            continue

        L = _norm_label(label)
        S = _norm_source(src)

        if start < 0 or end <= start or end > len(text):
            continue

        out.append(Span(start=int(start), end=int(end), label=L, source=S))

    return out


def _extract_regex_spans_raw(text: str) -> List[Span]:
    try:
        from detectors.regex import finde_regex
    except Exception:
        return []

    out: List[Span] = []

    for s, e, label in finde_regex(text) or []:
        if not isinstance(s, int) or not isinstance(e, int):
            continue
        if s < 0 or e <= s or e > len(text):
            continue
        out.append(Span(start=s, end=e, label=_norm_label(label), source="regex"))

    return out


def _parse_gold(gold: Dict[str, Any]) -> List[GoldEntity]:
    ents = gold.get("entities")
    if not isinstance(ents, list):
        raise ValueError("gold.json: field 'entities' must be a list")

    out: List[GoldEntity] = []

    for e in ents:
        if not isinstance(e, dict):
            continue

        raw_label = e.get("label")

        labels_ordered: List[str] = []
        if isinstance(raw_label, list):
            for x in raw_label:
                L = _norm_label(x)
                if L and L not in labels_ordered:
                    labels_ordered.append(L)
        else:
            L = _norm_label(raw_label)
            if L:
                labels_ordered.append(L)

        if not labels_ordered:
            continue

        primary_label = labels_ordered[0]
        acceptable_labels = set(labels_ordered)

        expected_sources_raw = e.get("expected_sources", [])
        if not isinstance(expected_sources_raw, list):
            expected_sources_raw = []
        expected_sources = {_norm_source(x) for x in expected_sources_raw if str(x).strip()}

        alts = e.get("alternatives", None)
        candidates: List[GoldCandidate] = []

        if isinstance(alts, list) and alts:
            for a in alts:
                if not isinstance(a, dict):
                    continue

                start = a.get("start")
                end = a.get("end")
                txt = a.get("text", "")

                if not isinstance(start, int) or not isinstance(end, int):
                    continue

                alt_sources_raw = a.get("expected_sources", None)
                if isinstance(alt_sources_raw, list) and alt_sources_raw:
                    alt_sources = {_norm_source(x) for x in alt_sources_raw if str(x).strip()}
                else:
                    alt_sources = set(expected_sources)

                candidates.append(
                    GoldCandidate(
                        start=int(start),
                        end=int(end),
                        text=str(txt or ""),
                        expected_sources=alt_sources,
                    )
                )
        else:
            start = e.get("start")
            end = e.get("end")
            txt = e.get("text", "")

            if not isinstance(start, int) or not isinstance(end, int):
                continue

            candidates.append(
                GoldCandidate(
                    start=int(start),
                    end=int(end),
                    text=str(txt or ""),
                    expected_sources=set(expected_sources),
                )
            )

        if not candidates:
            continue

        out.append(
            GoldEntity(
                primary_label=primary_label,
                acceptable_labels=acceptable_labels,
                candidates=candidates,
                expected_sources=expected_sources,
            )
        )

    return out


def _gold_required_for_policy(g: GoldEntity, allowed_labels: Set[str]) -> bool:
    if not allowed_labels:
        return False
    return bool(g.acceptable_labels.intersection(allowed_labels))


def _snapshot_config() -> Dict[str, Any]:
    return {
        "flags": dict(config.get_flags() or {}),
        "ner_labels": list(config.get("ner_labels", []) or []),
        "regex_labels": list(config.get("regex_labels", []) or []),
        "spacy_model": config.get("spacy_model", ""),
        "debug_mask": bool(config.get("debug_mask", False)),
        "use_ner_postprocessing": config.get("use_ner_postprocessing", True),
    }


def _restore_config(snap: Dict[str, Any]) -> None:
    flags = snap.get("flags", {}) or {}
    config.set_flags(
        use_regex=bool(flags.get("use_regex", True)),
        use_ner=bool(flags.get("use_ner", True)),
        debug_mask=bool(flags.get("debug_mask", False)),
    )
    config.set("ner_labels", snap.get("ner_labels", []) or [])
    config.set("regex_labels", snap.get("regex_labels", []) or [])
    config.set("spacy_model", snap.get("spacy_model", "") or "")
    config.set("debug_mask", bool(snap.get("debug_mask", False)))
    config.set("use_ner_postprocessing", snap.get("use_ner_postprocessing", True))


def _ctx(text: str, start: int, end: int, radius: int) -> str:
    left = text[max(0, start - radius):start].replace("\n", "\\n").replace("\r", "\\r")
    mid = text[start:end].replace("\n", "\\n").replace("\r", "\\r")
    right = text[end:min(len(text), end + radius)].replace("\n", "\\n").replace("\r", "\\r")
    return f"{left}▮{mid}▮{right}"


def _load_eval_config(eval_root: Path) -> Dict[str, Any]:
    cfg_path = eval_root / "eval_config.json"
    if not cfg_path.exists():
        return {}

    try:
        raw = json.loads(cfg_path.read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else {}
    except Exception:
        return {}


def _allowed_labels_for_source(cfg: Dict[str, Any], source: str) -> Set[str]:
    allowed_sources = cfg.get("allowed_sources", {})
    if not isinstance(allowed_sources, dict):
        return set()

    xs = allowed_sources.get(source, [])
    if not isinstance(xs, list):
        return set()

    out: Set[str] = set()

    for x in xs:
        s = str(x or "").strip().upper()
        if s:
            out.add(s)

    return out


def _apply_label_rules(
    text: str,
    spans: List[Span],
    regex_spans: List[Span],
    cfg: Dict[str, Any],
) -> List[Span]:
    ignore = set(str(x).strip().upper() for x in (cfg.get("ignore_labels", []) or []))

    ner_norm_raw = cfg.get("ner_normalize_labels", {}) or {}
    ner_norm: Dict[str, str] = {}
    if isinstance(ner_norm_raw, dict):
        for k, v in ner_norm_raw.items():
            kk = str(k).strip().upper()
            vv = str(v).strip().upper()
            if kk and vv:
                ner_norm[kk] = vv

    ner_to_domain_raw = cfg.get("ner_to_domain", {}) or {}
    ner_to_domain: Dict[str, str] = {}
    if isinstance(ner_to_domain_raw, dict):
        for k, v in ner_to_domain_raw.items():
            kk = str(k).strip().upper()
            vv = str(v).strip().upper()
            if kk and vv:
                ner_to_domain[kk] = vv

    loc_rules = cfg.get("loc_domain_rules", []) or []
    rules: List[Tuple[str, Set[str]]] = []
    if isinstance(loc_rules, list):
        for r in loc_rules:
            if not isinstance(r, dict):
                continue

            domain_label = str(r.get("domain_label", "")).strip().upper()
            overlaps = r.get("when_regex_label_overlaps", [])

            if not domain_label:
                continue

            ov: Set[str] = set()
            if isinstance(overlaps, list):
                for x in overlaps:
                    s = str(x).strip().upper()
                    if s:
                        ov.add(s)

            if ov:
                rules.append((domain_label, ov))

    out: List[Span] = []

    for s in spans:
        L = s.label.upper()

        if L in ignore:
            continue

        if s.source == "ner" and L in ner_norm:
            L = ner_norm[L]

        if s.source == "ner" and L in ner_to_domain:
            L = ner_to_domain[L]

        new_label = L

        if s.source == "ner" and L == "LOC" and rules:
            for domain_label, overlap_labels in rules:
                matched = False

                for r in regex_spans:
                    if r.label.upper() not in overlap_labels:
                        continue
                    if not (s.end <= r.start or r.end <= s.start):
                        new_label = domain_label
                        matched = True
                        break

                if matched:
                    break

        out.append(Span(start=s.start, end=s.end, label=new_label, source=s.source))

    return out


def _overlaps(a_start: int, a_end: int, b_start: int, b_end: int) -> bool:
    return not (a_end <= b_start or b_end <= a_start)


def _evaluate(
    text: str,
    gold_entities: List[GoldEntity],
    *,
    policy_name: str,
    eval_root: Optional[Path] = None,
) -> Tuple[EvalCounts, Dict[str, EvalCounts], List[Miss]]:
    _apply_policy(policy_name)

    cfg = _load_eval_config(eval_root or Path("evaluation"))
    allowed_policy_labels = _policy_labels(policy_name)

    preds = _extract_spans(text)

    allowed_regex = _allowed_labels_for_source(cfg, "regex")
    allowed_ner = _allowed_labels_for_source(cfg, "ner")

    if allowed_regex or allowed_ner:
        filtered: List[Span] = []

        for p in preds:
            if p.source == "regex":
                if allowed_regex and p.label.upper() not in allowed_regex:
                    continue
            if p.source == "ner":
                if allowed_ner and p.label.upper() not in allowed_ner:
                    continue
            filtered.append(p)

        preds = filtered

    regex_ref = _extract_regex_spans_raw(text)
    if allowed_regex:
        regex_ref = [r for r in regex_ref if r.label.upper() in allowed_regex]

    preds = _apply_label_rules(text, preds, regex_ref, cfg)

    pred_by_key: Dict[Tuple[int, int, str], Span] = {p.key(): p for p in preds}

    counts_total = EvalCounts()
    counts_by_label: Dict[str, EvalCounts] = {}
    misses: List[Miss] = []

    matched_pred_keys: Set[Tuple[int, int, str]] = set()
    partial_pred_keys: Set[Tuple[int, int, str]] = set()

    for g in gold_entities:
        if not _gold_required_for_policy(g, allowed_policy_labels):
            continue

        candidates = list(g.candidates)
        if not candidates:
            continue

        lbl_counts = counts_by_label.setdefault(g.primary_label, EvalCounts())

        found_exact: Optional[Tuple[int, int, str]] = None

        for c in candidates:
            for L in g.acceptable_labels:
                if L not in allowed_policy_labels:
                    continue

                k = (c.start, c.end, L)
                if k in pred_by_key:
                    found_exact = k
                    break

            if found_exact is not None:
                break

        if found_exact is not None:
            counts_total.tp += 1
            lbl_counts.tp += 1
            matched_pred_keys.add(found_exact)

            p = pred_by_key[found_exact]
            misses.append(
                Miss(
                    kind="TP",
                    label=p.label,
                    start=p.start,
                    end=p.end,
                    source=p.source,
                    text=text[p.start:p.end],
                )
            )
            continue

        best_partial_pred: Optional[Span] = None
        best_partial_gold: Optional[GoldCandidate] = None

        for c in candidates:
            for p in preds:
                if p.label not in g.acceptable_labels:
                    continue
                if p.label not in allowed_policy_labels:
                    continue
                if not _overlaps(p.start, p.end, c.start, c.end):
                    continue
                if p.start == c.start and p.end == c.end:
                    continue

                best_partial_pred = p
                best_partial_gold = c
                break

            if best_partial_pred is not None:
                break

        if best_partial_pred is not None and best_partial_gold is not None:
            partial_pred_keys.add(best_partial_pred.key())

            counts_total.fp += 1
            counts_total.fn += 1

            lbl_counts.fp += 1
            lbl_counts.fn += 1

            misses.append(
                Miss(
                    kind="PARTIAL",
                    label=g.primary_label,
                    start=best_partial_gold.start,
                    end=best_partial_gold.end,
                    source="gold",
                    text=best_partial_gold.text or text[best_partial_gold.start:best_partial_gold.end],
                    pred_start=best_partial_pred.start,
                    pred_end=best_partial_pred.end,
                    pred_source=best_partial_pred.source,
                    pred_text=text[best_partial_pred.start:best_partial_pred.end],
                )
            )
            continue

        counts_total.fn += 1
        lbl_counts.fn += 1

        c0 = candidates[0]
        misses.append(
            Miss(
                kind="FN",
                label=g.primary_label,
                start=c0.start,
                end=c0.end,
                source="gold",
                text=c0.text or text[c0.start:c0.end],
            )
        )

    for p in preds:
        if p.label not in allowed_policy_labels:
            continue

        k = p.key()

        if k in matched_pred_keys:
            continue
        if k in partial_pred_keys:
            continue

        counts_total.fp += 1
        lbl_counts = counts_by_label.setdefault(p.label, EvalCounts())
        lbl_counts.fp += 1

        misses.append(
            Miss(
                kind="FP",
                label=p.label,
                start=p.start,
                end=p.end,
                source=p.source,
                text=text[p.start:p.end],
            )
        )

    misses.sort(key=lambda m: (m.start, m.end, m.kind, m.label))
    return counts_total, counts_by_label, misses


def _format_summary(total: EvalCounts) -> str:
    return (
        f"TP={total.tp:3d} FP={total.fp:3d} FN={total.fn:3d} | "
        f"P={total.precision():.3f} R={total.recall():.3f} F1={total.f1():.3f}"
    )


def _format_per_label(by_label: Dict[str, EvalCounts]) -> List[str]:
    lines: List[str] = []

    for lbl in sorted(by_label.keys()):
        c = by_label[lbl]
        if (c.tp + c.fp + c.fn) == 0:
            continue

        lines.append(
            f"  {lbl:14s} TP={c.tp:3d} FP={c.fp:3d} FN={c.fn:3d} "
            f"P={c.precision():.3f} R={c.recall():.3f} F1={c.f1():.3f}"
        )

    return lines


def _format_misses(
    text: str,
    misses: List[Miss],
    *,
    show_tp: bool,
    ctx_radius: int,
    max_lines: int,
) -> List[str]:
    lines: List[str] = []

    def dump_fn() -> None:
        items = [m for m in misses if m.kind == "FN"]
        lines.append(f"NOT DETECTED (FN): {len(items)}")
        if not items:
            return

        shown = 0
        for m in items:
            if shown >= max_lines:
                lines.append(f"  ... truncated ({len(items) - max_lines} more)")
                break

            ctx = _ctx(text, m.start, m.end, ctx_radius) if ctx_radius > 0 else ""
            if ctx:
                lines.append(f"  - {m.label:14s} {m.start}:{m.end} [{m.source}] '{m.text}' ctx='{ctx}'")
            else:
                lines.append(f"  - {m.label:14s} {m.start}:{m.end} [{m.source}] '{m.text}'")

            shown += 1

    def dump_fp() -> None:
        items = [m for m in misses if m.kind == "FP"]
        lines.append(f"UNEXPECTED (FP): {len(items)}")
        if not items:
            return

        shown = 0
        for m in items:
            if shown >= max_lines:
                lines.append(f"  ... truncated ({len(items) - max_lines} more)")
                break

            ctx = _ctx(text, m.start, m.end, ctx_radius) if ctx_radius > 0 else ""
            if ctx:
                lines.append(f"  - {m.label:14s} {m.start}:{m.end} [{m.source}] '{m.text}' ctx='{ctx}'")
            else:
                lines.append(f"  - {m.label:14s} {m.start}:{m.end} [{m.source}] '{m.text}'")

            shown += 1

    def dump_partial() -> None:
        items = [m for m in misses if m.kind == "PARTIAL"]
        lines.append(f"NOT FULLY DETECTED (PARTIAL): {len(items)}")
        if not items:
            return

        shown = 0
        for m in items:
            if shown >= max_lines:
                lines.append(f"  ... truncated ({len(items) - max_lines} more)")
                break

            g_ctx = _ctx(text, m.start, m.end, ctx_radius) if ctx_radius > 0 else ""
            p_ctx = ""
            if m.pred_start is not None and m.pred_end is not None and ctx_radius > 0:
                p_ctx = _ctx(text, m.pred_start, m.pred_end, ctx_radius)

            p_meta = ""
            if m.pred_start is not None and m.pred_end is not None and m.pred_source is not None:
                p_meta = f"[pred:{m.pred_source}:{m.pred_start}:{m.pred_end}] '{m.pred_text or ''}'"

            if g_ctx:
                if p_ctx:
                    lines.append(
                        f"  - {m.label:14s} gold {m.start}:{m.end} [{m.source}] '{m.text}' "
                        f"{p_meta} gold_ctx='{g_ctx}' pred_ctx='{p_ctx}'"
                    )
                else:
                    lines.append(
                        f"  - {m.label:14s} gold {m.start}:{m.end} [{m.source}] '{m.text}' "
                        f"{p_meta} gold_ctx='{g_ctx}'"
                    )
            else:
                lines.append(
                    f"  - {m.label:14s} gold {m.start}:{m.end} [{m.source}] '{m.text}' {p_meta}"
                )

            shown += 1

    def dump_tp() -> None:
        if not show_tp:
            return

        items = [m for m in misses if m.kind == "TP"]
        lines.append(f"DETECTED (TP): {len(items)}")
        if not items:
            return

        shown = 0
        for m in items:
            if shown >= max_lines:
                lines.append(f"  ... truncated ({len(items) - max_lines} more)")
                break

            ctx = _ctx(text, m.start, m.end, ctx_radius) if ctx_radius > 0 else ""
            if ctx:
                lines.append(f"  - {m.label:14s} {m.start}:{m.end} [{m.source}] '{m.text}' ctx='{ctx}'")
            else:
                lines.append(f"  - {m.label:14s} {m.start}:{m.end} [{m.source}] '{m.text}'")

            shown += 1

    dump_fn()
    dump_partial()
    dump_fp()
    dump_tp()

    return lines


def _resolve_paths(eval_root: Path, basename: str) -> Tuple[Path, Path, Path, Path]:
    datasets_dir = eval_root / "datasets"
    data_dir = datasets_dir / "data"
    gold_dir = datasets_dir / "gold"

    result_dir = eval_root / "result"
    result_dir.mkdir(parents=True, exist_ok=True)

    text_path = data_dir / f"{basename}.txt"
    gold_path = gold_dir / f"{basename}.json"

    out_path = result_dir / f"{basename}_result.txt"
    dbg_path = result_dir / f"{basename}_result.debug.txt"

    return text_path, gold_path, out_path, dbg_path


def _run_single_variant(
    *,
    basename: str,
    eval_root: Path,
    policy: str,
    debug: bool,
    show_tp: bool,
    per_label: bool,
    ctx: int,
    max_lines: int,
    postprocess_enabled: bool,
) -> None:
    text_path, gold_path, _, _ = _resolve_paths(eval_root, basename)

    if not text_path.exists():
        raise FileNotFoundError(f"Missing text file: {text_path}")
    if not gold_path.exists():
        raise FileNotFoundError(f"Missing gold file: {gold_path}")

    text = _read_text(text_path)
    gold = _read_json(gold_path)
    gold_entities = _parse_gold(gold)

    variant_root = eval_root / "result" / ("postprocess_on" if postprocess_enabled else "postprocess_off")
    variant_root.mkdir(parents=True, exist_ok=True)

    out_path = variant_root / f"{basename}_result.txt"
    dbg_path = variant_root / f"{basename}_result.debug.txt"

    config.set("use_ner_postprocessing", postprocess_enabled)
    _apply_policy(policy)

    report_lines: List[str] = []
    debug_lines: List[str] = []

    total, by_label, misses = _evaluate(
        text,
        gold_entities,
        policy_name=policy,
        eval_root=eval_root,
    )

    report_lines.append(f"DATASET: {basename}")
    report_lines.append(f"TEXT: {text_path}")
    report_lines.append(f"GOLD: {gold_path}")
    report_lines.append(f"POLICY: {policy}")
    report_lines.append(f"NER_LABELS: {config.get('ner_labels', [])}")
    report_lines.append(f"REGEX_LABELS: {config.get('regex_labels', [])}")
    report_lines.append(f"NER_POSTPROCESSING: {bool(config.get('use_ner_postprocessing', True))}")
    report_lines.append("")
    report_lines.append("SUMMARY")
    report_lines.append("-" * 70)
    report_lines.append(_format_summary(total))

    if per_label:
        report_lines.append("")
        report_lines.append("PER-LABEL")
        report_lines.extend(_format_per_label(by_label))
        report_lines.append("")

    if debug:
        debug_lines.append(
            f"DATASET: {basename} | POLICY: {policy} | "
            f"POSTPROCESSING: {'on' if postprocess_enabled else 'off'}"
        )
        debug_lines.append(_format_summary(total))
        debug_lines.append("-" * 70)
        debug_lines.extend(
            _format_misses(
                text,
                misses,
                show_tp=bool(show_tp),
                ctx_radius=max(0, int(ctx)),
                max_lines=max(1, int(max_lines)),
            )
        )
        debug_lines.append("")
        debug_lines.append("=" * 70)
        debug_lines.append("")

    out_path.write_text("\n".join(report_lines).rstrip() + "\n", encoding="utf-8")

    if debug:
        dbg_path.write_text("\n".join(debug_lines).rstrip() + "\n", encoding="utf-8")

    print(f"Wrote: {out_path}")
    if debug:
        print(f"Wrote: {dbg_path}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True, help="Basename like Dataset_01 (without extension)")
    ap.add_argument("--eval-root", default="evaluation")
    ap.add_argument("--policy", choices=sorted(POLICY_SPECS.keys()), default="secure")
    ap.add_argument("--debug", action="store_true")
    ap.add_argument("--show-tp", action="store_true")
    ap.add_argument("--per-label", action="store_true")
    ap.add_argument("--ctx", type=int, default=20)
    ap.add_argument("--max-lines", type=int, default=200)
    ap.add_argument(
        "--only-post",
        choices=["on", "off"],
        default=None,
        help="Optional: run only one variant instead of both",
    )
    args = ap.parse_args()

    eval_root = Path(args.eval_root)
    snap = _snapshot_config()

    try:
        run_variants: List[bool]

        if args.only_post == "on":
            run_variants = [True]
        elif args.only_post == "off":
            run_variants = [False]
        else:
            run_variants = [False, True]

        for postprocess_enabled in run_variants:
            _run_single_variant(
                basename=args.name,
                eval_root=eval_root,
                policy=args.policy,
                debug=bool(args.debug),
                show_tp=bool(args.show_tp),
                per_label=bool(args.per_label),
                ctx=int(args.ctx),
                max_lines=int(args.max_lines),
                postprocess_enabled=postprocess_enabled,
            )

    finally:
        _restore_config(snap)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())