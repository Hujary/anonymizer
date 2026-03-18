from __future__ import annotations

import argparse
import json
import statistics
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

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


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _norm_label(value: Any) -> str:
    return str(value or "").strip().upper()


def _norm_source(value: Any) -> str:
    x = str(value or "").strip().lower()
    if x in ("ner", "regex", "dict", "manual"):
        return x
    if x == "dictionary":
        return "dict"
    return x or "?"


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


def _snapshot_config() -> Dict[str, Any]:
    return {
        "flags": dict(config.get_flags() or {}),
        "ner_labels": list(config.get("ner_labels", []) or []),
        "regex_labels": list(config.get("regex_labels", []) or []),
        "spacy_model": config.get("spacy_model", ""),
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
    config.set("spacy_model", snapshot.get("spacy_model", "") or "")
    config.set("debug_mask", bool(snapshot.get("debug_mask", False)))
    config.set("use_ner_postprocessing", snapshot.get("use_ner_postprocessing", True))


def _resolve_paths(eval_root: Path, basename: str) -> Tuple[Path, Path]:
    datasets_dir = eval_root / "datasets"
    data_dir = datasets_dir / "data"
    gold_dir = datasets_dir / "gold"

    text_path = data_dir / f"{basename}.txt"
    gold_path = gold_dir / f"{basename}.json"
    return text_path, gold_path


def _discover_datasets(eval_root: Path) -> List[str]:
    gold_dir = eval_root / "datasets" / "gold"
    if not gold_dir.exists():
        return []
    return [p.stem for p in sorted(gold_dir.glob("*.json"))]


def _parse_gold(gold: Dict[str, Any]) -> List[Dict[str, Any]]:
    entities = gold.get("entities")
    if not isinstance(entities, list):
        raise ValueError("gold.json: field 'entities' must be a list")

    out: List[Dict[str, Any]] = []

    for entity in entities:
        if not isinstance(entity, dict):
            continue

        raw_label = entity.get("label")

        labels_ordered: List[str] = []
        if isinstance(raw_label, list):
            for item in raw_label:
                label = _norm_label(item)
                if label and label not in labels_ordered:
                    labels_ordered.append(label)
        else:
            label = _norm_label(raw_label)
            if label:
                labels_ordered.append(label)

        if not labels_ordered:
            continue

        expected_sources_raw = entity.get("expected_sources", [])
        if not isinstance(expected_sources_raw, list):
            expected_sources_raw = []
        expected_sources = {_norm_source(x) for x in expected_sources_raw if str(x).strip()}

        out.append(
            {
                "primary_label": labels_ordered[0],
                "acceptable_labels": set(labels_ordered),
                "expected_sources": expected_sources,
            }
        )

    return out


def _load_dataset_cache(eval_root: Path, dataset_names: List[str]) -> Dict[str, Tuple[str, List[Dict[str, Any]]]]:
    cache: Dict[str, Tuple[str, List[Dict[str, Any]]]] = {}

    for dataset_name in dataset_names:
        text_path, gold_path = _resolve_paths(eval_root, dataset_name)

        if not text_path.exists():
            raise FileNotFoundError(f"Missing text file: {text_path}")
        if not gold_path.exists():
            raise FileNotFoundError(f"Missing gold file: {gold_path}")

        text = _read_text(text_path)
        gold = _read_json(gold_path)
        gold_entities = _parse_gold(gold)
        cache[dataset_name] = (text, gold_entities)

    return cache


def _compute_policy_gold_stats(
    *,
    dataset_names: List[str],
    dataset_cache: Dict[str, Tuple[str, List[Dict[str, Any]]]],
    policy: str,
) -> Dict[str, Any]:
    allowed_labels = _policy_labels(policy)

    total_texts = 0
    total_chars = 0
    total_relevant_gold = 0
    label_counts: Dict[str, int] = defaultdict(int)

    for dataset_name in dataset_names:
        text, gold_entities = dataset_cache[dataset_name]
        total_texts += 1
        total_chars += len(text)

        for entity in gold_entities:
            primary_label = str(entity.get("primary_label", "") or "").strip().upper()
            acceptable_labels = set(entity.get("acceptable_labels", set()) or set())

            if not acceptable_labels.intersection(allowed_labels):
                continue

            total_relevant_gold += 1

            if primary_label:
                label_counts[primary_label] += 1

    return {
        "texts": total_texts,
        "chars": total_chars,
        "relevant_gold": total_relevant_gold,
        "label_counts": dict(label_counts),
        "ner_labels": list(POLICY_SPECS[policy].get("ner_labels", [])),
        "regex_labels": list(POLICY_SPECS[policy].get("regex_labels", [])),
        "allowed_labels": sorted(allowed_labels),
    }


def _write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value.rstrip() + "\n", encoding="utf-8")


