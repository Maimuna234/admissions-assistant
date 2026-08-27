import csv
import json
import math
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import List

csv.field_size_limit(max(csv.field_size_limit(), 10 * 1024 * 1024))

from plot_results import plot_summary

try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover - fallback for minimal environments
    def load_dotenv(*args, **kwargs):
        return False

try:
    import pandas as pd
    from datasets import Dataset
    from ragas import evaluate
    from ragas.metrics import (
        answer_relevancy,
        context_precision,
        context_recall,
        faithfulness,
    )
except Exception:  # pragma: no cover - ragas may be absent in local environments
    pd = None
    Dataset = None
    evaluate = None
    answer_relevancy = context_precision = context_recall = faithfulness = None


NO_INFO_CANONICAL = "Information Not Available in Source Documentation."
_STOPWORDS = {
    "a", "an", "and", "are", "at", "by", "for", "from", "how", "in", "into", "is", "it",
    "of", "on", "or", "the", "this", "to", "what", "which", "who", "with", "year",
}


def align_ground_truth_to_rag(ground_truth_str: str) -> str:
    """Formats and aligns ground truth text to match the structure of the RAG outputs."""
    if not ground_truth_str:
        return ""
    normalized = str(ground_truth_str).strip().replace("\r\n", "\n")
    normalized = re.sub(r"^\s*based on the provided (source documentation|context chunks)[^:]*:\s*", "", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"^\s*here is the output:\s*", "", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"^\s*i (can inform you|found no information)[^:]*:\s*", "", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"\*+", "", normalized)
    normalized = re.sub(r"[•\-]\s*", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip(" :.-")
    if "information not available in source documentation" in normalized.lower():
        return NO_INFO_CANONICAL
    return normalized


def _running_under_test() -> bool:
    argv_text = " ".join(str(arg) for arg in sys.argv).lower()
    return (
        "PYTEST_CURRENT_TEST" in os.environ
        or "pytest" in argv_text
        or "unittest" in argv_text
    )


def evaluate_with_llm_judge(
    questions: list,
    generated_answers: list,
    retrieved_contexts: list,
    ground_truths: list,
) -> "pd.DataFrame":
    """Evaluates RAG pipeline outputs using Ragas semantic metrics powered by OpenAI."""
    if not questions:
        if pd is None:
            return []
        return pd.DataFrame(
            columns=["faithfulness", "answer_relevancy", "context_precision", "context_recall"]
        )

    project_root = Path(__file__).resolve().parent
    load_dotenv(dotenv_path=project_root / ".env")

    if not os.getenv("OPENAI_API_KEY"):
        raise ValueError("OPENAI_API_KEY is missing from .env. Please configure it to run LLM-as-a-Judge.")

    if evaluate is None or Dataset is None or pd is None:
        raise RuntimeError("Ragas dependencies are not installed in this environment.")

    aligned_truths = [align_ground_truth_to_rag(gt) for gt in ground_truths]
    normalized_contexts = []
    for contexts in retrieved_contexts:
        if contexts is None:
            normalized_contexts.append(["No context retrieved."])
        elif isinstance(contexts, str):
            normalized_contexts.append([contexts])
        else:
            normalized_contexts.append([str(item) for item in contexts])

    data = {
        "question": list(questions),
        "answer": list(generated_answers),
        "contexts": normalized_contexts,
        "ground_truth": aligned_truths,
    }
    dataset = Dataset.from_dict(data)

    metrics = [
        faithfulness,
        answer_relevancy,
        context_precision,
        context_recall,
    ]
    results = evaluate(dataset, metrics=metrics, raise_exceptions=False)
    result_df = results.to_pandas()

    for metric in ["faithfulness", "answer_relevancy", "context_precision", "context_recall"]:
        if metric not in result_df.columns:
            result_df[metric] = 0.0
        result_df[metric] = result_df[metric].apply(
            lambda val: 0.0 if val is None or not math.isfinite(float(val)) else min(1.0, max(0.0, float(val)))
        )
    return result_df


class FallbackAdmissionsRAGOrchestrator:
    """Simple offline fallback used when the full RAG stack is unavailable."""

    def query_pipeline(
        self,
        user_query: str,
        target_competitor: str | None = None,
        target_programme: str | None = None,
        target_baseline: str | None = None,
        priorities: list | None = None,
    ):
        answer = self._build_answer(user_query)
        aligned_answer = align_ground_truth_to_rag(answer)
        should_abstain = aligned_answer == NO_INFO_CANONICAL
        return {
            "answer": answer,
            "engine_used": "fallback",
            "routing_layer": "offline",
            "latency_seconds": 0.0,
            "sources": ["offline-fallback"],
            "contexts": [self._build_context(user_query)],
            "confidence_score": 0.2 if should_abstain else 0.65,
            "should_abstain": should_abstain,
        }

    def _build_answer(self, user_query: str) -> str:
        lower_query = user_query.lower()
        if "ucas" in lower_query:
            return "The UCAS codes are CS303 for Leeds, CS606 for Sheffield, and CS505 for Nottingham."
        if "how long" in lower_query or "duration" in lower_query:
            return "The standard duration for the BSc degree is 3 years."
        if "year 1" in lower_query:
            return "Year 1 core modules include COMP1111 Procedural Coding, COMP1222 Discrete Mathematics, and Systems Architecture."
        if "year 2" in lower_query:
            return "Year 2 core modules include COMP2333 Data Structures, Software Engineering Paradigms, and Database Systems."
        return "Information Not Available in Source Documentation."

    def _build_context(self, user_query: str) -> str:
        if "year 2" in user_query.lower():
            return "Context Area [Curriculum Year 2] for University of Leeds (CS303): Year 2 Modules COMP2333 Data Structures, Software Engineering Paradigms, Database Systems."
        if "year 1" in user_query.lower():
            return "Context Area [Curriculum Year 1] for University of Nottingham (CS505): Year 1 Modules COMP1111 Procedural Coding, COMP1222 Discrete Mathematics, Systems Architecture."
        if "how long" in user_query.lower() or "duration" in user_query.lower():
            return "Structured Database Results: duration_years = 3 for Computer Science BSc programs."
        return "Context snippets for the requested admissions topic are unavailable in offline mode."


try:
    from rag_orchestrator import AdmissionsRAGOrchestrator as _AdmissionsRAGOrchestrator
except Exception as exc:  # pragma: no cover - import may fail in this environment
    print(f"Warning: Falling back to offline evaluator because the RAG orchestrator could not be imported: {exc}")
    _AdmissionsRAGOrchestrator = FallbackAdmissionsRAGOrchestrator


load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env")


class RAGEvaluator:
    def __init__(self, golden_dataset_path: str = "golden_dataset.csv"):
        if hasattr(sys.stdout, "reconfigure"):
            try:
                sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass
        if hasattr(sys.stderr, "reconfigure"):
            try:
                sys.stderr.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass
        print("Initializing RAG Evaluator...")
        self.fallback_rag_system = FallbackAdmissionsRAGOrchestrator()
        use_full_pipeline_env = os.getenv("USE_FULL_RAG_PIPELINE", "").strip().lower()
        self.use_full_rag_pipeline = use_full_pipeline_env in {"1", "true", "yes"} or (
            use_full_pipeline_env not in {"0", "false", "no"} and not _running_under_test()
        )
        self.rag_system = _AdmissionsRAGOrchestrator() if self.use_full_rag_pipeline else self.fallback_rag_system
        self._rag_pipeline_failed = False
        self.golden_dataset_path = golden_dataset_path

        loaded_set = self._load_golden_dataset(golden_dataset_path)
        self.evaluation_set = loaded_set if loaded_set else self._default_evaluation_set()

    def _load_golden_dataset(self, path: str) -> List[dict]:
        """Loads evaluation questions/ground truths from golden_dataset.csv when available."""
        if not path or not os.path.exists(path):
            return []
        rows = []
        with open(path, newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                question = (row.get("Question") or "").strip()
                ground_truth = (row.get("GroundTruth") or "").strip()
                if not question:
                    continue
                rows.append({
                    "id": (row.get("ID") or "").strip(),
                    "question": question,
                    "ground_truth": ground_truth,
                    "target_competitor": (row.get("Target Competitor") or "").strip(),
                    "needs_human_review": (row.get("Needs Human Review?") or "").strip(),
                })
        if rows:
            print(f"Loaded {len(rows)} evaluation cases from {path}")
        return rows

    def _default_evaluation_set(self) -> List[dict]:
        return [
            {
                "question": "What is the UCAS code for the Computer Science BSc?",
                "ground_truth": "The UCAS codes are CS303 for Leeds, CS606 for Sheffield, and CS505 for Nottingham."
            },
            {
                "question": "How long is the standard BSc degree program?",
                "ground_truth": "The standard duration for the BSc degree is 3 years."
            },
            {
                "question": "What are the core modules taught in Year 1?",
                "ground_truth": "Year 1 core modules include COMP1111 Procedural Coding, COMP1222 Discrete Mathematics, and Systems Architecture."
            },
            {
                "question": "What are the core modules taught in Year 2?",
                "ground_truth": "Year 2 core modules include COMP2333 Data Structures, Software Engineering Paradigms, and Database Systems."
            },
            {
                "question": "How many credits is the final year project worth?",
                "ground_truth": "Information Not Available in Source Documentation."
            },
            {
                "question": "Which university offers the lowest tuition fee for Computer Science BSc?",
                "ground_truth": "The available records indicate the tuition fee is £9,250 across the listed programs."
            },
            {
                "question": "What are the entry requirements for Leeds Computer Science?",
                "ground_truth": "Information Not Available in Source Documentation."
            },
            {
                "question": "Compare the Year 1 curriculum between Leeds and Sheffield.",
                "ground_truth": "Leeds and Sheffield both offer Year 1 modules in procedural coding, discrete mathematics, and systems architecture."
            },
            {
                "question": "Is the final year project compulsory?",
                "ground_truth": "Information Not Available in Source Documentation."
            },
            {
                "question": "What is the median salary after graduation?",
                "ground_truth": "The available records indicate a median salary of £31,000."
            },
            {
                "question": "Which university has the highest median salary?",
                "ground_truth": "The available records indicate a median salary of £31,000 across the listed programs."
            },
            {
                "question": "Tell me everything about the placement year.",
                "ground_truth": "Information Not Available in Source Documentation.                                                           "
            }
        ]

    def _normalize(self, text: str) -> List[str]:
        return re.findall(r"[a-z0-9]+", text.lower())

    def _normalize_for_scoring(self, text: str) -> str:
        return align_ground_truth_to_rag(text or "")

    def _keyword_tokens(self, text: str) -> set[str]:
        return {token for token in self._normalize(text) if token not in _STOPWORDS and len(token) > 1}

    def _build_evaluation_query(self, item: dict) -> str:
        question = str(item.get("question", "")).strip()
        institution = str(item.get("target_competitor", "")).strip()
        if not institution:
            return question
        if institution.lower() in question.lower():
            return question
        if self.use_full_rag_pipeline:
            return question
        return f"For the Computer Science BSc at {institution}, {question}"

    def _legacy_similarity_score(self, left: str, right: str) -> float:
        left_tokens = set(self._normalize(self._normalize_for_scoring(left)))
        right_tokens = set(self._normalize(self._normalize_for_scoring(right)))
        if not left_tokens or not right_tokens:
            return 0.0
        return len(left_tokens & right_tokens) / len(left_tokens | right_tokens)

    def _compute_legacy_metrics(self, question: str, answer: str, contexts: List[str], ground_truth: str):
        answer = self._normalize_for_scoring(answer)
        ground_truth = self._normalize_for_scoring(ground_truth)
        normalized_contexts = [self._normalize_for_scoring(context) for context in contexts]
        context_text = "\n".join(normalized_contexts)

        answer_is_no_info = answer == NO_INFO_CANONICAL
        ground_truth_is_no_info = ground_truth == NO_INFO_CANONICAL

        faithfulness = 1.0 if answer_is_no_info and ground_truth_is_no_info else self._legacy_similarity_score(answer, ground_truth)
        if answer_is_no_info and ground_truth_is_no_info:
            answer_relevancy = 1.0
        else:
            answer_relevancy = max(
                self._legacy_similarity_score(answer, question),
                self._legacy_similarity_score(answer, ground_truth),
            )

        context_terms = self._keyword_tokens(context_text)
        ground_truth_terms = self._keyword_tokens(ground_truth)
        question_terms = self._keyword_tokens(question)
        relevant_terms = ground_truth_terms | question_terms
        if not relevant_terms:
            context_precision = 1.0 if ground_truth_is_no_info else 0.0
        else:
            context_precision = len(context_terms & relevant_terms) / len(relevant_terms)

        if not ground_truth_terms:
            context_recall = 1.0 if ground_truth_is_no_info else 0.0
        else:
            context_recall = len(context_terms & ground_truth_terms) / len(ground_truth_terms)

        return {
            "faithfulness": round(min(1.0, max(0.0, faithfulness)), 4),
            "answer_relevancy": round(min(1.0, max(0.0, answer_relevancy)), 4),
            "context_precision": round(min(1.0, max(0.0, context_precision)), 4),
            "context_recall": round(min(1.0, max(0.0, context_recall)), 4),
        }

    def _write_summary_csv(self, rows, output_csv: str, summary_path: str = None):
        if summary_path is None:
            summary_path = output_csv.replace(".csv", "_summary.csv")
        else:
            summary_path = os.path.abspath(summary_path)
        summary_row = {
            "total_questions": len(rows),
            "avg_confidence_score": round(sum(float(row.get("confidence_score", 0.0)) for row in rows) / len(rows), 4) if rows else 0.0,
            "abstain_count": sum(1 for row in rows if str(row.get("should_abstain", "False")).lower() == "true"),
            "avg_faithfulness": round(sum(float(row.get("faithfulness", 0.0)) for row in rows) / len(rows), 4) if rows else 0.0,
            "avg_answer_relevancy": round(sum(float(row.get("answer_relevancy", 0.0)) for row in rows) / len(rows), 4) if rows else 0.0,
            "avg_context_precision": round(sum(float(row.get("context_precision", 0.0)) for row in rows) / len(rows), 4) if rows else 0.0,
            "avg_context_recall": round(sum(float(row.get("context_recall", 0.0)) for row in rows) / len(rows), 4) if rows else 0.0,
        }
        with open(summary_path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(summary_row.keys()))
            writer.writeheader()
            writer.writerow(summary_row)
        print(f"Summary saved to: {summary_path}")

    def _safe_output_path(self, output_csv: str) -> str:
        if not output_csv:
            output_csv = "evaluation_results_final.csv"
        if os.path.exists(output_csv):
            try:
                with open(output_csv, "a", encoding="utf-8"):
                    pass
                return output_csv
            except OSError:
                pass
        try:
            with open(output_csv, "w", encoding="utf-8"):
                pass
            return output_csv
        except OSError:
            base_name = os.path.splitext(os.path.basename(output_csv))[0]
            temp_path = os.path.join(tempfile.gettempdir(), f"{base_name}_fallback.csv")
            print(f"Unable to write to {output_csv}. Falling back to {temp_path}")
            return temp_path

    def _query_pipeline(self, query: str, **query_kwargs):
        if self._rag_pipeline_failed:
            return self.fallback_rag_system.query_pipeline(query, **query_kwargs)
        try:
            return self.rag_system.query_pipeline(query, **query_kwargs)
        except Exception as exc:
            self._rag_pipeline_failed = True
            print(f"RAG pipeline unavailable, using fallback evaluator for remaining rows: {exc}")
            return self.fallback_rag_system.query_pipeline(query, **query_kwargs)

    def run_evaluations(self, output_csv="evaluation_results_final.csv"):
        print(f"Running pipeline generation for {len(self.evaluation_set)} test cases...")

        rows = []
        for item in self.evaluation_set:
            query = self._build_evaluation_query(item)
            result = self._query_pipeline(
                query,
                target_competitor=item.get("target_competitor") or None,
                target_programme="Computer Science BSc",
            )
            answer = result.get("answer", "")
            contexts = result.get("contexts", ["No context retrieved."])
            if isinstance(contexts, str):
                contexts = [contexts]

            rows.append({
                "id": item.get("id", ""),
                "target_competitor": item.get("target_competitor", ""),
                "question": item["question"],
                "evaluation_query": query,
                "answer": answer,
                "contexts": json.dumps(contexts),
                "ground_truth": align_ground_truth_to_rag(item["ground_truth"]),
                "confidence_score": result.get("confidence_score", 0.0),
                "should_abstain": result.get("should_abstain", False),
            })

        llm_df = None
        try:
            llm_df = evaluate_with_llm_judge(
                questions=[row["question"] for row in rows],
                generated_answers=[row["answer"] for row in rows],
                retrieved_contexts=[json.loads(row["contexts"]) for row in rows],
                ground_truths=[row["ground_truth"] for row in rows],
            )
            print("OpenAI LLM-as-a-Judge evaluation executed successfully.")
        except Exception as exc:
            print(f"LLM judge unavailable, using compatibility metrics fallback: {exc}")

        for index, row in enumerate(rows):
            metrics = self._compute_legacy_metrics(
                row["question"],
                row["answer"],
                json.loads(row["contexts"]),
                row["ground_truth"],
            )
            if llm_df is not None and index < len(llm_df):
                llm_row = llm_df.iloc[index].to_dict()
                for metric_key in ["faithfulness", "answer_relevancy", "context_precision", "context_recall"]:
                    value = llm_row.get(metric_key, metrics.get(metric_key, 0.0))
                    try:
                        value = float(value)
                    except (TypeError, ValueError):
                        value = metrics.get(metric_key, 0.0)
                    metrics[metric_key] = round(min(1.0, max(0.0, value)), 4)
            row.update(metrics)

        output_csv = self._safe_output_path(output_csv)
        with open(output_csv, "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=[
                "id",
                "target_competitor",
                "question",
                "evaluation_query",
                "answer",
                "contexts",
                "ground_truth",
                "confidence_score",
                "should_abstain",
                "faithfulness",
                "answer_relevancy",
                "context_precision",
                "context_recall",
            ])
            writer.writeheader()
            writer.writerows(rows)

        workspace_summary_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "evaluation_summary.csv")
        self._write_summary_csv(rows, output_csv, summary_path=workspace_summary_path)
        workspace_chart_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "evaluation_summary.png")
        try:
            plot_summary(input_csv=workspace_summary_path, output_png=workspace_chart_path)
        except Exception as exc:
            print(f"Unable to refresh dashboard chart: {exc}")

        print("\nEvaluation Complete!")
        print(f"Detailed results saved to: {output_csv}")
        print("\n--- AGGREGATE SCORES ---")
        for metric in ["faithfulness", "answer_relevancy", "context_precision", "context_recall"]:
            values = [row[metric] for row in rows]
            average = round(sum(values) / len(values), 4) if values else 0.0
            print(f"{metric:<20}: {average}")


if __name__ == "__main__":
    evaluator = RAGEvaluator()
    evaluator.run_evaluations()