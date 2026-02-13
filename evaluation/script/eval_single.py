from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import argparse
import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set, Tuple

from core import config
from pipeline.anonymisieren import erkenne

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
    label: str
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


def _extract_spans(text: str, *, allowed_sources: Set[str]) -> List[Span]:
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

        if S not in allowed_sources:
            continue

        if start < 0 or end <= start or end > len(text):
            continue

        out.append(Span(start=start, end=end, label=L, source=S))

    return out


def _parse_gold(gold: Dict[str, Any]) -> List[GoldEntity]:
    ents = gold.get("entities")
    if not isinstance(ents, list):
        raise ValueError("gold.json: field 'entities' must be a list")

    out: List[GoldEntity] = []

    for e in ents:
        if not isinstance(e, dict):
            continue

        label = _norm_label(e.get("label"))
        if not label:
            continue

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
                text = a.get("text", "")

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
                        text=str(text or ""),
                        expected_sources=alt_sources,
                    )
                )
        else:
            start = e.get("start")
            end = e.get("end")
            text = e.get("text", "")

            if not isinstance(start, int) or not isinstance(end, int):
                continue

            candidates.append(
                GoldCandidate(
                    start=int(start),
                    end=int(end),
                    text=str(text or ""),
                    expected_sources=set(expected_sources),
                )
            )

        if not candidates:
            continue

        out.append(GoldEntity(label=label, candidates=candidates, expected_sources=expected_sources))

    return out


def _gold_required_for_mode(g: GoldEntity, mode_sources: Set[str]) -> bool:
    if not g.expected_sources:
        return True
    return bool(g.expected_sources.intersection(mode_sources))


def _candidate_allowed_for_mode(c: GoldCandidate, mode_sources: Set[str]) -> bool:
    if not c.expected_sources:
        return True
    return bool(c.expected_sources.intersection(mode_sources))


def _set_config_for_mode(mode: str) -> None:
    # Erwartet core.config API: set_flags(...) + set(...)
    # Wenn deine API abweicht: dann bricht es hier, dann musst du es anpassen.
    flags = dict(config.get_flags() or {})
    debug_mask = bool(flags.get("debug_mask", False))

    if mode == "regex":
        config.set_flags(use_regex=True, use_ner=False, debug_mask=debug_mask)
        config.set("ner_labels", [])
    elif mode == "ner":
        config.set_flags(use_regex=False, use_ner=True, debug_mask=debug_mask)
        if not (config.get("ner_labels", None) or []):
            config.set("ner_labels", ["PER", "ORG", "LOC", "GPE", "MISC"])
    elif mode == "combined":
        config.set_flags(use_regex=True, use_ner=True, debug_mask=debug_mask)
        if not (config.get("ner_labels", None) or []):
            config.set("ner_labels", ["PER", "ORG", "LOC", "GPE", "MISC"])
    else:
        raise ValueError(f"Unknown mode: {mode}")


