from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

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

MODEL_SPECS: Dict[str, Dict[str, str]] = {
    "spacy": {
        "ner_backend": "spacy",
        "ner_model": "de_core_news_lg",
    },
    "flair": {
        "ner_backend": "flair",
        "ner_model": "flair/ner-german-large",
    },
}


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _norm_label(value: Any) -> str:
    return str(value or "").strip().upper()


def _normalize_label_list(values: List[str]) -> List[str]:
    out: List[str] = []
    seen: set[str] = set()

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


def _set_ner_runtime(model_key: str) -> None:
    key = str(model_key or "").strip().lower()

    if key not in MODEL_SPECS:
        raise ValueError(f"Unknown model key: {model_key}")

    spec = MODEL_SPECS[key]
    config.set("ner_backend", spec["ner_backend"])
    config.set("ner_model", spec["ner_model"])


def _snapshot_config() -> Dict[str, Any]:
    return {
        "flags": dict(config.get_flags() or {}),
        "ner_labels": list(config.get("ner_labels", []) or []),
        "regex_labels": list(config.get("regex_labels", []) or []),
        "ner_backend": str(config.get("ner_backend", "spacy") or "spacy"),
        "ner_model": str(config.get("ner_model", "") or ""),
        "debug_mask": bool(config.get("debug_mask", False)),
        "use_ner_postprocessing": config.get("use_ner_postprocessing", True),
    }


def _restore_config(snapshot: Dict[str, Any]) -> None:
    flags = snapshot.get("flags", {}) or {}
    config.set_flags(
        use_regex=bool(flags.get("use_regex", True)),
        use_ner=bool(flags.get("use_ner", True)),
        debug_mask=bool(flags.get("debug_mask", False)),
    )
    config.set("ner_labels", snapshot.get("ner_labels", []) or [])
    config.set("regex_labels", snapshot.get("regex_labels", []) or [])
    config.set("ner_backend", str(snapshot.get("ner_backend", "spacy") or "spacy"))
    config.set("ner_model", str(snapshot.get("ner_model", "") or ""))
    config.set("debug_mask", bool(snapshot.get("debug_mask", False)))
    config.set("use_ner_postprocessing", snapshot.get("use_ner_postprocessing", True))


def _discover_datasets(eval_root: Path) -> List[str]:
    gold_dir = eval_root / "datasets" / "gold"
    if not gold_dir.exists():
        return []
    return [p.stem for p in sorted(gold_dir.glob("*.json"))]


def _resolve_text_path(eval_root: Path, basename: str) -> Path:
    return eval_root / "datasets" / "data" / f"{basename}.txt"


def _is_hit_like(obj: Any) -> bool:
    if obj is None:
        return False

    if isinstance(obj, dict):
        return (
            ("start" in obj and ("ende" in obj or "end" in obj) and "label" in obj)
            or ("s" in obj and "e" in obj and "label" in obj)
        )

    return hasattr(obj, "start") and hasattr(obj, "label") and (hasattr(obj, "ende") or hasattr(obj, "end"))


def _extract_hits_count(value: Any) -> int:
    if value is None:
        return 0

    if isinstance(value, dict):
        direct_keys = [
            "hits",
            "treffer",
            "results",
            "detections",
            "entities",
            "recognized",
            "recognized_hits",
            "resolved_hits",
        ]
        for key in direct_keys:
            if key in value:
                count = _extract_hits_count(value[key])
                if count > 0:
                    return count

        best = 0
        for sub_value in value.values():
            best = max(best, _extract_hits_count(sub_value))
        return best

    if isinstance(value, (list, tuple)):
        if not value:
            return 0

        if all(_is_hit_like(item) for item in value):
            return len(value)

        best = 0
        for item in value:
            best = max(best, _extract_hits_count(item))
        return best

    if hasattr(value, "hits"):
        return _extract_hits_count(getattr(value, "hits"))

    if hasattr(value, "treffer"):
        return _extract_hits_count(getattr(value, "treffer"))

    if hasattr(value, "results"):
        return _extract_hits_count(getattr(value, "results"))

    if hasattr(value, "detections"):
        return _extract_hits_count(getattr(value, "detections"))

    return 0


def _dataset_meta(dataset_name: str) -> Tuple[str, str]:
    try:
        index = int(dataset_name.split("_")[-1])
    except Exception:
        return "Unknown", "unknown"

    domains = [
        "Supporttickets",
        "E-Mail",
        "HR-Dokumente",
        "Verträge",
        "Chats",
    ]

    domain_idx = (index - 1) // 6
    within = (index - 1) % 6

    domain = domains[domain_idx] if 0 <= domain_idx < len(domains) else "Unknown"

    if within in (0, 1):
        structure = "structured"
    elif within in (2, 3):
        structure = "regular"
    else:
        structure = "unstructured"

    return domain, structure


