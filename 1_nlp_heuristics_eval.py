import pandas as pd
import evaluate
import warnings
warnings.filterwarnings("ignore")

def run_nlp_evaluation(csv_path="golden_dataset1.csv"):
    print("--- Running Traditional NLP Heuristic Evaluation ---")
    df = pd.read_csv(csv_path)
    
    # In a real run, you would populate 'Generated_Answer' by calling your FastAPI endpoint for each df['Question']
    # For demonstration, we assume the dataset has been appended with a 'Generated_Answer' column after inference
    if 'Generated_Answer' not in df.columns:
        print("Note: Mocking 'Generated_Answer' for demonstration. Replace with actual API calls.")
        df['Generated_Answer'] = df['GroundTruth'] # Mocking perfect answers

    predictions = df['Generated_Answer'].tolist()
    references = df['GroundTruth'].tolist()

    # Initialize HuggingFace evaluate modules
    bleu = evaluate.load("bleu")
    rouge = evaluate.load("rouge")
    bertscore = evaluate.load("bertscore")

    # Calculate BLEU-4
    bleu_results = bleu.compute(predictions=predictions, references=references)
    print(f"BLEU Score: {bleu_results['bleu']:.4f}")

    # Calculate ROUGE-L
    rouge_results = rouge.compute(predictions=predictions, references=references)
    print(f"ROUGE-L Score: {rouge_results['rougeL']:.4f}")

    # Calculate BERTScore (using a lightweight model for speed)
    bert_results = bertscore.compute(predictions=predictions, references=references, lang="en")
    avg_bert_f1 = sum(bert_results['f1']) / len(bert_results['f1'])
    print(f"BERTScore (Average F1): {avg_bert_f1:.4f}")
    print("----------------------------------------------------\n")

if __name__ == "__main__":
    run_nlp_evaluation()