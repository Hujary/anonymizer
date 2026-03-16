from __future__ import annotations

import argparse
import csv
import statistics
import sys
import time
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
from pipeline.anonymisieren import erkenne

from evaluation.script.eval_single import (
    EvalCounts,
    Miss,
    POLICY_SPECS,
    _apply_policy,
    _evaluate,
    _format_misses,
    _format_per_label,
    _parse_gold,
    _policy_labels_for_mode,
    _read_json,
    _read_text,
    _resolve_paths,
    _restore_config,
    _set_config_for_mode,
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
    mode: str
    tp: int
    fp: int
    fn: int
    precision: float
    recall: float
    f1: float


@dataclass
class RuntimeAgg:
    samples_ms: List[float]

    def __init__(self) -> None:
        self.samples_ms = []

    def add_many(self, values: List[float]) -> None:
        self.samples_ms.extend(values)

    def count(self) -> int:
        return len(self.samples_ms)

    def mean(self) -> float:
        if not self.samples_ms:
            return 0.0
        return sum(self.samples_ms) / len(self.samples_ms)

    def median(self) -> float:
        if not self.samples_ms:
            return 0.0
        return float(statistics.median(self.samples_ms))

    def minimum(self) -> float:
        if not self.samples_ms:
            return 0.0
        return min(self.samples_ms)

    def maximum(self) -> float:
        if not self.samples_ms:
            return 0.0
        return max(self.samples_ms)

    def stddev(self) -> float:
        if len(self.samples_ms) < 2:
            return 0.0
        return float(statistics.pstdev(self.samples_ms))


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
    mode: str,
    postprocess_enabled: bool,
    max_items_per_section: int,
) -> str:
    lines: List[str] = []
    lines.append(
        f"LABEL REPORT | POLICY: {policy} | MODE: {mode} | "
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


def _format_short_summary(mode: str, total: EvalCounts) -> str:
    return (
        f"MODE {mode:8s} | "
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
            "mode": row.mode,
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
                "mode": row.mode,
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
            "mode",
            "tp",
            "fp",
            "fn",
            "precision",
            "recall",
            "f1",
        ],
    )

    overall_rows = _aggregate_rows(dataset_rows, ["policy", "mode"])
    _write_csv(
        csv_dir / "overall.csv",
        overall_rows,
        ["policy", "mode", "tp", "fp", "fn", "precision", "recall", "f1"],
    )

    domain_rows = _aggregate_rows(dataset_rows, ["policy", "mode", "domain"])
    _write_csv(
        csv_dir / "domain.csv",
        domain_rows,
        ["policy", "mode", "domain", "tp", "fp", "fn", "precision", "recall", "f1"],
    )

    structure_rows = _aggregate_rows(dataset_rows, ["policy", "mode", "structure"])
    _write_csv(
        csv_dir / "structure.csv",
        structure_rows,
        ["policy", "mode", "structure", "tp", "fp", "fn", "precision", "recall", "f1"],
    )

    domain_structure_rows = _aggregate_rows(dataset_rows, ["policy", "mode", "domain", "structure"])
    _write_csv(
        csv_dir / "domain_structure.csv",
        domain_structure_rows,
        ["policy", "mode", "domain", "structure", "tp", "fp", "fn", "precision", "recall", "f1"],
    )

    label_overall_rows = _aggregate_label_rows(label_rows, ["policy", "mode", "label"])
    _write_csv(
        csv_dir / "label.csv",
        label_overall_rows,
        ["policy", "mode", "label", "tp", "fp", "fn", "precision", "recall", "f1"],
    )

    label_domain_rows = _aggregate_label_rows(label_rows, ["policy", "mode", "domain", "label"])
    _write_csv(
        csv_dir / "domain_label.csv",
        label_domain_rows,
        ["policy", "mode", "domain", "label", "tp", "fp", "fn", "precision", "recall", "f1"],
    )

    label_structure_rows = _aggregate_label_rows(label_rows, ["policy", "mode", "structure", "label"])
    _write_csv(
        csv_dir / "structure_label.csv",
        label_structure_rows,
        ["policy", "mode", "structure", "label", "tp", "fp", "fn", "precision", "recall", "f1"],
    )

    label_domain_structure_rows = _aggregate_label_rows(
        label_rows,
        ["policy", "mode", "domain", "structure", "label"],
    )
    _write_csv(
        csv_dir / "domain_structure_label.csv",
        label_domain_structure_rows,
        ["policy", "mode", "domain", "structure", "label", "tp", "fp", "fn", "precision", "recall", "f1"],
    )