def _measure_erkenne_runtime_ms(
    *,
    text: str,
    runs: int,
) -> Tuple[List[float], int]:
    values: List[float] = []

    warmup_result = erkenne(text)
    last_count = _extract_hits_count(warmup_result)

    for _ in range(max(1, int(runs))):
        t0 = time.perf_counter_ns()
        result = erkenne(text)
        t1 = time.perf_counter_ns()

        values.append((t1 - t0) / 1_000_000.0)
        last_count = _extract_hits_count(result)

    return values, last_count


def _format_dataset_runtime_line(
    dataset_name: str,
    domain: str,
    structure: str,
    char_count: int,
    hit_count: int,
    values_ms: List[float],
) -> str:
    mean_ms = statistics.mean(values_ms) if values_ms else 0.0
    median_ms = statistics.median(values_ms) if values_ms else 0.0
    min_ms = min(values_ms) if values_ms else 0.0
    max_ms = max(values_ms) if values_ms else 0.0
    delta_ms = max_ms - min_ms
    stdev_ms = statistics.pstdev(values_ms) if len(values_ms) > 1 else 0.0
    mean_ms_per_label = (mean_ms / hit_count) if hit_count else 0.0

    return (
        f"{dataset_name:<12} | "
        f"{domain:<13} | "
        f"{structure:<12} | "
        f"chars={char_count:>5} | "
        f"labels={hit_count:>3} | "
        f"mean_ms={mean_ms:>8.3f} | "
        f"median_ms={median_ms:>8.3f} | "
        f"min_ms={min_ms:>8.3f} | "
        f"max_ms={max_ms:>8.3f} | "
        f"delta_ms={delta_ms:>8.3f} | "
        f"stdev_ms={stdev_ms:>8.3f} | "
        f"ms_per_label={mean_ms_per_label:>7.3f}"
    )


def _format_global_runtime_summary(
    *,
    all_values_ms: List[float],
    per_dataset_means_ms: List[float],
    dataset_count: int,
    total_chars: int,
    total_hits: int,
    runs_per_dataset: int,
) -> str:
    mean_all = statistics.mean(all_values_ms) if all_values_ms else 0.0
    median_all = statistics.median(all_values_ms) if all_values_ms else 0.0
    min_all = min(all_values_ms) if all_values_ms else 0.0
    max_all = max(all_values_ms) if all_values_ms else 0.0
    delta_all = max_all - min_all
    stdev_all = statistics.pstdev(all_values_ms) if len(all_values_ms) > 1 else 0.0

    mean_dataset_mean = statistics.mean(per_dataset_means_ms) if per_dataset_means_ms else 0.0
    median_dataset_mean = statistics.median(per_dataset_means_ms) if per_dataset_means_ms else 0.0
    min_dataset_mean = min(per_dataset_means_ms) if per_dataset_means_ms else 0.0
    max_dataset_mean = max(per_dataset_means_ms) if per_dataset_means_ms else 0.0
    delta_dataset_mean = max_dataset_mean - min_dataset_mean
    stdev_dataset_mean = statistics.pstdev(per_dataset_means_ms) if len(per_dataset_means_ms) > 1 else 0.0

    total_runtime_ms = sum(all_values_ms)
    total_processed_labels_across_runs = total_hits * runs_per_dataset
    average_runtime_per_resolved_label_ms = (
        total_runtime_ms / total_processed_labels_across_runs
        if total_processed_labels_across_runs
        else 0.0
    )

    lines = [
        "",
        "GLOBAL RUNTIME SUMMARY",
        "======================================================================",
        f"datasets={dataset_count}",
        f"runs_per_dataset={runs_per_dataset}",
        f"total_runs={len(all_values_ms)}",
        f"total_chars={total_chars}",
        f"total_resolved_labels={total_hits}",
        "",
        "ALL RUNS",
        f"mean_ms={mean_all:.3f}",
        f"median_ms={median_all:.3f}",
        f"min_ms={min_all:.3f}",
        f"max_ms={max_all:.3f}",
        f"delta_ms={delta_all:.3f}",
        f"stdev_ms={stdev_all:.3f}",
        "",
        "PER-DATASET MEAN RUNTIMES",
        f"mean_ms={mean_dataset_mean:.3f}",
        f"median_ms={median_dataset_mean:.3f}",
        f"min_ms={min_dataset_mean:.3f}",
        f"max_ms={max_dataset_mean:.3f}",
        f"delta_ms={delta_dataset_mean:.3f}",
        f"stdev_ms={stdev_dataset_mean:.3f}",
        "",
        "LABEL-NORMALIZED RUNTIME",
        f"estimated_total_runtime_ms={total_runtime_ms:.3f}",
        f"resolved_labels_across_all_datasets={total_hits}",
        f"resolved_labels_across_all_runs={total_processed_labels_across_runs}",
        f"average_runtime_per_resolved_label_ms={average_runtime_per_resolved_label_ms:.3f}",
        "",
    ]
    return "\n".join(lines)


