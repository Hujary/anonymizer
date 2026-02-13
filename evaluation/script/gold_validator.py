from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List, Dict, Any, Tuple


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, obj: Dict[str, Any]) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def context_snippet(text: str, start: int, end: int, radius: int = 30) -> str:
    left = max(0, start - radius)
    right = min(len(text), end + radius)
    before = text[left:start].replace("\n", "\\n")
    match = text[start:end].replace("\n", "\\n")
    after = text[end:right].replace("\n", "\\n")
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


def resolve_paths(dataset_root: Path, name: str) -> Tuple[Path, Path]:
    text_path = dataset_root / "data" / f"{name}.txt"
    result_path = dataset_root / "result" / f"{name}_string_positions.txt"
    result_path.parent.mkdir(parents=True, exist_ok=True)
    return text_path, result_path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-root", default="evaluation/datasets")
    parser.add_argument("--name", required=True)
    parser.add_argument(
        "--tokens",
        required=True,
        help="JSON file containing array of strings to search"
    )
    parser.add_argument(
        "--write-gold",
        action="store_true",
        help="Generate gold.json structure (without expected_sources)"
    )
    args = parser.parse_args()

    dataset_root = Path(args.dataset_root)
    text_path, result_path = resolve_paths(dataset_root, args.name)

    if not text_path.exists():
        raise FileNotFoundError(f"Text file not found: {text_path}")

    text = read_text(text_path)
    tokens_data = read_json(Path(args.tokens))

    if not isinstance(tokens_data, list):
        raise ValueError("Token file must contain a JSON array of strings")

    lines: List[str] = []
    gold_entities: List[Dict[str, Any]] = []

    lines.append(f"DATASET: {args.name}")
    lines.append(f"len(text)={len(text)}")
    lines.append("=" * 60)
    lines.append("")

    for token in tokens_data:
        if not isinstance(token, str) or not token.strip():
            continue

        occurrences = find_all(text, token)

        lines.append(f"TOKEN: '{token}'")
        lines.append(f"occurrences: {len(occurrences)}")

        for idx, (start, end) in enumerate(occurrences):
            ctx = context_snippet(text, start, end)
            lines.append(f"  - #{idx} {start}:{end}  ctx='{ctx}'")

            if args.write_gold:
                gold_entities.append({
                    "label": "UNKNOWN",
                    "start": start,
                    "end": end,
                    "text": token
                })

        if not occurrences:
            lines.append("  !! NOT FOUND !!")

        lines.append("")

    result_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    print(f"Wrote: {result_path}")

    if args.write_gold:
        gold_path = dataset_root / "gold" / f"{args.name}.json"
        gold_path.parent.mkdir(parents=True, exist_ok=True)

        gold_obj = {
            "document_id": args.name,
            "entities": gold_entities
        }

        write_json(gold_path, gold_obj)
        print(f"Wrote: {gold_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())