from __future__ import annotations

import argparse
import csv
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

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
    _result_model_slug,
    _set_runtime_ner_config,
    _snapshot_config,
)


NER_VARIANTS: List[Tuple[str, str]] = [
    ("spacy", "de_core_news_lg"),
    ("flair", "flair/ner-german-large"),
]

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
        denominator = self.tp + self.fp
        return (self.tp / denominator) if denominator else 0.0

    def recall(self) -> float:
        denominator = self.tp + self.fn
        return (self.tp / denominator) if denominator else 0.0

    def f1(self) -> float:
        precision = self.precision()
        recall = self.recall()
        denominator = precision + recall
        return (2.0 * precision * recall / denominator) if denominator else 0.0


@dataclass(frozen=True)
class DatasetRunRow:
    dataset: str
    dataset_index: int
    domain: str
    structure: str
    variant: int
    policy: str
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
    text_path, gold_path = _resolve_paths(eval_root, name)

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

    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _miss_line(dataset: str, miss: Miss) -> str:
    if miss.kind == "PARTIAL":
        gold_text = (miss.text or "").replace("\n", "\\n").replace("\r", "\\r")
        pred_text = (miss.pred_text or "").replace("\n", "\\n").replace("\r", "\\r")
        pred_source = miss.pred_source or "?"
        pred_start = miss.pred_start if miss.pred_start is not None else -1
        pred_end = miss.pred_end if miss.pred_end is not None else -1

        return (
            f"{dataset} gold:{miss.start}:{miss.end} [{miss.source}] '{gold_text}' "
            f"<- pred:{pred_source}:{pred_start}:{pred_end} '{pred_text}'"
        )

    text = (miss.text or "").replace("\n", "\\n").replace("\r", "\\r")
    return f"{dataset} {miss.start}:{miss.end} [{miss.source}] '{text}'"


def _format_label_report(
    label_hits: Dict[str, Dict[str, List[str]]],
    *,
    policy: str,
    postprocess_enabled: bool,
    max_items_per_section: int,
) -> str:
    lines: List[str] = []
    lines.append(
        f"LABEL REPORT | POLICY: {policy} | "
        f"NER_BACKEND: {config.get('ner_backend', 'spacy')} | "
        f"NER_MODEL: {config.get('ner_model', '')} | "
        f"POSTPROCESSING: {'on' if postprocess_enabled else 'off'}"
    )
    lines.append("-" * 80)
    lines.append("")

    for label in sorted(label_hits.keys()):
        sections = label_hits[label]
        lines.append(label)
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


def _format_short_summary(total: EvalCounts) -> str:
    return (
        f"TP={total.tp} FP={total.fp} FN={total.fn} | "
        f"P={total.precision():.3f} R={total.recall():.3f} F1={total.f1():.3f}"
    )


def _parse_dataset_index(name: str) -> int:
    parts = name.split("_")
    if len(parts) != 2:
        raise ValueError(f"Unexpected dataset name: {name}")

    index = int(parts[1])
    if index < 1 or index > 30:
        raise ValueError(f"Dataset index out of range: {name}")

    return index


def _dataset_meta(name: str) -> DatasetMeta:
    index = _parse_dataset_index(name)

    zero_based = index - 1
    domain_index = zero_based // 6
    in_domain = zero_based % 6
    structure_index = in_domain // 2
    variant = (in_domain % 2) + 1

    return DatasetMeta(
        dataset=name,
        dataset_index=index,
        domain=DOMAINS[domain_index],
        structure=STRUCTURES[structure_index],
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
        }

        key = tuple(row_dict[key_name] for key_name in group_keys)

        if key not in buckets:
            buckets[key] = MetricAgg()
            key_values[key] = {key_name: row_dict[key_name] for key_name in group_keys}

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
        key = tuple(row[key_name] for key_name in group_keys)

        if key not in buckets:
            buckets[key] = MetricAgg()
            key_values[key] = {key_name: row[key_name] for key_name in group_keys}

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


def _build_dataset_csv_rows(rows: List[DatasetRunRow]) -> List[Dict[str, object]]:
    out: List[Dict[str, object]] = []

    for row in rows:
        out.append(
            {
                "dataset": row.dataset,
                "dataset_index": row.dataset_index,
                "domain": row.domain,
                "structure": row.structure,
                "variant": row.variant,
                "policy": row.policy,
                "tp": row.tp,
                "fp": row.fp,
                "fn": row.fn,
                "precision": f"{row.precision:.6f}",
                "recall": f"{row.recall:.6f}",
                "f1": f"{row.f1:.6f}",
            }
        )

    return out


