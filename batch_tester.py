import time
import pandas as pd
from rag_orchestrator import AdmissionsRAGOrchestrator

# 1. Initialize the pipeline
print("Initializing RAG Orchestrator for Batch Testing...")
rag = AdmissionsRAGOrchestrator()

# 2. Define the test batch with diverse scenarios
test_batch = [
    {
        "test_id": "T01",
        "type": "Standard Retrieval",
        "query": "What are the core modules taught in year 1?",
        "target": "University of Leeds"
    },
    {
        "test_id": "T02",
        "type": "Guardrail Audit",
        "query": "What is the name of the university president's dog?",
        "target": "University of Leeds"
    },
    {
        "test_id": "T03",
        "type": "Metadata Filter Check",
        "query": "What are the international tuition fees?",
        "target": "University of Manchester"
    },
    {
        "test_id": "T04",
        "type": "Complex Synthesis",
        "query": "Summarize the placement year options and graduate salaries.",
        "target": "University of Leeds"
    }
]

results_log = []

print(f"\n🚀 Starting Batch Execution ({len(test_batch)} queries)...\n")

for item in test_batch:
    print(f"Executing {item['test_id']} - {item['type']}...")
    
    # Run the query
    result = rag.query_pipeline(
        user_query=item['query'],
        target_competitor=item['target']
    )
    
    # Check if the guardrail activated properly
    guardrail_status = "Activated" if "Information Not Available" in result['answer'] else "Passed"
    
    results_log.append({
        "Test ID": item['test_id'],
        "Test Category": item['type'],
        "Target": item['target'],
        "Engine": result['engine_used'],
        "Latency (s)": result['latency_seconds'],
        "Guardrail": guardrail_status
    })
    
    # Mandatory delay to prevent API rate limits during automated testing
    time.sleep(2)

# 3. Compile and analyze results
df_results = pd.DataFrame(results_log)
print("\n📊 BATCH TEST RESULTS:")
print(df_results.to_markdown(index=False))

# 4. Latency Constraint Validation
avg_latency = df_results["Latency (s)"].mean()
print(f"\n⏱️ Average Latency: {avg_latency:.3f} seconds")

# Validating against your project's 3.5s constraint
if avg_latency <= 3.5:
    print("✅ System successfully meets the 3.5s maximum latency constraint.")
else:
    print("⚠️ Warning: System exceeds the 3.5s latency constraint. Profiling recommended.")