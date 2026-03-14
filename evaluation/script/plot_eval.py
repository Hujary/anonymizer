from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


BASE_DIR = Path(__file__).resolve().parent
OVERALL_CSV = BASE_DIR / "overall.csv"
DOMAIN_CSV = BASE_DIR / "domain.csv"
OUTPUT_DIR = BASE_DIR / "plots"


def _ensure_output_dir() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def _load_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"CSV nicht gefunden: {path}")
    return pd.read_csv(path)


def _sort_mode_column(df: pd.DataFrame) -> pd.DataFrame:
    mode_order = ["regex", "ner", "combined"]
    out = df.copy()
    out["mode"] = pd.Categorical(out["mode"], categories=mode_order, ordered=True)
    out = out.sort_values("mode")
    return out


def plot_overall_scores(df_overall: pd.DataFrame) -> None:
    df = _sort_mode_column(df_overall)

    fig, ax = plt.subplots(figsize=(8, 5))

    x = range(len(df))
    width = 0.25

    ax.bar([i - width for i in x], df["precision"], width=width, label="Precision")
    ax.bar(x, df["recall"], width=width, label="Recall")
    ax.bar([i + width for i in x], df["f1"], width=width, label="F1")

    ax.set_title("Gesamtvergleich: Precision / Recall / F1 pro Mode")
    ax.set_xlabel("Mode")
    ax.set_ylabel("Score")
    ax.set_xticks(list(x))
    ax.set_xticklabels(df["mode"].tolist())
    ax.set_ylim(0.0, 1.05)
    ax.legend()
    ax.grid(axis="y", alpha=0.3)

    fig.tight_layout()
    fig.savefig(OUTPUT_DIR / "overall_scores.png", dpi=200)
    plt.close(fig)


def plot_overall_errors(df_overall: pd.DataFrame) -> None:
    df = _sort_mode_column(df_overall)

    fig, ax = plt.subplots(figsize=(8, 5))

    x = range(len(df))
    width = 0.35

    ax.bar([i - width / 2 for i in x], df["fp"], width=width, label="FP")
    ax.bar([i + width / 2 for i in x], df["fn"], width=width, label="FN")

    ax.set_title("Gesamtvergleich: FP / FN pro Mode")
    ax.set_xlabel("Mode")
    ax.set_ylabel("Anzahl")
    ax.set_xticks(list(x))
    ax.set_xticklabels(df["mode"].tolist())
    ax.legend()
    ax.grid(axis="y", alpha=0.3)

    fig.tight_layout()
    fig.savefig(OUTPUT_DIR / "overall_errors.png", dpi=200)
    plt.close(fig)


def plot_domain_f1(df_domain: pd.DataFrame) -> None:
    df = _sort_mode_column(df_domain)

    pivot = df.pivot(index="domain", columns="mode", values="f1")
    pivot = pivot[["regex", "ner", "combined"]]

    fig, ax = plt.subplots(figsize=(10, 6))

    x = list(range(len(pivot.index)))
    width = 0.25

    ax.bar([i - width for i in x], pivot["regex"], width=width, label="regex")
    ax.bar(x, pivot["ner"], width=width, label="ner")
    ax.bar([i + width for i in x], pivot["combined"], width=width, label="combined")

    ax.set_title("F1 pro Domain und Mode")
    ax.set_xlabel("Domain")
    ax.set_ylabel("F1")
    ax.set_xticks(x)
    ax.set_xticklabels(pivot.index.tolist(), rotation=20, ha="right")
    ax.set_ylim(0.0, 1.05)
    ax.legend()
    ax.grid(axis="y", alpha=0.3)

    fig.tight_layout()
    fig.savefig(OUTPUT_DIR / "domain_f1.png", dpi=200)
    plt.close(fig)


def plot_domain_errors(df_domain: pd.DataFrame) -> None:
    df = _sort_mode_column(df_domain)

    domains = df["domain"].drop_duplicates().tolist()
    modes = ["regex", "ner", "combined"]

    fig, axes = plt.subplots(nrows=2, ncols=1, figsize=(12, 10), sharex=True)

    width = 0.25
    x = list(range(len(domains)))

    for idx, mode in enumerate(modes):
        sub = df[df["mode"] == mode].set_index("domain").reindex(domains)

        axes[0].bar(
            [i + (idx - 1) * width for i in x],
            sub["fp"],
            width=width,
            label=mode,
        )

        axes[1].bar(
            [i + (idx - 1) * width for i in x],
            sub["fn"],
            width=width,
            label=mode,
        )

    axes[0].set_title("FP pro Domain und Mode")
    axes[0].set_ylabel("FP")
    axes[0].legend()
    axes[0].grid(axis="y", alpha=0.3)

    axes[1].set_title("FN pro Domain und Mode")
    axes[1].set_ylabel("FN")
    axes[1].set_xlabel("Domain")
    axes[1].set_xticks(x)
    axes[1].set_xticklabels(domains, rotation=20, ha="right")
    axes[1].legend()
    axes[1].grid(axis="y", alpha=0.3)

    fig.tight_layout()
    fig.savefig(OUTPUT_DIR / "domain_errors.png", dpi=200)
    plt.close(fig)


def main() -> None:
    _ensure_output_dir()

    df_overall = _load_csv(OVERALL_CSV)
    df_domain = _load_csv(DOMAIN_CSV)

    plot_overall_scores(df_overall)
    plot_overall_errors(df_overall)
    plot_domain_f1(df_domain)
    plot_domain_errors(df_domain)

    print(f"Plots gespeichert in: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()