def _write_policy_csv_files(
    csv_dir: Path,
    dataset_rows: List[DatasetRunRow],
    label_rows: List[Dict[str, object]],
) -> None:
    dataset_csv_rows = _build_dataset_csv_rows(dataset_rows)

    _write_csv(
        csv_dir / "dataset.csv",
        dataset_csv_rows,
        [
            "dataset",
            "dataset_index",
            "domain",
            "structure",
            "variant",
            "policy",
            "tp",
            "fp",
            "fn",
            "precision",
            "recall",
            "f1",
        ],
    )

    overall_rows = _aggregate_rows(dataset_rows, ["policy"])
    _write_csv(
        csv_dir / "overall.csv",
        overall_rows,
        ["policy", "tp", "fp", "fn", "precision", "recall", "f1"],
    )

    domain_rows = _aggregate_rows(dataset_rows, ["policy", "domain"])
    _write_csv(
        csv_dir / "domain.csv",
        domain_rows,
        ["policy", "domain", "tp", "fp", "fn", "precision", "recall", "f1"],
    )

    structure_rows = _aggregate_rows(dataset_rows, ["policy", "structure"])
    _write_csv(
        csv_dir / "structure.csv",
        structure_rows,
        ["policy", "structure", "tp", "fp", "fn", "precision", "recall", "f1"],
    )

    domain_structure_rows = _aggregate_rows(dataset_rows, ["policy", "domain", "structure"])
    _write_csv(
        csv_dir / "domain_structure.csv",
        domain_structure_rows,
        ["policy", "domain", "structure", "tp", "fp", "fn", "precision", "recall", "f1"],
    )

    label_overall_rows = _aggregate_label_rows(label_rows, ["policy", "label"])
    _write_csv(
        csv_dir / "label.csv",
        label_overall_rows,
        ["policy", "label", "tp", "fp", "fn", "precision", "recall", "f1"],
    )

    label_domain_rows = _aggregate_label_rows(label_rows, ["policy", "domain", "label"])
    _write_csv(
        csv_dir / "domain_label.csv",
        label_domain_rows,
        ["policy", "domain", "label", "tp", "fp", "fn", "precision", "recall", "f1"],
    )

    label_structure_rows = _aggregate_label_rows(label_rows, ["policy", "structure", "label"])
    _write_csv(
        csv_dir / "structure_label.csv",
        label_structure_rows,
        ["policy", "structure", "label", "tp", "fp", "fn", "precision", "recall", "f1"],
    )

    label_domain_structure_rows = _aggregate_label_rows(
        label_rows,
        ["policy", "domain", "structure", "label"],
    )
    _write_csv(
        csv_dir / "domain_structure_label.csv",
        label_domain_structure_rows,
        ["policy", "domain", "structure", "label", "tp", "fp", "fn", "precision", "recall", "f1"],
    )


