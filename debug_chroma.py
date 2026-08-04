import os
import chromadb

# Update this path if your Chroma DB folder has a different name or location
CHROMA_PATH = "./chroma_db" 

def inspect_chroma_db():
    print("=" * 50)
    print("🔍 CHROMADB DIAGNOSTIC UTILITY")
    print("=" * 50)

    # 1. Check if directory exists
    if not os.path.exists(CHROMA_PATH):
        print(f"❌ Folder '{CHROMA_PATH}' was not found in: {os.getcwd()}")
        print("➡️ Action Required: Check where your chroma_db folder is stored and update 'CHROMA_PATH' at the top of this script.")
        return

    print(f"📁 Database path verified: {os.path.abspath(CHROMA_PATH)}\n")

    try:
        # 2. Connect to Chroma Client
        client = chromadb.PersistentClient(path=CHROMA_PATH)
        collections = client.list_collections()

        if not collections:
            print("❌ Database exists, but NO COLLECTIONS were found.")
            print("➡️ Action Required: You need to run your document ingestion pipeline to populate the database.")
            return

        print(f"✅ Found {len(collections)} collection(s):\n")

        # 3. Inspect each collection
        for col in collections:
            doc_count = col.count()
            print(f"📌 Collection Name: '{col.name}'")
            print(f"   Total Chunks Stored: {doc_count}")

            if doc_count > 0:
                print("   --- Chunk Preview (First Stored Entry) ---")
                peek_data = col.peek(limit=1)
                
                if peek_data and peek_data.get('documents'):
                    sample_text = peek_data['documents'][0]
                    # Truncate text preview for readability
                    preview = sample_text[:250].replace('\n', ' ')
                    print(f"   Text: \"{preview}...\"\n")
                else:
                    print("   ⚠️ Collection exists, but contains no text documents.\n")
            else:
                print("   ⚠️ Collection exists, but has 0 total chunks.\n")

    except Exception as e:
        print(f"❌ Error connecting to ChromaDB: {e}")

if __name__ == "__main__":
    inspect_chroma_db()