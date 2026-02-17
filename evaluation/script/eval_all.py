from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

EVAL_DIR = REPO_ROOT / "evaluation"
SCRIPT_DIR = EVAL_DIR / "script"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(EVAL_DIR) not in sys.path:
    sys.path.insert(0, str(EVAL_DIR))

from core import config

from evaluation.script.eval_single import (  # type: ignore
    EvalCounts,
    Miss,
    _evaluate,
    _format_misses,
    _format_per_label,
    _format_summary,
    _parse_gold,
    _read_json,
    _read_text,
    _resolve_paths,
    _restore_config,
    _snapshot_config,
)


@dataclass
class ModeAgg:
    tp: int = 0
    fp: int = 0
    fn: int = 0

    def add(self, c: EvalCounts) -> None:
        self.tp += c.tp
        self.fp += c.fp
        self.fn += c.fn

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


def _discover_datasets(eval_root: Path) -> List[str]:
    gold_dir = eval_root / "datasets" / "gold"
    if not gold_dir.exists():
        return []
    names: List[str] = []
    for p in sorted(gold_dir.glob("*.json")):
        names.append(p.stem)
    return names


def _load_gold_entities(eval_root: Path, name: str) -> Tuple[str, List[Any], str, str]:
    text_path, gold_path, _, _ = _resolve_paths(eval_root, name)
    if not text_path.exists():
        raise FileNotFoundError(f"Missing text file: {text_path}")
    if not gold_path.exists():
        raise FileNotFoundError(f"Missing gold file: {gold_path}")

    text = _read_text(text_path)
    gold = _read_json(gold_path)
    gold_entities = _parse_gold(gold)
    return text, gold_entities, str(text_path), str(gold_path)


def _write_text(path: Path, s: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(s.rstrip() + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--eval-root", default="evaluation")
    ap.add_argument("--debug", action="store_true", help="Write per-dataset debug files")
    ap.add_argument("--show-tp", action="store_true", help="Include TP list in debug files")
    ap.add_argument("--per-label", action="store_true", help="Include per-label stats per dataset")
    ap.add_argument("--ctx", type=int, default=20)
    ap.add_argument("--max-lines", type=int, default=200)
    ap.add_argument("--only", nargs="*", default=None, help="Run only these dataset basenames (e.g. Dataset_01 Dataset_02)")
    ap.add_argument("--out", default=None, help="Output file for combined report (default: evaluation/result/ALL_result.txt)")

    ap.add_argument(
        "--no-ner-post",
        action="store_true",
        help="Disable NER postprocessing (raw spaCy output)",
    )

    args = ap.parse_args()

    eval_root = Path(args.eval_root)

    dataset_names = _discover_datasets(eval_root)
    if args.only:
        wanted = {x.strip() for x in args.only if x.strip()}
        dataset_names = [n for n in dataset_names if n in wanted]

    if not dataset_names:
        raise SystemExit("No datasets found (no gold json files).")

    out_path = Path(args.out) if args.out else (eval_root / "result" / "ALL_result.txt")
    dbg_dir = eval_root / "result" / "debug_all"

    modes: List[Tuple[str, Set[str]]] = [
        ("regex", {"regex"}),
        ("ner", {"ner"}),
        ("combined", {"regex", "ner"}),
    ]

    snap = _snapshot_config()
    try:
        if args.no_ner_post:
            config.set("use_ner_postprocessing", False)
        else:
            config.set("use_ner_postprocessing", True)

        report_lines: List[str] = []
        report_lines.append(f"EVAL ROOT: {eval_root}")
        report_lines.append(f"DATASETS: {len(dataset_names)}")
        report_lines.append(f"NER_POSTPROCESSING: {not bool(args.no_ner_post)}")
        report_lines.append("")

        agg: Dict[str, ModeAgg] = {m[0]: ModeAgg() for m in modes}

        for name in dataset_names:
            text, gold_entities, text_path_s, gold_path_s = _load_gold_entities(eval_root, name)

            report_lines.append(f"DATASET: {name}")
            report_lines.append(f"TEXT: {text_path_s}")
            report_lines.append(f"GOLD: {gold_path_s}")
            report_lines.append("")

            report_lines.append("SUMMARY")
            report_lines.append("-" * 70)

            for mode, sources in modes:
                total, by_label, misses = _evaluate(text, gold_entities, mode=mode, mode_sources=set(sources))
                agg[mode].add(total)
                report_lines.append(_format_summary(mode, total))

                if args.per_label:
                    report_lines.append("")
                    report_lines.append(f"PER-LABEL ({mode})")
                    report_lines.extend(_format_per_label(by_label))
                    report_lines.append("")

                if args.debug:
                    dbg_lines: List[str] = []
                    dbg_lines.append(f"DATASET: {name} | MODE: {mode}")
                    dbg_lines.append(_format_summary(mode, total))
                    dbg_lines.append("-" * 70)
                    dbg_lines.extend(
                        _format_misses(
                            text,
                            misses,
                            show_tp=bool(args.show_tp),
                            ctx_radius=max(0, int(args.ctx)),
                            max_lines=max(1, int(args.max_lines)),
                        )
                    )
                    dbg_lines.append("")
                    _write_text(dbg_dir / f"{name}_{mode}.debug.txt", "\n".join(dbg_lines))

            report_lines.append("")
            report_lines.append("=" * 70)
            report_lines.append("")

        report_lines.append("GLOBAL SUMMARY (micro-averaged over all datasets)")
        report_lines.append("-" * 70)
        for mode, _ in modes:
            a = agg[mode]
            report_lines.append(
                f"MODE {mode:8s} | "
                f"TP={a.tp:4d} FP={a.fp:4d} FN={a.fn:4d} | "
                f"P={a.precision():.3f} R={a.recall():.3f} F1={a.f1():.3f}"
            )

        _write_text(out_path, "\n".join(report_lines))
        print(f"Wrote: {out_path}")
        if args.debug:
            print(f"Wrote debug files: {dbg_dir}")

    finally:
        _restore_config(snap)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())