def _run_variant(
    *,
    eval_root: Path,
    result_root: Path,
    dataset_names: List[str],
    selected_policies: List[str],
    debug: bool,
    show_tp: bool,
    per_label: bool,
    ctx: int,
    max_lines: int,
    label_report: bool,
    label_report_max: int,
    postprocess_enabled: bool,
) -> None:
    model_slug = _result_model_slug()
    variant_root = result_root / model_slug / ("postprocess_on" if postprocess_enabled else "postprocess_off")
    variant_root.mkdir(parents=True, exist_ok=True)

    config.set("use_ner_postprocessing", postprocess_enabled)

    dataset_cache: Dict[str, Tuple[str, List[object]]] = {}
    for dataset_name in dataset_names:
        dataset_cache[dataset_name] = _load_gold_entities(eval_root, dataset_name)

    for policy in selected_policies:
        _apply_policy(policy)

        policy_dir = variant_root / policy
        labels_dir = policy_dir / "labels"
        csv_dir = policy_dir / "csv"
        debug_dir = policy_dir / "debug_all"

        policy_dir.mkdir(parents=True, exist_ok=True)
        labels_dir.mkdir(parents=True, exist_ok=True)
        csv_dir.mkdir(parents=True, exist_ok=True)
        if debug:
            debug_dir.mkdir(parents=True, exist_ok=True)

        report_lines: List[str] = []
        policy_dataset_rows: List[DatasetRunRow] = []
        policy_label_rows: List[Dict[str, object]] = []

        policy_global_agg = MetricAgg()

        policy_label_hits: Dict[str, Dict[str, List[str]]] = {}
        if label_report:
            policy_label_hits = defaultdict(lambda: {"TP": [], "PARTIAL": [], "FN": [], "FP": []})

        for dataset_name in dataset_names:
            meta = _dataset_meta(dataset_name)
            text, gold_entities = dataset_cache[dataset_name]

            report_lines.append(f"DATASET: {dataset_name}")
            report_lines.append(f"DOMAIN: {meta.domain}")
            report_lines.append(f"STRUCTURE: {meta.structure}")
            report_lines.append(f"NER_BACKEND: {config.get('ner_backend', 'spacy')}")
            report_lines.append(f"NER_MODEL: {config.get('ner_model', '')}")
            report_lines.append(f"POSTPROCESSING: {'on' if postprocess_enabled else 'off'}")
            report_lines.append("")
            report_lines.append(f"POLICY {policy}")

            total, by_label, misses = _evaluate(
                text,
                gold_entities,
                policy_name=policy,
                eval_root=eval_root,
            )

            policy_global_agg.add(total)

            policy_dataset_rows.append(
                DatasetRunRow(
                    dataset=dataset_name,
                    dataset_index=meta.dataset_index,
                    domain=meta.domain,
                    structure=meta.structure,
                    variant=meta.variant,
                    policy=policy,
                    tp=total.tp,
                    fp=total.fp,
                    fn=total.fn,
                    precision=total.precision(),
                    recall=total.recall(),
                    f1=total.f1(),
                )
            )

            report_lines.append(_format_short_summary(total))

            if per_label:
                report_lines.append("")
                report_lines.append(
                    f"PER-LABEL ({policy} | "
                    f"{'postprocess_on' if postprocess_enabled else 'postprocess_off'} | "
                    f"{config.get('ner_backend', 'spacy')} | "
                    f"{config.get('ner_model', '')})"
                )
                report_lines.extend(_format_per_label(by_label))
                report_lines.append("")

            for label in sorted(by_label.keys()):
                counts = by_label[label]
                policy_label_rows.append(
                    {
                        "dataset": dataset_name,
                        "dataset_index": meta.dataset_index,
                        "domain": meta.domain,
                        "structure": meta.structure,
                        "variant": meta.variant,
                        "policy": policy,
                        "label": label,
                        "tp": counts.tp,
                        "fp": counts.fp,
                        "fn": counts.fn,
                    }
                )

            if label_report:
                for miss in misses:
                    miss_label = str(miss.label or "").strip().upper() or "?"
                    miss_kind = str(miss.kind or "").strip().upper()

                    if miss_kind not in ("TP", "FN", "FP", "PARTIAL"):
                        continue

                    policy_label_hits[miss_label][miss_kind].append(_miss_line(dataset_name, miss))

            if debug:
                debug_lines: List[str] = []
                debug_lines.append(
                    f"DATASET: {dataset_name} | DOMAIN: {meta.domain} | STRUCTURE: {meta.structure} | "
                    f"VARIANT: {meta.variant} | POLICY: {policy} | "
                    f"NER_BACKEND: {config.get('ner_backend', 'spacy')} | "
                    f"NER_MODEL: {config.get('ner_model', '')} | "
                    f"POSTPROCESSING: {'on' if postprocess_enabled else 'off'}"
                )
                debug_lines.append(_format_short_summary(total))
                debug_lines.append("-" * 70)
                debug_lines.extend(
                    _format_misses(
                        text,
                        misses,
                        show_tp=show_tp,
                        ctx_radius=max(0, int(ctx)),
                        max_lines=max(1, int(max_lines)),
                    )
                )
                debug_lines.append("")

                _write_text(
                    debug_dir / f"{dataset_name}_{policy}.debug.txt",
                    "\n".join(debug_lines),
                )

            report_lines.append("")
            report_lines.append("=" * 70)
            report_lines.append("")

        if postprocess_enabled:
            report_lines.append("GLOBAL SUMMARY (micro-averaged over all datasets)")
        else:
            report_lines.append("GLOBAL SUMMARY (micro-averaged over all datasets) (no Postprocessing)")

        report_lines.append("-" * 70)
        report_lines.append(
            f"POLICY {policy:8s} | "
            f"TP={policy_global_agg.tp:4d} FP={policy_global_agg.fp:4d} FN={policy_global_agg.fn:4d} | "
            f"P={policy_global_agg.precision():.3f} R={policy_global_agg.recall():.3f} F1={policy_global_agg.f1():.3f}"
        )

        _write_text(policy_dir / "report.txt", "\n".join(report_lines))
        print(f"Wrote: {policy_dir / 'report.txt'}")

        if label_report:
            label_report_text = _format_label_report(
                policy_label_hits,
                policy=policy,
                postprocess_enabled=postprocess_enabled,
                max_items_per_section=max(1, int(label_report_max)),
            )
            _write_text(labels_dir / "combined.txt", label_report_text)
            print(f"Wrote: {labels_dir / 'combined.txt'}")

        _write_policy_csv_files(
            csv_dir=csv_dir,
            dataset_rows=policy_dataset_rows,
            label_rows=policy_label_rows,
        )
        print(f"Wrote: {csv_dir / 'dataset.csv'}")
        print(f"Wrote: {csv_dir / 'overall.csv'}")
        print(f"Wrote: {csv_dir / 'domain.csv'}")
        print(f"Wrote: {csv_dir / 'structure.csv'}")
        print(f"Wrote: {csv_dir / 'domain_structure.csv'}")
        print(f"Wrote: {csv_dir / 'label.csv'}")
        print(f"Wrote: {csv_dir / 'domain_label.csv'}")
        print(f"Wrote: {csv_dir / 'structure_label.csv'}")
        print(f"Wrote: {csv_dir / 'domain_structure_label.csv'}")

    if debug:
        print(f"Wrote debug files under: {variant_root}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--eval-root", default="evaluation")
    parser.add_argument("--debug", action="store_true", help="Write per-dataset debug files")
    parser.add_argument("--show-tp", action="store_true", help="Include TP list in debug files")
    parser.add_argument("--per-label", action="store_true", help="Include per-label stats per dataset in txt report")
    parser.add_argument("--ctx", type=int, default=20)
    parser.add_argument("--max-lines", type=int, default=200)
    parser.add_argument("--only", nargs="*", default=None, help="Run only these dataset basenames")
    parser.add_argument("--label-report", action="store_true", help="Write aggregated TP/PARTIAL/FN/FP label reports")
    parser.add_argument("--label-report-max", type=int, default=500)
    parser.add_argument(
        "--policies",
        nargs="*",
        default=["minimal", "secure"],
        choices=sorted(POLICY_SPECS.keys()),
        help="Policies to evaluate",
    )
    parser.add_argument(
        "--only-post",
        choices=["on", "off"],
        default=None,
        help="Optional: run only one variant instead of both",
    )
    args = parser.parse_args()

    eval_root = Path(args.eval_root)
    result_root = eval_root / "result"
    result_root.mkdir(parents=True, exist_ok=True)

    dataset_names = _discover_datasets(eval_root)

    if args.only:
        wanted = {value.strip() for value in args.only if value.strip()}
        dataset_names = [name for name in dataset_names if name in wanted]

    if not dataset_names:
        raise SystemExit("No datasets found (no gold json files).")

    selected_policies = [policy for policy in args.policies if policy in POLICY_SPECS]
    if not selected_policies:
        raise SystemExit("No policies selected.")

    snapshot = _snapshot_config()

    try:
        for ner_backend, ner_model in NER_VARIANTS:
            _set_runtime_ner_config(ner_backend, ner_model)

            if args.only_post == "on":
                run_variants = [True]
            elif args.only_post == "off":
                run_variants = [False]
            else:
                run_variants = [False, True]

            for postprocess_enabled in run_variants:
                _run_variant(
                    eval_root=eval_root,
                    result_root=result_root,
                    dataset_names=dataset_names,
                    selected_policies=selected_policies,
                    debug=bool(args.debug),
                    show_tp=bool(args.show_tp),
                    per_label=bool(args.per_label),
                    ctx=int(args.ctx),
                    max_lines=int(args.max_lines),
                    label_report=bool(args.label_report),
                    label_report_max=int(args.label_report_max),
                    postprocess_enabled=postprocess_enabled,
                )

    finally:
        _restore_config(snapshot)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())