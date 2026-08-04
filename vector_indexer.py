import json
import os
from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma

class VectorIndexingPipeline:
    def __init__(self, db_directory="./chroma_db"):
        self.db_directory = db_directory
        self.kb_file = "clearing_knowledge_base.json"
        
        # Initialize an open-source sentence transformer model for local/Colab deployment
        # This maps text into a dense 384-dimensional vector space
        print("🔄 Loading embedding model engine...")
        self.embedding_engine = HuggingFaceEmbeddings(
            model_name="all-MiniLM-L6-v2",
            model_kwargs={'device': 'cpu'} # Change to 'cuda' if running on GPU/Colab
        )

    def process_kb_to_documents(self):
        """
        Loads the json dataset and creates individual LangChain Document objects
        with clean semantic text boundaries and exact metadata matrices.
        """
        if not os.path.exists(self.kb_file):
            raise FileNotFoundError(f"❌ Missing source file: {self.kb_file}. Run Phase 1 first!")

        with open(self.kb_file, "r", encoding="utf-8") as f:
            kb_data = json.load(f)

        documents_pool = []

        for entry in kb_data:
            uni_name = entry["university_name"]
            course_code = entry["course_code"]
            source_url = entry["metadata_reference"]["source_url"]
            
            # Extract and stringify quantitative metrics to create a baseline profile chunk
            metrics = entry["metrics"]
            metrics_text = (
                f"Statistical Profile for {uni_name} ({course_code}): "
                f"Annual tuition fee is £{metrics['annual_tuition_fee_uk']:,}. "
                f"Percentage of graduates in professional employment or further study "
                f"after 15 months is {metrics['graduate_in_work_15_months_pct']}%. "
                f"The Longitudinal Education Outcomes (LEO) median salary after 3 years is £{metrics['leo_median_salary_3_years']:,}."
            )
            
            # Base metadata assigned to every chunk from this institution
            base_metadata = {
                "institution": uni_name,
                "course_code": course_code,
                "source_url": source_url
            }

            # 1. Create a dedicated document chunk for the Quantitative Profile
            meta_metrics = base_metadata.copy()
            meta_metrics["data_layer"] = "quantitative_profile"
            documents_pool.append(Document(page_content=metrics_text, metadata=meta_metrics))

            # 2. Iterate through qualitative content layers to create isolated semantic chunks
            for layer_name, layer_content in entry["knowledge_layers"].items():
                if not layer_content or layer_content == "Information Not Listed":
                    continue
                
                # Format a highly specific text segment combining context and description
                human_readable_label = layer_name.replace("_", " ").title()
                chunk_text = f"Context Area [{human_readable_label}] for {uni_name} ({course_code}): {layer_content}"
                
                # Update metadata specifying the exact data layer type (SRS Requirement FR-2.3)
                meta_layer = base_metadata.copy()
                meta_layer["data_layer"] = layer_name
                
                documents_pool.append(Document(page_content=chunk_text, metadata=meta_layer))

        print(f"✅ Generated {len(documents_pool)} isolated context chunks from knowledge base.")
        return documents_pool

    def build_and_persist_vector_store(self, documents):
        """
        Initializes a persistent local ChromaDB instance and indexes the document embeddings.
        """
        print(f"📦 Committing records to persistent database at: {self.db_directory}...")
        
        # Instantiate Chroma and load the records
        vector_store = Chroma.from_documents(
            documents=documents,
            embedding=self.embedding_engine,
            persist_directory=self.db_directory
        )
        print("✅ Vector indexing and structural storage completed successfully.")
        return vector_store

    def run(self):
        docs = self.process_kb_to_documents()
        self.build_and_persist_vector_store(docs)

if __name__ == "__main__":
    pipeline = VectorIndexingPipeline()
    pipeline.run()