def _entity_matches_policy(acceptable_labels: Set[str], allowed_labels: Set[str]) -> bool:
    if not allowed_labels:
        return False
    return bool(acceptable_labels.intersection(allowed_labels))


def _entity_matches_mode(expected_sources: Set[str], mode_sources: Set[str]) -> bool:
    if not expected_sources:
        return True
    return bool(expected_sources.intersection(mode_sources))


def _format_counter(counter: Dict[str, int]) -> str:
    if not counter:
        return "-"
    parts: List[str] = []
    for key in sorted(counter.keys()):
        parts.append(f"{key}={counter[key]}")
    return ", ".join(parts)


def _build_runtime_profile(
    *,
    eval_root: Path,
    dataset_names: List[str],
    policy: str,
    selected_modes: List[Tuple[str, Set[str]]],
) -> Dict[str, object]:
    total_chars = 0
    policy_entity_count = 0
    policy_label_counter: Dict[str, int] = defaultdict(int)

    mode_entity_counts: Dict[str, int] = {mode_name: 0 for mode_name, _ in selected_modes}
    mode_label_counters: Dict[str, Dict[str, int]] = {
        mode_name: defaultdict(int) for mode_name, _ in selected_modes
    }

    allowed_combined = _policy_labels_for_mode(policy, "combined")

    for dataset_name in dataset_names:
        text, gold_entities = _load_gold_entities(eval_root, dataset_name)
        total_chars += len(text)

        for entity in gold_entities:
            acceptable_labels = set(getattr(entity, "acceptable_labels", set()) or set())
            primary_label = str(getattr(entity, "primary_label", "") or "").strip().upper()
            expected_sources = set(getattr(entity, "expected_sources", set()) or set())

            if _entity_matches_policy(acceptable_labels, allowed_combined):
                policy_entity_count += 1
                if primary_label:
                    policy_label_counter[primary_label] += 1

            for mode_name, mode_sources in selected_modes:
                allowed_mode_labels = _policy_labels_for_mode(policy, mode_name)

                if not _entity_matches_policy(acceptable_labels, allowed_mode_labels):
                    continue

                if not _entity_matches_mode(expected_sources, mode_sources):
                    continue

                mode_entity_counts[mode_name] += 1
                if primary_label:
                    mode_label_counters[mode_name][primary_label] += 1

    avg_chars = (total_chars / len(dataset_names)) if dataset_names else 0.0

    return {
        "dataset_count": len(dataset_names),
        "total_chars": total_chars,
        "avg_chars": avg_chars,
        "policy_entity_count": policy_entity_count,
        "policy_label_counter": dict(policy_label_counter),
        "mode_entity_counts": mode_entity_counts,
        "mode_label_counters": {k: dict(v) for k, v in mode_label_counters.items()},
    }


def _measure_runtime_ms(text: str, *, mode: str, runs: int) -> List[float]:
    _set_config_for_mode(mode)

    try:
        erkenne(text)
    except Exception:
        return []

    samples: List[float] = []
    n = max(1, int(runs))

    for _ in range(n):
        t0 = time.perf_counter()
        erkenne(text)
        t1 = time.perf_counter()
        samples.append((t1 - t0) * 1000.0)

    return samples


