from __future__ import annotations

import argparse
import csv
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Set, Tuple

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

EVAL_DIR = REPO_ROOT / "evaluation"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(EVAL_DIR) not in sys.path:
    sys.path.insert(0, str(EVAL_DIR))

from core import config

from evaluation.script.eval_single import (
    EvalCounts,
    Miss,
    POLICY_SPECS,
    _apply_policy,
    _evaluate,
    _format_misses,
    _format_per_label,
    _parse_gold,
    _read_json,
    _read_text,
    _resolve_paths,
    _restore_config,
    _snapshot_config,
)


DOMAINS: List[str] = [
    "Supporttickets",
    "E-Mail",
    "HR-Dokumente",
    "Verträge",
    "Chats",
]

STRUCTURES: List[str] = [
    "structured",
    "regular",
    "unstructured",
]

MODES: List[Tuple[str, Set[str]]] = [
    ("regex", {"regex"}),
    ("ner", {"ner"}),
    ("combined", {"regex", "ner"}),
]


@dataclass(frozen=True)
class DatasetMeta:
    dataset: str
    dataset_index: int
    domain: str
    structure: str
    variant: int


@dataclass
class MetricAgg:
    tp: int = 0
    fp: int = 0
    fn: int = 0

    def add(self, counts: EvalCounts) -> None:
        self.tp += counts.tp
        self.fp += counts.fp
        self.fn += counts.fn

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
class DatasetRunRow:
    dataset: str
    dataset_index: int
    domain: str
    structure: str
    variant: int
    policy: str
    mode: str
    tp: int
    fp: int
    fn: int
    precision: float
    recall: float
    f1: float


def _discover_datasets(eval_root: Path) -> List[str]:
    gold_dir = eval_root / "datasets" / "gold"
    if not gold_dir.exists():
        return []
    return [p.stem for p in sorted(gold_dir.glob("*.json"))]


def _load_gold_entities(eval_root: Path, name: str) -> Tuple[str, List[object]]:
    text_path, gold_path, _, _ = _resolve_paths(eval_root, name)
    if not text_path.exists():
        raise FileNotFoundError(f"Missing text file: {text_path}")
    if not gold_path.exists():
        raise FileNotFoundError(f"Missing gold file: {gold_path}")

    text = _read_text(text_path)
    gold = _read_json(gold_path)
    gold_entities = _parse_gold(gold)
    return text, gold_entities


def _write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value.rstrip() + "\n", encoding="utf-8")