def _measure_erkenne_runtime_ms(
    *,
    text: str,
    samples: int,
) -> List[float]:
    values: List[float] = []

    erkenne(text)

    for _ in range(max(1, int(samples))):
        t0 = time.perf_counter_ns()
        erkenne(text)
        t1 = time.perf_counter_ns()
        values.append((t1 - t0) / 1_000_000.0)

    return values


def _build_worker_report(
    *,
    dataset_names: List[str],
    dataset_cache: Dict[str, Tuple[str, List[Dict[str, Any]]]],
    policy: str,
    runtime_samples: int,
    postprocess_enabled: bool,
) -> str:
    policy_stats = _compute_policy_gold_stats(
        dataset_names=dataset_names,
        dataset_cache=dataset_cache,
        policy=policy,
    )

    all_runtime_values: List[float] = []

    for dataset_name in dataset_names:
        text, _ = dataset_cache[dataset_name]
        values = _measure_erkenne_runtime_ms(
            text=text,
            samples=runtime_samples,
        )
        all_runtime_values.extend(values)

    mean_ms = statistics.mean(all_runtime_values) if all_runtime_values else 0.0
    median_ms = statistics.median(all_runtime_values) if all_runtime_values else 0.0
    min_ms = min(all_runtime_values) if all_runtime_values else 0.0
    max_ms = max(all_runtime_values) if all_runtime_values else 0.0
    stdev_ms = statistics.pstdev(all_runtime_values) if len(all_runtime_values) > 1 else 0.0

    label_counts = policy_stats["label_counts"]
    if label_counts:
        label_dist = ", ".join(f"{label}={label_counts[label]}" for label in sorted(label_counts.keys()))
    else:
        label_dist = "none"

    lines: List[str] = []
    lines.append(f"POLICY: {policy}")
    lines.append("-" * 80)
    lines.append(f"TEXT_COUNT: {policy_stats['texts']}")
    lines.append(f"TOTAL_TEXT_CHARS: {policy_stats['chars']}")
    avg_len = (policy_stats["chars"] / policy_stats["texts"]) if policy_stats["texts"] else 0.0
    lines.append(f"AVERAGE_TEXT_LENGTH: {avg_len:.1f} characters")
    lines.append(f"POLICY_RELEVANT_GOLD_ENTITIES: {policy_stats['relevant_gold']}")
    lines.append(f"NER_LABELS: {policy_stats['ner_labels']}")
    lines.append(f"REGEX_LABELS: {policy_stats['regex_labels']}")
    lines.append(f"ALLOWED_LABELS_COMBINED: {policy_stats['allowed_labels']}")
    lines.append(f"LABEL_DISTRIBUTION: {label_dist}")
    lines.append("")
    lines.append("RUNTIME SUMMARY")
    lines.append("-" * 80)
    lines.append(f"samples : {len(all_runtime_values)}")
    lines.append(f"mean_ms : {mean_ms:.3f}")
    lines.append(f"median_ms : {median_ms:.3f}")
    lines.append(f"min_ms : {min_ms:.3f}")
    lines.append(f"max_ms : {max_ms:.3f}")
    lines.append(f"stdev_ms : {stdev_ms:.3f}")
    lines.append("")
    lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _run_worker(
    *,
    eval_root: Path,
    dataset_names: List[str],
    policy: str,
    postprocess_enabled: bool,
    runtime_samples: int,
) -> int:
    snapshot = _snapshot_config()

    try:
        config.set("use_ner_postprocessing", postprocess_enabled)
        _apply_policy(policy)

        dataset_cache = _load_dataset_cache(eval_root, dataset_names)

        report = _build_worker_report(
            dataset_names=dataset_names,
            dataset_cache=dataset_cache,
            policy=policy,
            runtime_samples=runtime_samples,
            postprocess_enabled=postprocess_enabled,
        )

        sys.stdout.write(report)
        sys.stdout.flush()
        return 0
    finally:
        _restore_config(snapshot)


