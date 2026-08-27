import json
import time

import pandas as pd

from rag_orchestrator import AdmissionsRAGOrchestrator


CORE_QUESTIONS = [
    "What are the core modules taught in Year 1?",
    "What are the core modules taught in Year 2?",
    "Does this program offer a placement year in industry?",
    "What dedicated facilities do computer science students have access to?",
]

ENTRY_REQUIREMENT_QUESTION = "What are the standard A-level grade requirements?"
ENTRY_REQUIREMENT_UNIVERSITIES = {
    "University of Manchester",
    "Lancaster University",
    "University of Leeds",
    "University of Birmingham",
    "University of Nottingham",
    "University of Sheffield",
}


def _load_universities():
    with open("clearing_knowledge_base.json", "r", encoding="utf-8") as handle:
        return json.load(handle)


def _build_benchmark_plan():
    plan = []
    for record in _load_universities():
        university = record["university_name"]
        for question in CORE_QUESTIONS:
            plan.append((university, question))
        if university in ENTRY_REQUIREMENT_UNIVERSITIES:
            plan.append((university, ENTRY_REQUIREMENT_QUESTION))
    return plan


def bootstrap_golden_dataset():
    print("Initializing pipeline to bootstrap a balanced cross-university golden dataset...")

    rag = AdmissionsRAGOrchestrator()
    benchmark_plan = _build_benchmark_plan()
    results_data = []

    print(f"\nRunning {len(benchmark_plan)} university/question pairs through the RAG pipeline.\n")

    for i, (university, question) in enumerate(benchmark_plan, 1):
        print(f"Processing [{i}/{len(benchmark_plan)}]: {university} -> {question}")
        result = rag.query_pipeline(user_query=question, target_competitor=university)
        results_data.append({
            "ID": i,
            "Target Competitor": university,
            "Question": question,
            "Draft Ground Truth (LLM Output)": result["answer"],
            "Needs Human Review?": "YES",
        })
        time.sleep(2)

    df = pd.DataFrame(results_data)
    df.to_csv("golden_dataset_draft.csv", index=False)
    print("\nSuccess! Saved to 'golden_dataset_draft.csv'")

if __name__ == "__main__":
    bootstrap_golden_dataset()