def _run_model_benchmark(
    *,
    eval_root: Path,
    result_root: Path,
    dataset_names: List[str],
    model_key: str,
    runs: int,
) -> Path:
    model_spec = MODEL_SPECS[model_key]

    _set_ner_runtime(model_key)
    _apply_policy("secure")
    config.set("use_ner_postprocessing", True)

    model_result_dir = result_root / "runtime_secure_postprocess_on"
    model_result_dir.mkdir(parents=True, exist_ok=True)

    output_path = model_result_dir / f"{model_key}_times.txt"

    lines: List[str] = [
        "RUNTIME REPORT",
        "======================================================================",
        f"policy=secure",
        f"postprocessing=on",
        f"ner_backend={model_spec['ner_backend']}",
        f"ner_model={model_spec['ner_model']}",
        f"runs_per_dataset={max(1, int(runs))}",
        "measurement=pure execution time of erkenne(text)",
        "warmup=one untimed warm-up run per text",
        "",
        "DATASET      | DOMAIN        | STRUCTURE    | CHARS | LABELS |  MEAN_MS | MEDIAN_MS |   MIN_MS |   MAX_MS | DELTA_MS | STDEV_MS | MS_PER_LABEL",
        "-----------------------------------------------------------------------------------------------------------------------------------------------------",
    ]

    all_values_ms: List[float] = []
    per_dataset_means_ms: List[float] = []
    total_chars = 0
    total_hits = 0

    for idx, dataset_name in enumerate(dataset_names, start=1):
        text_path = _resolve_text_path(eval_root, dataset_name)

        if not text_path.exists():
            raise FileNotFoundError(f"Missing text file: {text_path}")

        text = _read_text(text_path)
        domain, structure = _dataset_meta(dataset_name)

        values_ms, hit_count = _measure_erkenne_runtime_ms(
            text=text,
            runs=max(1, int(runs)),
        )

        total_chars += len(text)
        total_hits += hit_count
        all_values_ms.extend(values_ms)
        per_dataset_means_ms.append(statistics.mean(values_ms) if values_ms else 0.0)

        lines.append(
            _format_dataset_runtime_line(
                dataset_name=dataset_name,
                domain=domain,
                structure=structure,
                char_count=len(text),
                hit_count=hit_count,
                values_ms=values_ms,
            )
        )

        print(f"[{model_key}] [{idx:02d}/{len(dataset_names):02d}] {dataset_name} fertig")

    lines.append(
        _format_global_runtime_summary(
            all_values_ms=all_values_ms,
            per_dataset_means_ms=per_dataset_means_ms,
            dataset_count=len(dataset_names),
            total_chars=total_chars,
            total_hits=total_hits,
            runs_per_dataset=max(1, int(runs)),
        )
    )

    output_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    print(f"Wrote: {output_path}")
    return output_path


def _build_combined_summary(result_paths: List[Path], output_path: Path) -> None:
    sections: List[str] = []

    for path in result_paths:
        content = path.read_text(encoding="utf-8").rstrip()
        sections.append(content)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n\n".join(sections).rstrip() + "\n", encoding="utf-8")
    print(f"Wrote: {output_path}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--eval-root", default="evaluation")
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument("--only", nargs="*", default=None, help="Run only these dataset basenames")
    parser.add_argument(
        "--models",
        nargs="*",
        default=["spacy", "flair"],
        choices=sorted(MODEL_SPECS.keys()),
        help="NER models/backends to benchmark",
    )
    args = parser.parse_args()

    eval_root = Path(args.eval_root)
    result_root = eval_root / "result"

    dataset_names = _discover_datasets(eval_root)
    if args.only:
        wanted = {value.strip() for value in args.only if value.strip()}
        dataset_names = [name for name in dataset_names if name in wanted]

    if not dataset_names:
        raise SystemExit("No datasets found (no gold json files).")

    selected_models = [m for m in args.models if m in MODEL_SPECS]
    if not selected_models:
        raise SystemExit("No models selected.")

    snapshot = _snapshot_config()

    try:
        result_paths: List[Path] = []

        for model_key in selected_models:
            result_path = _run_model_benchmark(
                eval_root=eval_root,
                result_root=result_root,
                dataset_names=dataset_names,
                model_key=model_key,
                runs=max(1, int(args.runs)),
            )
            result_paths.append(result_path)

        combined_path = (
            result_root
            / "runtime_secure_postprocess_on"
            / "combined_runtime_report.txt"
        )
        _build_combined_summary(result_paths, combined_path)

    finally:
        _restore_config(snapshot)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())