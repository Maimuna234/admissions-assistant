import csv
import os
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).resolve().parent


def _resolve_path(path_value: str, default_name: str) -> str:
    if not path_value:
        return str(WORKSPACE_ROOT / default_name)
    candidate = Path(path_value)
    if candidate.is_absolute():
        return str(candidate)
    for base in [WORKSPACE_ROOT, Path.cwd()]:
        resolved = (base / candidate).resolve()
        if resolved.exists():
            return str(resolved)
    return str((WORKSPACE_ROOT / candidate).resolve())

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
except Exception as exc:
    raise SystemExit(f"matplotlib is required to generate charts: {exc}")


def plot_summary(input_csv: str = "evaluation_summary.csv", output_png: str = "evaluation_summary.png"):
    input_csv = _resolve_path(input_csv, "evaluation_summary.csv")
    output_png = _resolve_path(output_png, "evaluation_summary.png")
    if not os.path.exists(input_csv):
        raise FileNotFoundError(f"Missing input file: {input_csv}")

    with open(input_csv, newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    if not rows:
        raise ValueError("No summary rows found")

    row = rows[0]
    metrics = {
        "Faithfulness": float(row["avg_faithfulness"]),
        "Answer Relevancy": float(row["avg_answer_relevancy"]),
        "Context Precision": float(row["avg_context_precision"]),
        "Context Recall": float(row["avg_context_recall"]),
    }

    labels = list(metrics.keys())
    values = list(metrics.values())

    plt.figure(figsize=(8, 4.5))
    bars = plt.bar(labels, values, color=["#4C78A8", "#F58518", "#54A24B", "#E45756"])
    plt.ylim(0, 1.0)
    plt.ylabel("Score")
    plt.title("RAG Evaluation Summary")
    plt.xticks(rotation=15, ha="right")

    for bar, value in zip(bars, values):
        plt.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.01, f"{value:.3f}", ha="center", va="bottom")

    plt.tight_layout()
    plt.savefig(output_png, dpi=150)
    plt.close()
    print(f"✅ Chart written to: {output_png}")


if __name__ == "__main__":
    plot_summary()
