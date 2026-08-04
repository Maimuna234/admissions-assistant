import csv
import os
from pathlib import Path
from statistics import mean


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


def summarize_csv(input_csv: str = "evaluation_results_monitoring.csv", output_csv: str = "evaluation_summary.csv"):
    input_csv = _resolve_path(input_csv, "evaluation_results_monitoring.csv")
    output_csv = _resolve_path(output_csv, "evaluation_summary.csv")
    if not os.path.exists(input_csv):
        raise FileNotFoundError(f"Missing input file: {input_csv}")

    with open(input_csv, newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    if not rows:
        raise ValueError("No rows found in the evaluation CSV")

    summary = {
        "total_questions": len(rows),
        "avg_confidence_score": round(mean(float(row["confidence_score"]) for row in rows), 4),
        "abstain_count": sum(1 for row in rows if row.get("should_abstain") == "True"),
        "avg_faithfulness": round(mean(float(row["faithfulness"]) for row in rows), 4),
        "avg_answer_relevancy": round(mean(float(row["answer_relevancy"]) for row in rows), 4),
        "avg_context_precision": round(mean(float(row["context_precision"]) for row in rows), 4),
        "avg_context_recall": round(mean(float(row["context_recall"]) for row in rows), 4),
    }

    with open(output_csv, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(summary.keys()))
        writer.writeheader()
        writer.writerow(summary)

    print(f"✅ Summary written to: {output_csv}")
    print(summary)


if __name__ == "__main__":
    summarize_csv()