def _format_runtime_line(mode_name: str, agg: RuntimeAgg) -> str:
    return (
        f"MODE {mode_name:8s} | "
        f"samples={agg.count():4d} | "
        f"mean={agg.mean():8.3f} ms | "
        f"median={agg.median():8.3f} ms | "
        f"min={agg.minimum():8.3f} ms | "
        f"max={agg.maximum():8.3f} ms | "
        f"std={agg.stddev():8.3f} ms"
    )


def _build_runtime_report(
    *,
    policy: str,
    postprocess_enabled: bool,
    runtime_runs: int,
    profile: Dict[str, object],
    runtime_aggs: Dict[str, RuntimeAgg],
) -> str:
    lines: List[str] = []

    dataset_count = int(profile.get("dataset_count", 0))
    total_chars = int(profile.get("total_chars", 0))
    avg_chars = float(profile.get("avg_chars", 0.0))
    policy_entity_count = int(profile.get("policy_entity_count", 0))
    policy_label_counter = dict(profile.get("policy_label_counter", {}) or {})
    mode_entity_counts = dict(profile.get("mode_entity_counts", {}) or {})
    mode_label_counters = dict(profile.get("mode_label_counters", {}) or {})

    lines.append("RUNTIME REPORT")
    lines.append("=" * 80)
    lines.append(f"POLICY: {policy}")
    lines.append(f"POSTPROCESSING: {'on' if postprocess_enabled else 'off'}")
    lines.append(f"DATASETS: {dataset_count}")
    lines.append(f"RUNTIME RUNS PER TEXT: {max(1, int(runtime_runs))}")
    lines.append("MEASUREMENT: pure execution time of erkenne(text)")
    lines.append("WARM-UP: one untimed warm-up run per text and mode")
    lines.append("")

    lines.append("CORPUS PROFILE")
    lines.append("-" * 80)
    lines.append(f"TOTAL CHARACTERS: {total_chars}")
    lines.append(f"AVERAGE TEXT LENGTH: {avg_chars:.1f} characters")
    lines.append(f"POLICY-RELEVANT GOLD ENTITIES: {policy_entity_count}")
    lines.append(f"LABEL DISTRIBUTION: {_format_counter(policy_label_counter)}")
    lines.append("")

    lines.append("MODE-SPECIFIC ENTITY PROFILE")
    lines.append("-" * 80)
    for mode_name in ("regex", "ner", "combined"):
        if mode_name not in runtime_aggs:
            continue
        entity_count = int(mode_entity_counts.get(mode_name, 0))
        label_counter = dict(mode_label_counters.get(mode_name, {}) or {})
        lines.append(
            f"MODE {mode_name:8s} | entities={entity_count:4d} | "
            f"labels={_format_counter(label_counter)}"
        )
    lines.append("")

    lines.append("RUNTIME SUMMARY")
    lines.append("-" * 80)
    for mode_name in ("regex", "ner", "combined"):
        if mode_name not in runtime_aggs:
            continue
        lines.append(_format_runtime_line(mode_name, runtime_aggs[mode_name]))
    lines.append("")

    if "combined" in runtime_aggs:
        combined = runtime_aggs["combined"]
        lines.append("COMBINED MODE (relevant for interactive usage)")
        lines.append("-" * 80)
        lines.append(f"AVERAGE PROCESSING TIME: {combined.mean():.3f} ms")
        lines.append(f"MEDIAN PROCESSING TIME: {combined.median():.3f} ms")
        lines.append(f"MINIMUM PROCESSING TIME: {combined.minimum():.3f} ms")
        lines.append(f"MAXIMUM PROCESSING TIME: {combined.maximum():.3f} ms")
        lines.append(f"STANDARD DEVIATION: {combined.stddev():.3f} ms")

    return "\n".join(lines).rstrip() + "\n"


