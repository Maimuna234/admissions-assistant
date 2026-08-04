from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma

def run_semantic_audit_query(user_query, target_competitor):
    """
    Simulates a targeted lookup request from the orchestration layer.
    """
    embedding_engine = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    
    # Reload the persistent localized vector instance
    db = Chroma(persist_directory="./chroma_db", embedding_function=embedding_engine)
    
    print(f"\n🔍 Executing retrieval audit for query: '{user_query}'")
    print(f"🎯 Target Competitor Constraint Filter: '{target_competitor}'")
    
    # Apply a hard metadata filter constraint to isolate the targeted institution
    retriever_results = db.similarity_search(
        user_query,
        k=2,
        filter={"institution": target_competitor}
    )
    
    if not retriever_results:
        print("⚠️ Verification failure: No matching records returned from the index slice.")
        return

    # Print out results alongside their metadata to confirm tracking works
    for idx, doc in enumerate(retriever_results, 1):
        print(f"\n--- Retried Document Chunk #{idx} ---")
        print(f"📄 Content snippet: {doc.page_content}")
        print(f"🔖 Tracked Institution: {doc.metadata.get('institution')}")
        print(f"🔢 Target Course Code : {doc.metadata.get('course_code')}")
        print(f"📁 Target Data Layer  : {doc.metadata.get('data_layer')}")
        print(f"🔗 Verification Link  : {doc.metadata.get('source_url')}")

if __name__ == "__main__":
    # Test Scenario: Querying module structures specifically for Leeds
    run_semantic_audit_query(
        user_query="What modules are taught in year 1 and are there placements?", 
        target_competitor="University of Leeds"
    )