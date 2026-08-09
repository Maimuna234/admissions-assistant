import pandas as pd
from datasets import Dataset
from ragas import evaluate
from ragas.metrics import (
    faithfulness,
    answer_relevancy,
    context_precision,
    context_recall
)

def run_ragas_evaluation(csv_path="golden_dataset1.csv"):
    print("--- Running RAGAS Triad Evaluation ---")
    df = pd.read_csv(csv_path)
    
    # To use RAGAS, data must be formatted with specific columns.
    # Replace these mock arrays with the actual inputs/outputs from your API evaluation run.
    data = {
        "question": df['Question'].tolist(),
        "answer": df['GroundTruth'].tolist(), # Replace with your model's actual Generated_Answer
        "contexts": [["Mock retrieved context 1", "Mock retrieved context 2"]] * len(df), # Replace with actual retrieved text chunks
        "ground_truth": df['GroundTruth'].tolist()
    }
    
    dataset = Dataset.from_dict(data)
    
    # Define the metrics to evaluate
    metrics = [
        faithfulness,
        answer_relevancy,
        context_precision,
        context_recall
    ]
    
    # Execute evaluation (Requires LLM API Key in environment variables)
    try:
        results = evaluate(dataset, metrics=metrics, raise_exceptions=False)
        print("RAGAS Results:\n", results)
        
        # Export to CSV for report inclusion
        results_df = results.to_pandas()
        results_df.to_csv("ragas_evaluation_results.csv", index=False)
        print("Results exported to 'ragas_evaluation_results.csv'")
    except Exception as e:
        print(f"Evaluation failed. Ensure your LLM API keys (e.g., OPENAI_API_KEY) are set. Error: {e}")
    print("--------------------------------------\n")

if __name__ == "__main__":
    run_ragas_evaluation()