def _run_subprocess_worker(
    *,
    script_path: Path,
    eval_root: Path,
    dataset_names: List[str],
    policy: str,
    postprocess_enabled: bool,
    runtime_samples: int,
) -> str:
    cmd = [
        sys.executable,
        str(script_path),
        "--worker",
        "--eval-root",
        str(eval_root),
        "--policy",
        policy,
        "--postprocess",
        "on" if postprocess_enabled else "off",
        "--runtime-samples",
        str(runtime_samples),
    ]

    if dataset_names:
        cmd.append("--only")
        cmd.extend(dataset_names)

    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=str(REPO_ROOT),
        check=False,
    )

    if result.returncode != 0:
        stderr = (result.stderr or "").strip()
        stdout = (result.stdout or "").strip()
        message_parts: List[str] = [
            f"Worker failed for policy={policy}, postprocess={'on' if postprocess_enabled else 'off'}",
        ]
        if stdout:
            message_parts.append(f"STDOUT:\n{stdout}")
        if stderr:
            message_parts.append(f"STDERR:\n{stderr}")
        raise RuntimeError("\n\n".join(message_parts))

    return result.stdout


def _build_main_report_prefix(
    *,
    dataset_count: int,
    runtime_samples: int,
    postprocess_enabled: bool,
) -> str:
    lines: List[str] = []
    lines.append("RUNTIME REPORT")
    lines.append("=" * 80)
    lines.append(f"POSTPROCESSING: {'on' if postprocess_enabled else 'off'}")
    lines.append(f"DATASETS: {dataset_count}")
    lines.append(f"RUNTIME RUNS PER TEXT: {runtime_samples}")
    lines.append("MEASUREMENT: pure execution time of erkenne(text)")
    lines.append("WARM-UP: one untimed warm-up run per text")
    lines.append("")
    return "\n".join(lines) + "\n"


def _run_main(
    *,
    script_path: Path,
    eval_root: Path,
    result_root: Path,
    dataset_names: List[str],
    selected_policies: List[str],
    runtime_samples: int,
    only_post: str | None,
) -> int:
    if only_post == "on":
        run_variants = [True]
    elif only_post == "off":
        run_variants = [False]
    else:
        run_variants = [False, True]

    for postprocess_enabled in run_variants:
        variant_name = "postprocess_on" if postprocess_enabled else "postprocess_off"
        variant_root = result_root / variant_name
        variant_root.mkdir(parents=True, exist_ok=True)

        report_parts: List[str] = [
            _build_main_report_prefix(
                dataset_count=len(dataset_names),
                runtime_samples=runtime_samples,
                postprocess_enabled=postprocess_enabled,
            ).rstrip()
        ]

        for policy in selected_policies:
            worker_output = _run_subprocess_worker(
                script_path=script_path,
                eval_root=eval_root,
                dataset_names=dataset_names,
                policy=policy,
                postprocess_enabled=postprocess_enabled,
                runtime_samples=runtime_samples,
            ).rstrip()

            report_parts.append(worker_output)

        final_report = "\n\n".join(part for part in report_parts if part).rstrip() + "\n"
        target_path = variant_root / "times.txt"
        _write_text(target_path, final_report)
        print(f"Wrote: {target_path}")

    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--eval-root", default="evaluation")
    parser.add_argument("--runtime-samples", type=int, default=5)
    parser.add_argument(
        "--policies",
        nargs="*",
        default=["minimal", "secure"],
        choices=sorted(POLICY_SPECS.keys()),
        help="Policies to benchmark",
    )
    parser.add_argument(
        "--only-post",
        choices=["on", "off"],
        default=None,
        help="Optional: run only one variant instead of both",
    )
    parser.add_argument("--only", nargs="*", default=None, help="Run only these dataset basenames")
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--policy", choices=sorted(POLICY_SPECS.keys()), default=None)
    parser.add_argument("--postprocess", choices=["on", "off"], default=None)
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

    if args.worker:
        if not args.policy:
            raise SystemExit("--worker requires --policy")
        if not args.postprocess:
            raise SystemExit("--worker requires --postprocess")

        return _run_worker(
            eval_root=eval_root,
            dataset_names=dataset_names,
            policy=args.policy,
            postprocess_enabled=(args.postprocess == "on"),
            runtime_samples=max(1, int(args.runtime_samples)),
        )

    selected_policies = [policy for policy in args.policies if policy in POLICY_SPECS]
    if not selected_policies:
        raise SystemExit("No policies selected.")

    return _run_main(
        script_path=Path(__file__).resolve(),
        eval_root=eval_root,
        result_root=result_root,
        dataset_names=dataset_names,
        selected_policies=selected_policies,
        runtime_samples=max(1, int(args.runtime_samples)),
        only_post=args.only_post,
    )


if __name__ == "__main__":
    raise SystemExit(main())