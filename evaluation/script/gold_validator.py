from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple, Optional


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, obj: Any) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def context_snippet(text: str, start: int, end: int, radius: int = 30) -> str:
    left = max(0, start - radius)
    right = min(len(text), end + radius)
    before = text[left:start].replace("\n", "\\n").replace("\r", "\\r")
    match = text[start:end].replace("\n", "\\n").replace("\r", "\\r")
    after = text[end:right].replace("\n", "\\n").replace("\r", "\\r")
    return f"{before}▮{match}▮{after}"


def find_all(text: str, needle: str) -> List[Tuple[int, int]]:
    results: List[Tuple[int, int]] = []
    i = 0
    while True:
        pos = text.find(needle, i)
        if pos == -1:
            break
        results.append((pos, pos + len(needle)))
        i = pos + 1
    return results


def _norm_label(x: Any) -> str:
    return str(x or "").strip().upper()


def _norm_sources(x: Any) -> List[str]:
    if not isinstance(x, list):
        return []
    out: List[str] = []
    for v in x:
        s = str(v or "").strip().lower()
        if not s:
            continue
        if s == "dictionary":
            s = "dict"
        out.append(s)
    uniq: List[str] = []
    seen = set()
    for s in out:
        if s in seen:
            continue
        seen.add(s)
        uniq.append(s)
    return uniq


def resolve_paths(dataset_root: Path, eval_root: Path, name: str) -> Tuple[Path, Path, Path]:
    text_path = dataset_root / "data" / f"{name}.txt"

    report_dir = eval_root / "result"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / f"{name}_string_positions.txt"

    gold_path = dataset_root / "gold" / f"{name}.json"
    gold_path.parent.mkdir(parents=True, exist_ok=True)

    return text_path, report_path, gold_path


def _parse_tokens_spec(tokens_obj: Any, fallback_document_id: str) -> Tuple[str, List[Dict[str, Any]]]:
    if isinstance(tokens_obj, dict):
        doc_id = str(tokens_obj.get("document_id") or fallback_document_id)
        items = tokens_obj.get("items")
        if not isinstance(items, list):
            raise ValueError("tokens json: expected {document_id, items:[...]} where items is a list")
        return doc_id, items

    if isinstance(tokens_obj, list):
        raise ValueError(
            "tokens json is a list of strings/objects. That format cannot carry label/source cleanly. "
            "Use object format: {document_id:'...', items:[{label, expected_sources, text/alternatives...}]}"
        )

    raise ValueError("tokens json: invalid format")


def _build_gold_entity_from_item(text: str, item: Dict[str, Any], lines: List[str]) -> Optional[Dict[str, Any]]:
    label = _norm_label(item.get("label"))
    expected_sources = _norm_sources(item.get("expected_sources"))

    if not label:
        lines.append("  !! SKIP item: missing label")
        return None

    alternatives = item.get("alternatives", None)

    if isinstance(alternatives, list) and alternatives:
        alt_entries: List[Dict[str, Any]] = []
        for alt in alternatives:
            if not isinstance(alt, dict):
                continue
            alt_text = str(alt.get("text") or "").strip()
            alt_sources = _norm_sources(alt.get("expected_sources", expected_sources))
            if not alt_text:
                continue

            occ = find_all(text, alt_text)
            lines.append(f"  ALT '{alt_text}' occurrences: {len(occ)}")

            if len(occ) == 0:
                lines.append("    !! NOT FOUND !!")
                continue

            if len(occ) > 1:
                lines.append("    !! MULTIPLE FOUND -> taking first. If wrong, make text more specific.")
            start, end = occ[0]
            ctx = context_snippet(text, start, end)
            lines.append(f"    - {start}:{end} ctx='{ctx}'")

            alt_entries.append(
                {
                    "start": start,
                    "end": end,
                    "text": alt_text,
                    "expected_sources": alt_sources,
                }
            )

        if not alt_entries:
            lines.append("  !! SKIP entity: all alternatives not found")
            return None

        return {
            "label": label,
            "expected_sources": expected_sources,
            "alternatives": alt_entries,
        }

    entity_text = str(item.get("text") or "").strip()
    if not entity_text:
        lines.append("  !! SKIP item: missing text (or alternatives)")
        return None

    occ = find_all(text, entity_text)
    lines.append(f"occurrences: {len(occ)}")

    if len(occ) == 0:
        lines.append("  !! NOT FOUND !!")
        return None

    if len(occ) > 1:
        lines.append("  !! MULTIPLE FOUND -> taking first. If wrong, make text more specific.")
    start, end = occ[0]
    ctx = context_snippet(text, start, end)
    lines.append(f"  - {start}:{end} ctx='{ctx}'")

    return {
        "label": label,
        "expected_sources": expected_sources,
        "start": start,
        "end": end,
        "text": entity_text,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-root", default="evaluation/datasets")
    parser.add_argument("--eval-root", default="evaluation")
    parser.add_argument("--name", required=True)
    parser.add_argument("--tokens", required=True, help="tokens json: {document_id, items:[...]}")
    parser.add_argument("--write-gold", action="store_true", help="Write evaluation/datasets/gold/<name>.json")
    args = parser.parse_args()

    dataset_root = Path(args.dataset_root)
    eval_root = Path(args.eval_root)

    text_path, report_path, gold_path = resolve_paths(dataset_root, eval_root, args.name)

    if not text_path.exists():
        raise FileNotFoundError(f"Text file not found: {text_path}")

    text = read_text(text_path)
    tokens_obj = read_json(Path(args.tokens))

    document_id, items = _parse_tokens_spec(tokens_obj, fallback_document_id=args.name)

    lines: List[str] = []
    gold_entities: List[Dict[str, Any]] = []

    lines.append(f"DATASET: {args.name}")
    lines.append(f"TEXT: {text_path}")
    lines.append(f"len(text)={len(text)}")
    lines.append("=" * 60)
    lines.append("")

    for idx, item in enumerate(items):
        if not isinstance(item, dict):
            lines.append(f"ITEM #{idx}: !! SKIP not an object")
            lines.append("")
            continue

        label = _norm_label(item.get("label"))
        srcs = _norm_sources(item.get("expected_sources"))
        show_srcs = ",".join(srcs) if srcs else "(none)"

        lines.append(f"ITEM #{idx}: label={label} expected_sources={show_srcs}")

        ent = _build_gold_entity_from_item(text, item, lines)
        if ent is not None:
            gold_entities.append(ent)

        lines.append("")

    report_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    print(f"Wrote: {report_path}")

    if args.write_gold:
        gold_obj = {
            "document_id": document_id,
            "entities": gold_entities,
        }
        write_json(gold_path, gold_obj)
        print(f"Wrote: {gold_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())