def _snapshot_config() -> Dict[str, Any]:
    return {
        "flags": dict(config.get_flags() or {}),
        "ner_labels": list(config.get("ner_labels", []) or []),
        "regex_labels": list(config.get("regex_labels", []) or []),
        "spacy_model": config.get("spacy_model", ""),
        "debug_mask": bool(config.get("debug_mask", False)),
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


def _evaluate(
    text: str,
    gold_entities: List[GoldEntity],
    *,
    mode: str,
    mode_sources: Set[str],
) -> Tuple[EvalCounts, Dict[str, EvalCounts], List[str]]:
    _set_config_for_mode(mode)

    preds = _extract_spans(text, allowed_sources=mode_sources)
    pred_by_key: Dict[Tuple[int, int, str], Span] = {p.key(): p for p in preds}

    counts_total = EvalCounts()
    counts_by_label: Dict[str, EvalCounts] = {}
    debug_lines: List[str] = []

    matched_pred_keys: Set[Tuple[int, int, str]] = set()

    for g in gold_entities:
        if not _gold_required_for_mode(g, mode_sources):
            continue

        candidates = [c for c in g.candidates if _candidate_allowed_for_mode(c, mode_sources)]
        if not candidates:
            continue

        found_key: Optional[Tuple[int, int, str]] = None
        for c in candidates:
            k = (c.start, c.end, g.label)
            if k in pred_by_key:
                found_key = k
                break

        lbl_counts = counts_by_label.setdefault(g.label, EvalCounts())

        if found_key is not None:
            counts_total.tp += 1
            lbl_counts.tp += 1
            matched_pred_keys.add(found_key)
        else:
            counts_total.fn += 1
            lbl_counts.fn += 1
            cand_str = " OR ".join([f"{c.start}:{c.end} '{c.text}'" for c in candidates])
            debug_lines.append(f"FN {g.label}: {cand_str}")

    for p in preds:
        k = p.key()
        if k in matched_pred_keys:
            continue
        counts_total.fp += 1
        lbl_counts = counts_by_label.setdefault(p.label, EvalCounts())
        lbl_counts.fp += 1
        debug_lines.append(f"FP {p.label} ({p.source}) {p.start}:{p.end} '{text[p.start:p.end]}'")

    return counts_total, counts_by_label, debug_lines


def _format_report(mode: str, total: EvalCounts, by_label: Dict[str, EvalCounts]) -> str:
    lines: List[str] = []
    lines.append(f"MODE: {mode}")
    lines.append(f"TP: {total.tp}")
    lines.append(f"FP: {total.fp}")
    lines.append(f"FN: {total.fn}")
    lines.append(f"Precision: {total.precision():.4f}")
    lines.append(f"Recall:    {total.recall():.4f}")
    lines.append(f"F1:        {total.f1():.4f}")
    lines.append("")
    lines.append("PER-LABEL:")
    for lbl in sorted(by_label.keys()):
        c = by_label[lbl]
        lines.append(
            f"- {lbl:12s} TP={c.tp:3d} FP={c.fp:3d} FN={c.fn:3d} "
            f"P={c.precision():.4f} R={c.recall():.4f} F1={c.f1():.4f}"
        )
    return "\n".join(lines)


def _resolve_paths(dataset_root: Path, basename: str) -> Tuple[Path, Path, Path]:
    data_dir = dataset_root / "data"
    gold_dir = dataset_root / "gold"
    result_dir = dataset_root / "result"

    text_path = data_dir / f"{basename}.txt"
    gold_path = gold_dir / f"{basename}.json"
    result_dir.mkdir(parents=True, exist_ok=True)

    out_path = result_dir / f"{basename}_result.txt"
    dbg_path = result_dir / f"{basename}_result.debug.txt"
    return text_path, gold_path, out_path, dbg_path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset-root", default="evaluation/datasets", help="Root folder containing data/gold/result")
    ap.add_argument("--name", required=True, help="Basename like Dataset_01 (without extension)")
    ap.add_argument("--debug", action="store_true", help="Write FP/FN details into result debug file")
    args = ap.parse_args()

    dataset_root = Path(args.dataset_root)
    basename = args.name

    text_path, gold_path, out_path, dbg_path = _resolve_paths(dataset_root, basename)

    if not text_path.exists():
        raise FileNotFoundError(f"Missing text file: {text_path}")
    if not gold_path.exists():
        raise FileNotFoundError(f"Missing gold file: {gold_path}")

    text = _read_text(text_path)
    gold = _read_json(gold_path)
    gold_entities = _parse_gold(gold)

    snap = _snapshot_config()
    try:
        modes = [
            ("regex", {"regex"}),
            ("ner", {"ner"}),
            ("combined", {"regex", "ner"}),
        ]

        all_reports: List[str] = []
        all_debug: List[str] = []

        all_reports.append(f"DATASET: {basename}")
        all_reports.append(f"TEXT: {text_path}")
        all_reports.append(f"GOLD: {gold_path}")
        all_reports.append("")
        all_reports.append("=" * 70)
        all_reports.append("")

        for mode, sources in modes:
            total, by_label, debug_lines = _evaluate(text, gold_entities, mode=mode, mode_sources=set(sources))
            all_reports.append(_format_report(mode, total, by_label))
            all_reports.append("\n" + ("=" * 70) + "\n")

            if args.debug:
                all_debug.append(f"DATASET: {basename}")
                all_debug.append(f"MODE: {mode}")
                all_debug.extend(debug_lines)
                all_debug.append("\n" + ("-" * 70) + "\n")

        out_path.write_text("\n".join(all_reports).rstrip() + "\n", encoding="utf-8")

        if args.debug:
            dbg_path.write_text("\n".join(all_debug).rstrip() + "\n", encoding="utf-8")

    finally:
        _restore_config(snap)

    print(f"Wrote: {out_path}")
    if args.debug:
        print(f"Wrote: {dbg_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())