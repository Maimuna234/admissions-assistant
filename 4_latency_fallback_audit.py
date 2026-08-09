import time
import pandas as pd
import requests

# Constants based on NFRs
T_MAX_SECONDS = 3.5
FALLBACK_THRESHOLD_MS = 500

def mock_cloud_api_call(simulate_timeout=False):
    """Simulates a call to the primary LLM API (e.g., Gemini Cloud)."""
    if simulate_timeout:
        time.sleep(1.0) # Simulate 1 second delay (Network interruption)
        raise TimeoutError("Cloud API Rate Limited or Network Timeout")
    time.sleep(1.5) # Normal processing latency
    return "Cloud Model Response"

def mock_local_barkla2_call():
    """Simulates a localized Barkla2 HPC LLaMA3 fallback."""
    time.sleep(0.3) # 300ms execution time locally
    return "Fallback Barkla2 Response"

def query_orchestrator(query, trigger_failure=False):
    """Simulates your system's fallback logic."""
    start_time = time.time()
    
    try:
        # Attempt primary route
        response = mock_cloud_api_call(simulate_timeout=trigger_failure)
        route_used = "Primary (Cloud)"
    except TimeoutError:
        # Fallback Trigger Logic (< 500ms initiation)
        fallback_start = time.time()
        response = mock_local_barkla2_call()
        fallback_latency = (time.time() - fallback_start) * 1000
        print(f"   [Fallback Initiated] HPC execution took: {fallback_latency:.2f}ms")
        route_used = "Fallback (Barkla2 LLaMA3)"
        
    total_time = time.time() - start_time
    return response, total_time, route_used

def run_nfr_audit(csv_path="golden_dataset1.csv"):
    print("--- Running NFR Latency & Fallback Audit ---")
    df = pd.read_csv(csv_path)
    sample_queries = df['Question'].head(5).tolist() # Testing on first 5 scenarios
    
    for idx, query in enumerate(sample_queries):
        # Simulate network failure on the 3rd query to test fallback
        trigger_failure = (idx == 2) 
        print(f"\nScenario {idx+1}: Testing Failover={trigger_failure}")
        
        response, latency, route = query_orchestrator(query, trigger_failure=trigger_failure)
        
        print(f"   Route Executed: {route}")
        print(f"   Total End-to-End Latency: {latency:.3f}s")
        
        if latency <= T_MAX_SECONDS:
            print(f"   Status: PASS (Latency <= {T_MAX_SECONDS}s)")
        else:
            print(f"   Status: FAIL (Latency exceeded {T_MAX_SECONDS}s limit)")

    print("--------------------------------------------\n")

if __name__ == "__main__":
    run_nfr_audit()