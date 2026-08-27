import os
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

from evaluator import evaluate_with_llm_judge


load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env")


def _write_summary_csv(results_df: pd.DataFrame, summary_path: Path) -> None:
    metric_columns = ["faithfulness", "answer_relevancy", "context_precision", "context_recall"]
    summary_row = {
        "total_rows": int(len(results_df)),
    }
    for column in metric_columns:
        if column in results_df.columns and not results_df.empty:
            summary_row[f"avg_{column}"] = round(float(results_df[column].astype(float).mean()), 4)
        else:
            summary_row[f"avg_{column}"] = 0.0

    summary_df = pd.DataFrame([summary_row])
    summary_df.to_csv(summary_path, index=False)


def _parse_context_value(candidate) -> list[str]:
    if isinstance(candidate, str):
        parts = [part.strip() for part in candidate.split("\n---\n") if part.strip()]
        return parts or ["No context retrieved."]
    if candidate is None:
        return ["No context retrieved."]
    return [str(item) for item in candidate]


def run_ragas_evaluation(csv_path="golden_dataset1.csv"):
    print("--- Running RAGAS Triad Evaluation ---")
    df = pd.read_csv(csv_path)

    questions = df["Question"].fillna("").tolist()
    answers = df.get("Generated_Answer", df.get("Answer", df["GroundTruth"])).fillna("").tolist()
    contexts = []
    for _, row in df.iterrows():
        candidate = row.get("Retrieved_Contexts", row.get("Retrieved_Context", row.get("Context", row.get("Contexts", ""))))
        contexts.append(_parse_context_value(candidate))

    ground_truths = df["GroundTruth"].fillna("").tolist()

    try:
        results_df = evaluate_with_llm_judge(
            questions=questions,
            generated_answers=answers,
            retrieved_contexts=contexts,
            ground_truths=ground_truths,
        )
        script_dir = Path(__file__).resolve().parent
        results_path = script_dir / "ragas_evaluation_results.csv"
        summary_path = script_dir / "ragas_evaluation_summary.csv"
        results_df.to_csv(results_path, index=False)
        _write_summary_csv(results_df, summary_path)
        print("RAGAS Results:\n", results_df)
        print(f"Results exported to '{results_path.name}'")
        print(f"Summary exported to '{summary_path.name}'")
    except Exception as exc:
        print(f"Evaluation failed. Ensure your LLM API keys (e.g., OPENAI_API_KEY) are set and the ragas stack is installed. Error: {exc}")
    print("--------------------------------------\n")


if __name__ == "__main__":
    csv_file = os.environ.get("GOLDEN_DATASET_PATH", "golden_dataset1.csv")
    run_ragas_evaluation(csv_file)