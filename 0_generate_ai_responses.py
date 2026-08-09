import pandas as pd
import requests
import json
import time
from tqdm import tqdm

# Configuration
CSV_INPUT_PATH = "golden_dataset1.csv"
CSV_OUTPUT_PATH = "evaluated_golden_dataset1.csv"
API_URL = "http://127.0.0.1:8000/api/chat"

# Optional: Set this if your FastAPI endpoint requires an authorization header
API_KEY = "Bearer your_api_key_here"  # Change this if your API enforces _check_api_key

def generate_responses():
    print(f"Loading dataset from: {CSV_INPUT_PATH}")
    
    try:
        df = pd.read_csv(CSV_INPUT_PATH)
    except FileNotFoundError:
        print(f"Error: {CSV_INPUT_PATH} not found in the current directory.")
        return

    # Create new columns to hold the API outputs
    df["Generated_Answer"] = ""
    df["Retrieved_Contexts"] = ""
    df["Latency_Seconds"] = 0.0

    print(f"Starting batch generation for {len(df)} questions...")
    
    # Headers for the API request
    headers = {
        "Content-Type": "application/json",
        "Authorization": API_KEY 
    }

    # Iterate over the dataset with a progress bar
    for index, row in tqdm(df.iterrows(), total=len(df), desc="Processing Queries"):
        question = row.get("Question", "")
        competitor = row.get("Target Competitor", "")
        
        # Build the payload matching the openwebui_api.py /api/chat schema
        payload = {
            "question": question,
            "competitor_university": competitor if pd.notna(competitor) else "",
            # "priorities": ["Entry Requirements", "Fees & Cost"] # Add defaults if needed
        }
        
        start_time = time.time()
        try:
            # Send the request to the FastAPI endpoint
            response = requests.post(API_URL, headers=headers, json=payload, timeout=30)
            response.raise_for_status() # Raise an exception for bad status codes (4xx/5xx)
            
            data = response.json()
            
            # Extract the necessary fields based on the API response structure
            answer = data.get("answer", "No answer returned.")
            contexts = data.get("contexts", [])
            
            # Contexts might be a list of strings or dictionaries; safely join them
            if isinstance(contexts, list):
                if len(contexts) > 0 and isinstance(contexts[0], dict):
                    context_str = "\n---\n".join([json.dumps(c) for c in contexts])
                else:
                    context_str = "\n---\n".join([str(c) for c in contexts])
            else:
                context_str = str(contexts)
            
            df.at[index, "Generated_Answer"] = answer
            df.at[index, "Retrieved_Contexts"] = context_str
            df.at[index, "Latency_Seconds"] = data.get("latency_seconds", time.time() - start_time)
            
        except requests.exceptions.RequestException as e:
            print(f"\n[Warning] API call failed at index {index} (Question: '{question}'): {e}")
            df.at[index, "Generated_Answer"] = f"API_ERROR: {str(e)}"
            df.at[index, "Retrieved_Contexts"] = "API_ERROR"
            df.at[index, "Latency_Seconds"] = time.time() - start_time
            
        # Optional: slight delay to prevent rate-limiting on the LLM side during batch processing
        time.sleep(0.5)

    # Save the updated DataFrame
    df.to_csv(CSV_OUTPUT_PATH, index=False)
    print(f"\nBatch processing complete! Output saved to: {CSV_OUTPUT_PATH}")
    print(f"Preview of generated data:\n{df[['Question', 'Generated_Answer']].head(3)}")

if __name__ == "__main__":
    generate_responses()