def _write_csv(path: Path, rows: List[Dict[str, object]], fieldnames: List[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _miss_line(dataset: str, m: Miss) -> str:
    if m.kind == "PARTIAL":
        g = (m.text or "").replace("\n", "\\n").replace("\r", "\\r")
        p = (m.pred_text or "").replace("\n", "\\n").replace("\r", "\\r")
        ps = m.pred_source or "?"
        p_start = m.pred_start if m.pred_start is not None else -1
        p_end = m.pred_end if m.pred_end is not None else -1
        return (
            f"{dataset} gold:{m.start}:{m.end} [{m.source}] '{g}' "
            f"<- pred:{ps}:{p_start}:{p_end} '{p}'"
        )

    t = (m.text or "").replace("\n", "\\n").replace("\r", "\\r")
    return f"{dataset} {m.start}:{m.end} [{m.source}] '{t}'"


def _format_label_report(
    label_hits: Dict[str, Dict[str, List[str]]],
    *,
    policy: str,
    mode: str,
    max_items_per_section: int,
) -> str:
    lines: List[str] = []
    lines.append(f"LABEL REPORT | POLICY: {policy} | MODE: {mode}")
    lines.append("-" * 80)
    lines.append("")

    for lbl in sorted(label_hits.keys()):
        sections = label_hits[lbl]
        lines.append(lbl)
        lines.append("-" * 80)

        for kind, title in (
            ("TP", "ERKANNT (TP)"),
            ("PARTIAL", "NICHT VOLLSTÄNDIG ERKANNT (PARTIAL)"),
            ("FN", "NICHT ERKANNT (FN)"),
            ("FP", "UNERWARTET (FP)"),
        ):
            items = sections.get(kind, [])
            lines.append(f"{title}: {len(items)}")
            if items:
                shown = 0
                for item in items:
                    if shown >= max_items_per_section:
                        lines.append(f"  ... truncated ({len(items) - max_items_per_section} more)")
                        break
                    lines.append(f"  - {item}")
                    shown += 1
            lines.append("")

        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _format_summary(mode: str, total: EvalCounts) -> str:
    return (
        f"MODE {mode:8s} | "
        f"TP={total.tp} FP={total.fp} FN={total.fn} | "
        f"P={total.precision():.3f} R={total.recall():.3f} F1={total.f1():.3f}"
    )


def _parse_dataset_index(name: str) -> int:
    parts = name.split("_")
    if len(parts) != 2:
        raise ValueError(f"Unexpected dataset name: {name}")

    idx = int(parts[1])
    if idx < 1 or idx > 30:
        raise ValueError(f"Dataset index out of range: {name}")

    return idx


def _dataset_meta(name: str) -> DatasetMeta:
    idx = _parse_dataset_index(name)

    zero_based = idx - 1
    domain_idx = zero_based // 6
    in_domain = zero_based % 6
    structure_idx = in_domain // 2
    variant = (in_domain % 2) + 1

    return DatasetMeta(
        dataset=name,
        dataset_index=idx,
        domain=DOMAINS[domain_idx],
        structure=STRUCTURES[structure_idx],
        variant=variant,
    )


def _aggregate_rows(
    rows: List[DatasetRunRow],
    group_keys: List[str],
) -> List[Dict[str, object]]:
    buckets: Dict[Tuple[object, ...], MetricAgg] = {}
    key_values: Dict[Tuple[object, ...], Dict[str, object]] = {}

    for row in rows:
        row_dict: Dict[str, object] = {
            "dataset": row.dataset,
            "dataset_index": row.dataset_index,
            "domain": row.domain,
            "structure": row.structure,
            "variant": row.variant,
            "policy": row.policy,
            "mode": row.mode,
        }

        key = tuple(row_dict[k] for k in group_keys)

        if key not in buckets:
            buckets[key] = MetricAgg()
            key_values[key] = {k: row_dict[k] for k in group_keys}

        buckets[key].tp += row.tp
        buckets[key].fp += row.fp
        buckets[key].fn += row.fn

    out: List[Dict[str, object]] = []

    for key in sorted(buckets.keys()):
        agg = buckets[key]
        base = dict(key_values[key])
        base["tp"] = agg.tp
        base["fp"] = agg.fp
        base["fn"] = agg.fn
        base["precision"] = f"{agg.precision():.6f}"
        base["recall"] = f"{agg.recall():.6f}"
        base["f1"] = f"{agg.f1():.6f}"
        out.append(base)

    return out


def _aggregate_label_rows(
    label_rows: List[Dict[str, object]],
    group_keys: List[str],
) -> List[Dict[str, object]]:
    buckets: Dict[Tuple[object, ...], MetricAgg] = {}
    key_values: Dict[Tuple[object, ...], Dict[str, object]] = {}

    for row in label_rows:
        key = tuple(row[k] for k in group_keys)

        if key not in buckets:
            buckets[key] = MetricAgg()
            key_values[key] = {k: row[k] for k in group_keys}

        buckets[key].tp += int(row["tp"])
        buckets[key].fp += int(row["fp"])
        buckets[key].fn += int(row["fn"])

    out: List[Dict[str, object]] = []

    for key in sorted(buckets.keys()):
        agg = buckets[key]
        base = dict(key_values[key])
        base["tp"] = agg.tp
        base["fp"] = agg.fp
        base["fn"] = agg.fn
        base["precision"] = f"{agg.precision():.6f}"
        base["recall"] = f"{agg.recall():.6f}"
        base["f1"] = f"{agg.f1():.6f}"
        out.append(base)

    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--eval-root", default="evaluation")
    ap.add_argument("--debug", action="store_true", help="Write per-dataset debug files")
    ap.add_argument("--show-tp", action="store_true", help="Include TP list in debug files")
    ap.add_argument("--per-label", action="store_true", help="Include per-label stats per dataset in txt report")
    ap.add_argument("--ctx", type=int, default=20)
    ap.add_argument("--max-lines", type=int, default=200)
    ap.add_argument("--only", nargs="*", default=None, help="Run only these dataset basenames")
    ap.add_argument("--out", default=None, help="Output file for combined report")
    ap.add_argument("--no-ner-post", action="store_true", help="Disable NER postprocessing")
    ap.add_argument("--label-report", action="store_true", help="Write aggregated TP/PARTIAL/FN/FP label reports")
    ap.add_argument("--label-report-max", type=int, default=500)
    ap.add_argument(
        "--policies",
        nargs="*",
        default=["minimal", "secure"],
        choices=sorted(POLICY_SPECS.keys()),
        help="Policies to evaluate",
    )
    ap.add_argument(
        "--modes",
        nargs="*",
        default=["regex", "ner", "combined"],
        choices=["regex", "ner", "combined"],
        help="Modes to evaluate",
    )
    args = ap.parse_args()

    eval_root = Path(args.eval_root)
    result_dir = eval_root / "result"
    result_dir.mkdir(parents=True, exist_ok=True)

    dataset_names = _discover_datasets(eval_root)
    if args.only:
        wanted = {x.strip() for x in args.only if x.strip()}
        dataset_names = [n for n in dataset_names if n in wanted]

    if not dataset_names:
        raise SystemExit("No datasets found (no gold json files).")

    selected_modes = [m for m in MODES if m[0] in set(args.modes)]
    if not selected_modes:
        raise SystemExit("No modes selected.")

    selected_policies = [p for p in args.policies if p in POLICY_SPECS]
    if not selected_policies:
        raise SystemExit("No policies selected.")

    out_path = Path(args.out) if args.out else (result_dir / "ALL_result.txt")
    dbg_dir = result_dir / "debug_all"

    snap = _snapshot_config()

    try:
        config.set("use_ner_postprocessing", False if args.no_ner_post else True)

        report_lines: List[str] = []

        global_agg: Dict[Tuple[str, str], MetricAgg] = {
            (policy, mode): MetricAgg()
            for policy in selected_policies
            for mode, _ in selected_modes
        }

        label_hits_by_run: Dict[Tuple[str, str], Dict[str, Dict[str, List[str]]]] = {}
        if args.label_report:
            for policy in selected_policies:
                for mode, _ in selected_modes:
                    label_hits_by_run[(policy, mode)] = defaultdict(
                        lambda: {"TP": [], "PARTIAL": [], "FN": [], "FP": []}
                    )

        dataset_rows: List[DatasetRunRow] = []
        label_rows: List[Dict[str, object]] = []

        for name in dataset_names:
            meta = _dataset_meta(name)
            text, gold_entities = _load_gold_entities(eval_root, name)

            report_lines.append(f"DATASET: {name}")
            report_lines.append(f"DOMAIN: {meta.domain}")
            report_lines.append(f"STRUCTURE: {meta.structure}")
            report_lines.append("")

            for policy in selected_policies:
                _apply_policy(policy)

                report_lines.append(f"POLICY {policy}")

                for mode, sources in selected_modes:
                    total, by_label, misses = _evaluate(
                        text,
                        gold_entities,
                        mode=mode,
                        mode_sources=set(sources),
                        policy_name=policy,
                        eval_root=eval_root,
                    )

                    global_agg[(policy, mode)].add(total)

                    dataset_rows.append(
                        DatasetRunRow(
                            dataset=name,
                            dataset_index=meta.dataset_index,
                            domain=meta.domain,
                            structure=meta.structure,
                            variant=meta.variant,
                            policy=policy,
                            mode=mode,
                            tp=total.tp,
                            fp=total.fp,
                            fn=total.fn,
                            precision=total.precision(),
                            recall=total.recall(),
                            f1=total.f1(),
                        )
                    )

                    report_lines.append(_format_summary(mode, total))

                    if args.per_label:
                        report_lines.append("")
                        report_lines.append(f"PER-LABEL ({policy} | {mode})")
                        report_lines.extend(_format_per_label(by_label))
                        report_lines.append("")

                    known_labels = set(by_label.keys())
                    for label in sorted(known_labels):
                        c = by_label[label]
                        label_rows.append(
                            {
                                "dataset": name,
                                "dataset_index": meta.dataset_index,
                                "domain": meta.domain,
                                "structure": meta.structure,
                                "variant": meta.variant,
                                "policy": policy,
                                "mode": mode,
                                "label": label,
                                "tp": c.tp,
                                "fp": c.fp,
                                "fn": c.fn,
                            }
                        )

                    if args.label_report:
                        bucket = label_hits_by_run[(policy, mode)]
                        for miss in misses:
                            L = str(miss.label or "").strip().upper() or "?"
                            K = str(miss.kind or "").strip().upper()
                            if K not in ("TP", "FN", "FP", "PARTIAL"):
                                continue
                            bucket[L][K].append(_miss_line(name, miss))

                    if args.debug:
                        dbg_lines: List[str] = []
                        dbg_lines.append(
                            f"DATASET: {name} | DOMAIN: {meta.domain} | STRUCTURE: {meta.structure} | "
                            f"VARIANT: {meta.variant} | POLICY: {policy} | MODE: {mode}"
                        )
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
                        _write_text(dbg_dir / f"{name}_{policy}_{mode}.debug.txt", "\n".join(dbg_lines))

                report_lines.append("")

            report_lines.append("=" * 70)
            report_lines.append("")

        report_lines.append("GLOBAL SUMMARY (micro-averaged over all datasets)")
        report_lines.append("-" * 70)

        for policy in selected_policies:
            for mode, _ in selected_modes:
                a = global_agg[(policy, mode)]
                report_lines.append(
                    f"POLICY {policy:8s} | MODE {mode:8s} | "
                    f"TP={a.tp:4d} FP={a.fp:4d} FN={a.fn:4d} | "
                    f"P={a.precision():.3f} R={a.recall():.3f} F1={a.f1():.3f}"
                )

        _write_text(out_path, "\n".join(report_lines))
        print(f"Wrote: {out_path}")

        if args.debug:
            print(f"Wrote debug files: {dbg_dir}")

        if args.label_report:
            for policy in selected_policies:
                for mode, _ in selected_modes:
                    out_lbl = result_dir / f"ALL_labels_{policy}_{mode}.txt"
                    txt = _format_label_report(
                        label_hits_by_run[(policy, mode)],
                        policy=policy,
                        mode=mode,
                        max_items_per_section=max(1, int(args.label_report_max)),
                    )
                    _write_text(out_lbl, txt)
                    print(f"Wrote: {out_lbl}")

        dataset_csv_rows: List[Dict[str, object]] = []
        for row in dataset_rows:
            dataset_csv_rows.append(
                {
                    "dataset": row.dataset,
                    "dataset_index": row.dataset_index,
                    "domain": row.domain,
                    "structure": row.structure,
                    "variant": row.variant,
                    "policy": row.policy,
                    "mode": row.mode,
                    "tp": row.tp,
                    "fp": row.fp,
                    "fn": row.fn,
                    "precision": f"{row.precision:.6f}",
                    "recall": f"{row.recall:.6f}",
                    "f1": f"{row.f1:.6f}",
                }
            )

        _write_csv(
            result_dir / "metrics_dataset.csv",
            dataset_csv_rows,
            [
                "dataset",
                "dataset_index",
                "domain",
                "structure",
                "variant",
                "policy",
                "mode",
                "tp",
                "fp",
                "fn",
                "precision",
                "recall",
                "f1",
            ],
        )
        print(f"Wrote: {result_dir / 'metrics_dataset.csv'}")

        overall_rows = _aggregate_rows(dataset_rows, ["policy", "mode"])
        _write_csv(
            result_dir / "metrics_overall.csv",
            overall_rows,
            ["policy", "mode", "tp", "fp", "fn", "precision", "recall", "f1"],
        )
        print(f"Wrote: {result_dir / 'metrics_overall.csv'}")

        domain_rows = _aggregate_rows(dataset_rows, ["policy", "mode", "domain"])
        _write_csv(
            result_dir / "metrics_domain.csv",
            domain_rows,
            ["policy", "mode", "domain", "tp", "fp", "fn", "precision", "recall", "f1"],
        )
        print(f"Wrote: {result_dir / 'metrics_domain.csv'}")

        structure_rows = _aggregate_rows(dataset_rows, ["policy", "mode", "structure"])
        _write_csv(
            result_dir / "metrics_structure.csv",
            structure_rows,
            ["policy", "mode", "structure", "tp", "fp", "fn", "precision", "recall", "f1"],
        )
        print(f"Wrote: {result_dir / 'metrics_structure.csv'}")

        domain_structure_rows = _aggregate_rows(dataset_rows, ["policy", "mode", "domain", "structure"])
        _write_csv(
            result_dir / "metrics_domain_structure.csv",
            domain_structure_rows,
            ["policy", "mode", "domain", "structure", "tp", "fp", "fn", "precision", "recall", "f1"],
        )
        print(f"Wrote: {result_dir / 'metrics_domain_structure.csv'}")

        label_overall_rows = _aggregate_label_rows(label_rows, ["policy", "mode", "label"])
        _write_csv(
            result_dir / "metrics_label.csv",
            label_overall_rows,
            ["policy", "mode", "label", "tp", "fp", "fn", "precision", "recall", "f1"],
        )
        print(f"Wrote: {result_dir / 'metrics_label.csv'}")

        label_domain_rows = _aggregate_label_rows(label_rows, ["policy", "mode", "domain", "label"])
        _write_csv(
            result_dir / "metrics_domain_label.csv",
            label_domain_rows,
            ["policy", "mode", "domain", "label", "tp", "fp", "fn", "precision", "recall", "f1"],
        )
        print(f"Wrote: {result_dir / 'metrics_domain_label.csv'}")

        label_structure_rows = _aggregate_label_rows(label_rows, ["policy", "mode", "structure", "label"])
        _write_csv(
            result_dir / "metrics_structure_label.csv",
            label_structure_rows,
            ["policy", "mode", "structure", "label", "tp", "fp", "fn", "precision", "recall", "f1"],
        )
        print(f"Wrote: {result_dir / 'metrics_structure_label.csv'}")

        label_domain_structure_rows = _aggregate_label_rows(
            label_rows,
            ["policy", "mode", "domain", "structure", "label"],
        )
        _write_csv(
            result_dir / "metrics_domain_structure_label.csv",
            label_domain_structure_rows,
            ["policy", "mode", "domain", "structure", "label", "tp", "fp", "fn", "precision", "recall", "f1"],
        )
        print(f"Wrote: {result_dir / 'metrics_domain_structure_label.csv'}")

    finally:
        _restore_config(snap)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())