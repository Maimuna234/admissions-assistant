import pandas as pd
import numpy as np

def calculate_mrr(retrieved_lists, relevant_docs):
    mrr_score = 0.0
    for retrieved, relevant in zip(retrieved_lists, relevant_docs):
        for rank, doc in enumerate(retrieved):
            if doc in relevant:
                mrr_score += 1.0 / (rank + 1)
                break
    return mrr_score / len(retrieved_lists)

def run_ir_evaluation():
    print("--- Running Information Retrieval (IR) Evaluation ---")
    # Simulating retrieval results for K=5
    K = 5
    
    # Mock data: In reality, extract the 'source_id' from your ChromaDB/SQLite metadata returns
    retrieved_chunks = [["doc_1", "doc_5", "doc_3", "doc_8", "doc_9"]] * 50 
    ground_truth_docs = [["doc_3", "doc_10"]] * 50 

    # Precision@K
    precisions = [len(set(ret[:K]) & set(rel)) / K for ret, rel in zip(retrieved_chunks, ground_truth_docs)]
    avg_precision = np.mean(precisions)

    # Recall@K
    recalls = [len(set(ret[:K]) & set(rel)) / len(rel) if len(rel) > 0 else 0 for ret, rel in zip(retrieved_chunks, ground_truth_docs)]
    avg_recall = np.mean(recalls)

    # MRR
    mrr = calculate_mrr(retrieved_chunks, ground_truth_docs)

    print(f"Precision@{K}: {avg_precision:.4f}")
    print(f"Recall@{K}: {avg_recall:.4f}")
    print(f"Mean Reciprocal Rank (MRR): {mrr:.4f}")
    print("---------------------------------------------------\n")

if __name__ == "__main__":
    run_ir_evaluation()