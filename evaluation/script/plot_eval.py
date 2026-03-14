from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt


BASE_DIR = Path(__file__).resolve().parents[1]

RESULT_DIR = BASE_DIR / "result"

MINIMAL_CSV = RESULT_DIR / "minimal" / "csv"
SECURE_CSV = RESULT_DIR / "secure" / "csv"

PLOT_DIR = RESULT_DIR / "plots"
PLOT_DIR.mkdir(parents=True, exist_ok=True)


def load_csv(path: Path):
    if not path.exists():
        raise RuntimeError(f"CSV not found: {path}")
    return pd.read_csv(path)


def plot_overall(policy_name, df):

    modes = df["mode"]

    x = range(len(modes))
    width = 0.25

    plt.figure(figsize=(8,5))

    plt.bar([i-width for i in x], df["precision"], width=width, label="Precision")
    plt.bar(x, df["recall"], width=width, label="Recall")
    plt.bar([i+width for i in x], df["f1"], width=width, label="F1")

    plt.xticks(x, modes)
    plt.ylim(0,1.05)

    plt.title(f"Overall Scores ({policy_name})")
    plt.ylabel("Score")
    plt.xlabel("Mode")

    plt.grid(axis="y", alpha=0.3)
    plt.legend()

    plt.tight_layout()

    out = PLOT_DIR / f"{policy_name}_overall_scores.png"
    plt.savefig(out, dpi=200)

    plt.close()


def plot_errors(policy_name, df):

    modes = df["mode"]

    x = range(len(modes))
    width = 0.35

    plt.figure(figsize=(8,5))

    plt.bar([i-width/2 for i in x], df["fp"], width=width, label="FP")
    plt.bar([i+width/2 for i in x], df["fn"], width=width, label="FN")

    plt.xticks(x, modes)

    plt.title(f"Errors ({policy_name})")
    plt.ylabel("Count")
    plt.xlabel("Mode")

    plt.grid(axis="y", alpha=0.3)
    plt.legend()

    plt.tight_layout()

    out = PLOT_DIR / f"{policy_name}_errors.png"
    plt.savefig(out, dpi=200)

    plt.close()


def plot_domain(policy_name, df):

    pivot = df.pivot(index="domain", columns="mode", values="f1")

    pivot = pivot[["regex","ner","combined"]]

    x = range(len(pivot.index))
    width = 0.25

    plt.figure(figsize=(10,6))

    plt.bar([i-width for i in x], pivot["regex"], width=width, label="regex")
    plt.bar(x, pivot["ner"], width=width, label="ner")
    plt.bar([i+width for i in x], pivot["combined"], width=width, label="combined")

    plt.xticks(x, pivot.index, rotation=20)

    plt.title(f"F1 by Domain ({policy_name})")

    plt.ylabel("F1")
    plt.xlabel("Domain")

    plt.ylim(0,1.05)

    plt.grid(axis="y", alpha=0.3)
    plt.legend()

    plt.tight_layout()

    out = PLOT_DIR / f"{policy_name}_domain_f1.png"
    plt.savefig(out, dpi=200)

    plt.close()


def process_policy(name, path):

    overall = load_csv(path / "overall.csv")
    domain = load_csv(path / "domain.csv")

    plot_overall(name, overall)
    plot_errors(name, overall)
    plot_domain(name, domain)


def main():

    process_policy("minimal", MINIMAL_CSV)
    process_policy("secure", SECURE_CSV)

    print("Plots generated in:", PLOT_DIR)


if __name__ == "__main__":
    main()