def _run_variant(
    *,
    eval_root: Path,
    result_root: Path,
    dataset_names: List[str],
    selected_modes: List[Tuple[str, Set[str]]],
    selected_policies: List[str],
    debug: bool,
    show_tp: bool,
    per_label: bool,
    ctx: int,
    max_lines: int,
    label_report: bool,
    label_report_max: int,
    postprocess_enabled: bool,
    runtime_runs: int,
) -> None:
    variant_name = "postprocess_on" if postprocess_enabled else "postprocess_off"
    variant_root = result_root / variant_name
    variant_root.mkdir(parents=True, exist_ok=True)

    debug_dir = variant_root / "debug_all"

    config.set("use_ner_postprocessing", postprocess_enabled)

    for policy in selected_policies:
        _apply_policy(policy)

        policy_dir = variant_root / policy
        labels_dir = policy_dir / "labels"
        csv_dir = policy_dir / "csv"

        policy_dir.mkdir(parents=True, exist_ok=True)
        labels_dir.mkdir(parents=True, exist_ok=True)
        csv_dir.mkdir(parents=True, exist_ok=True)

        report_lines: List[str] = []
        policy_dataset_rows: List[DatasetRunRow] = []
        policy_label_rows: List[Dict[str, object]] = []

        policy_global_agg: Dict[str, MetricAgg] = {
            mode_name: MetricAgg()
            for mode_name, _ in selected_modes
        }

        runtime_aggs: Dict[str, RuntimeAgg] = {
            mode_name: RuntimeAgg()
            for mode_name, _ in selected_modes
        }

        runtime_profile = _build_runtime_profile(
            eval_root=eval_root,
            dataset_names=dataset_names,
            policy=policy,
            selected_modes=selected_modes,
        )

        policy_label_hits_by_mode: Dict[str, Dict[str, Dict[str, List[str]]]] = {}
        if label_report:
            for mode_name, _ in selected_modes:
                policy_label_hits_by_mode[mode_name] = defaultdict(
                    lambda: {"TP": [], "PARTIAL": [], "FN": [], "FP": []}
                )

        for dataset_name in dataset_names:
            meta = _dataset_meta(dataset_name)
            text, gold_entities = _load_gold_entities(eval_root, dataset_name)

            report_lines.append(f"DATASET: {dataset_name}")
            report_lines.append(f"DOMAIN: {meta.domain}")
            report_lines.append(f"STRUCTURE: {meta.structure}")
            report_lines.append(f"POSTPROCESSING: {'on' if postprocess_enabled else 'off'}")
            report_lines.append("")
            report_lines.append(f"POLICY {policy}")

            for mode_name, sources in selected_modes:
                runtime_samples = _measure_runtime_ms(
                    text,
                    mode=mode_name,
                    runs=runtime_runs,
                )
                runtime_aggs[mode_name].add_many(runtime_samples)

                total, by_label, misses = _evaluate(
                    text,
                    gold_entities,
                    mode=mode_name,
                    mode_sources=set(sources),
                    policy_name=policy,
                    eval_root=eval_root,
                )

                policy_global_agg[mode_name].add(total)

                policy_dataset_rows.append(
                    DatasetRunRow(
                        dataset=dataset_name,
                        dataset_index=meta.dataset_index,
                        domain=meta.domain,
                        structure=meta.structure,
                        variant=meta.variant,
                        policy=policy,
                        mode=mode_name,
                        tp=total.tp,
                        fp=total.fp,
                        fn=total.fn,
                        precision=total.precision(),
                        recall=total.recall(),
                        f1=total.f1(),
                    )
                )

                report_lines.append(_format_short_summary(mode_name, total))

                if per_label:
                    report_lines.append("")
                    report_lines.append(
                        f"PER-LABEL ({policy} | {mode_name} | "
                        f"{'postprocess_on' if postprocess_enabled else 'postprocess_off'})"
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
                            "mode": mode_name,
                            "label": label,
                            "tp": counts.tp,
                            "fp": counts.fp,
                            "fn": counts.fn,
                        }
                    )

                if label_report:
                    bucket = policy_label_hits_by_mode[mode_name]
                    for miss in misses:
                        miss_label = str(miss.label or "").strip().upper() or "?"
                        miss_kind = str(miss.kind or "").strip().upper()

                        if miss_kind not in ("TP", "FN", "FP", "PARTIAL"):
                            continue

                        bucket[miss_label][miss_kind].append(_miss_line(dataset_name, miss))

                if debug:
                    debug_lines: List[str] = []
                    debug_lines.append(
                        f"DATASET: {dataset_name} | DOMAIN: {meta.domain} | STRUCTURE: {meta.structure} | "
                        f"VARIANT: {meta.variant} | POLICY: {policy} | MODE: {mode_name} | "
                        f"POSTPROCESSING: {'on' if postprocess_enabled else 'off'}"
                    )

                    if runtime_samples:
                        debug_lines.append(
                            f"RUNTIME | samples={len(runtime_samples)} | "
                            f"mean={sum(runtime_samples) / len(runtime_samples):.3f} ms | "
                            f"min={min(runtime_samples):.3f} ms | "
                            f"max={max(runtime_samples):.3f} ms"
                        )

                    debug_lines.append(_format_short_summary(mode_name, total))
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
                        debug_dir / f"{dataset_name}_{policy}_{mode_name}.debug.txt",
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

        for mode_name, _ in selected_modes:
            agg = policy_global_agg[mode_name]
            report_lines.append(
                f"POLICY {policy:8s} | MODE {mode_name:8s} | "
                f"TP={agg.tp:4d} FP={agg.fp:4d} FN={agg.fn:4d} | "
                f"P={agg.precision():.3f} R={agg.recall():.3f} F1={agg.f1():.3f}"
            )

        _write_text(policy_dir / "report.txt", "\n".join(report_lines))
        print(f"Wrote: {policy_dir / 'report.txt'}")

        runtime_report_text = _build_runtime_report(
            policy=policy,
            postprocess_enabled=postprocess_enabled,
            runtime_runs=runtime_runs,
            profile=runtime_profile,
            runtime_aggs=runtime_aggs,
        )
        _write_text(policy_dir / "runtime.txt", runtime_report_text)
        print(f"Wrote: {policy_dir / 'runtime.txt'}")

        if label_report:
            for mode_name, _ in selected_modes:
                label_report_text = _format_label_report(
                    policy_label_hits_by_mode[mode_name],
                    policy=policy,
                    mode=mode_name,
                    postprocess_enabled=postprocess_enabled,
                    max_items_per_section=max(1, int(label_report_max)),
                )
                _write_text(labels_dir / f"{mode_name}.txt", label_report_text)
                print(f"Wrote: {labels_dir / f'{mode_name}.txt'}")

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
        print(f"Wrote debug files: {debug_dir}")


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
    parser.add_argument("--runtime-runs", type=int, default=5, help="Untimed warm-up + n timed runs per text and mode")
    parser.add_argument(
        "--policies",
        nargs="*",
        default=["minimal", "secure"],
        choices=sorted(POLICY_SPECS.keys()),
        help="Policies to evaluate",
    )
    parser.add_argument(
        "--modes",
        nargs="*",
        default=["regex", "ner", "combined"],
        choices=["regex", "ner", "combined"],
        help="Modes to evaluate",
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

    selected_modes = [mode_tuple for mode_tuple in MODES if mode_tuple[0] in set(args.modes)]
    if not selected_modes:
        raise SystemExit("No modes selected.")

    selected_policies = [policy for policy in args.policies if policy in POLICY_SPECS]
    if not selected_policies:
        raise SystemExit("No policies selected.")

    snapshot = _snapshot_config()

    try:
        run_variants: List[bool]

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
                selected_modes=selected_modes,
                selected_policies=selected_policies,
                debug=bool(args.debug),
                show_tp=bool(args.show_tp),
                per_label=bool(args.per_label),
                ctx=int(args.ctx),
                max_lines=int(args.max_lines),
                label_report=bool(args.label_report),
                label_report_max=int(args.label_report_max),
                postprocess_enabled=postprocess_enabled,
                runtime_runs=int(args.runtime_runs),
            )

    finally:
        _restore_config(snapshot)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())