import os
import re
from typing import List, Dict, Any
from dotenv import load_dotenv

# LangChain Imports
try:
    from langchain_community.document_loaders import PyPDFLoader, TextLoader, DirectoryLoader
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    from langchain_huggingface import HuggingFaceEmbeddings
    from langchain_chroma import Chroma
    from langchain_core.documents import Document
except ImportError:  # pragma: no cover - environment fallback
    PyPDFLoader = TextLoader = DirectoryLoader = None
    RecursiveCharacterTextSplitter = None
    HuggingFaceEmbeddings = None
    Chroma = None

    class Document:
        def __init__(self, page_content, metadata=None):
            self.page_content = page_content
            self.metadata = metadata or {}

# Disable ChromaDB telemetry logging
os.environ["CHROMA_TELEMETRY_IMPL"] = "None"

load_dotenv()


class DataIngestionPipeline:
    def __init__(self, db_directory: str = "./chroma_db", chunk_size: int = 300, chunk_overlap: int = 50):
        self.db_directory = db_directory
        
        if HuggingFaceEmbeddings is None or RecursiveCharacterTextSplitter is None:
            print("⚠️ LangChain vector dependencies are unavailable. Falling back to lightweight metadata-only ingestion.")
            self.embedding_engine = None
            self.text_splitter = None
        else:
            # 1. Initialize HuggingFace Embedding Model (matches rag_orchestrator.py)
            print("🔄 Loading HuggingFace Embedding Model (all-MiniLM-L6-v2)...")
            self.embedding_engine = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
            
            # 2. Text Splitter Configuration
            self.text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                separators=["\n\n", "\n", ". ", " ", ""],
                add_start_index=True,
            )

    def extract_metadata(self, text: str, source_file: str = "unknown") -> Dict[str, Any]:
        """
        Parses text and headers to auto-extract structured metadata tags.
        """
        metadata = {
            "university": "General / Unspecified",
            "course_code": "N/A",
            "academic_year": 0,  # 0 indicates non-year-specific content
            "content_type": "general",
            "source_url": source_file,
            "data_layer": "Unstructured Vector Document"
        }

        # 1. Detect University Name
        uni_patterns = [
            r"University of Liverpool",
            r"University of Leeds",
            r"University of Sheffield",
            r"University of Nottingham",
            r"University of Manchester",
            r"Lancaster University",
            r"Manchester Metropolitan University",
            r"Newcastle University"
        ]
        for pattern in uni_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                metadata["university"] = pattern
                break

        # 2. Detect UCAS / Course Code (e.g., CS303, CS505, CS606, CS202, CS909, CS101)
        code_match = re.search(r"\b(CS\d{3})\b", text, re.IGNORECASE)
        if code_match:
            metadata["course_code"] = code_match.group(1).upper()

        # 3. Detect Academic Year
        year_match = re.search(r"Year\s*([1-3])", text, re.IGNORECASE)
        if year_match:
            metadata["academic_year"] = int(year_match.group(1))

        # 4. Classify Content Type
        lower_text = text.lower()
        if any(kw in lower_text for kw in ["module", "procedural coding", "discrete mathematics", "curriculum", "syllabus", "structures", "credits", "project"]):
            metadata["content_type"] = "curriculum"
        if any(kw in lower_text for kw in ["tuition", "fee", "salary", "statistical profile", "employment", "leo", "entry requirement", "entry requirements", "placement", "international tuition"]):
            metadata["content_type"] = "financial_stats"

        return metadata

    def process_raw_text_records(self, raw_records: List[Dict[str, str]]):
        """
        Ingests directly passed structured dictionary inputs or text chunks.
        """
        print(f"\n📦 Processing {len(raw_records)} direct text records...")
        documents = []

        for record in raw_records:
            content = record.get("text", "")
            source_file = record.get("source", "direct_input")
            
            # Extract metadata
            metadata = self.extract_metadata(content, source_file)
            
            # Override metadata if explicitly passed in record
            if "university" in record:
                metadata["university"] = record["university"]
            if "academic_year" in record:
                metadata["academic_year"] = record["academic_year"]
            if "course_code" in record:
                metadata["course_code"] = record["course_code"]

            # Create LangChain Document
            doc = Document(page_content=content, metadata=metadata)
            documents.append(doc)

        if self.text_splitter is None:
            return documents

        # Split and store
        chunks = self.text_splitter.split_documents(documents)
        self._add_to_chroma(chunks)

    def load_and_ingest_files(self, data_folder: str = "./data"):
        """
        Scans a local directory for PDFs or TXT files, parses metadata, and ingests them.
        """
        if not os.path.exists(data_folder):
            os.makedirs(data_folder)
            print(f"📁 Created folder [{data_folder}]. Place your PDF/TXT source files there.")
            return

        print(f"\n📂 Scanning directory [{data_folder}] for documents...")
        all_docs = []

        # Load Text Files
        txt_loader = DirectoryLoader(data_folder, glob="*.txt", loader_cls=TextLoader)
        loaded_txt = txt_loader.load()
        
        # Load PDF Files
        pdf_loader = DirectoryLoader(data_folder, glob="*.pdf", loader_cls=PyPDFLoader)
        loaded_pdf = pdf_loader.load()

        raw_docs = loaded_txt + loaded_pdf
        
        if not raw_docs:
            print("⚠️ No PDF or TXT files found in the data directory.")
            return

        for doc in raw_docs:
            source = doc.metadata.get("source", "local_file")
            metadata = self.extract_metadata(doc.page_content, source)
            
            # Combine loader metadata with extracted metadata
            doc.metadata.update(metadata)
            all_docs.append(doc)

        if self.text_splitter is None:
            return all_docs

        # Split documents into chunks
        chunks = self.text_splitter.split_documents(all_docs)
        print(f"✂️ Created {len(chunks)} chunks from {len(raw_docs)} files.")

        self._add_to_chroma(chunks)

    def _add_to_chroma(self, chunks: List[Document]):
        """Persists document chunks into ChromaDB."""
        if Chroma is None or self.embedding_engine is None:
            print("⚠️ ChromaDB vector store unavailable. Skipping persistence.")
            return
        print("💾 Persisting chunks to ChromaDB vector store...")
        vector_store = Chroma(
            persist_directory=self.db_directory,
            embedding_function=self.embedding_engine
        )
        vector_store.add_documents(chunks)
        print(f"✅ Ingestion completed! Total chunks stored in [{self.db_directory}].")


# --- Demonstration & Direct Ingestion Execution ---
if __name__ == "__main__":
    pipeline = DataIngestionPipeline(db_directory="./chroma_db")

    # Sample dataset matching university evaluation scenarios
    sample_university_data = [
        {
            "text": "Official specification for University of Leeds (CS303): 3 years full-time. Entry Requirements: AAA including Mathematics. Year 1 modules include Procedural Coding, Discrete Mathematics, and Systems Architecture. The final-year project is worth 40 credits and there is an optional industrial placement year.",
            "university": "University of Leeds",
            "course_code": "CS303",
            "academic_year": 1,
            "source": "leeds_catalog_2026.pdf"
        },
        {
            "text": "University of Leeds financial profile: Home tuition fee is £9,250 per year; international tuition fee is £30,250. Median graduate salary after three years is £32,000 and the graduate employment rate is 88.5%.",
            "university": "University of Leeds",
            "course_code": "CS303",
            "academic_year": 0,
            "source": "leeds_financial_2026.pdf"
        },
        {
            "text": "University of Sheffield (CS606): 3 years full-time. Entry Requirements: A*AA including Mathematics. Year 1 modules include Java Programming, Discrete Mathematics, and Systems Architecture. The final-year project is worth 40 credits and the course offers a placement year.",
            "university": "University of Sheffield",
            "course_code": "CS606",
            "academic_year": 1,
            "source": "sheffield_catalog_2026.pdf"
        },
        {
            "text": "University of Sheffield financial profile: Home tuition fee is £9,250 per year; international tuition fee is £29,110. Median graduate salary after three years is £31,500 and the graduate employment rate is 86%.",
            "university": "University of Sheffield",
            "course_code": "CS606",
            "academic_year": 0,
            "source": "sheffield_financial_2026.pdf"
        },
        {
            "text": "University of Nottingham (CS505): 3 years full-time. Entry Requirements: A*AA including Mathematics. Year 1 modules include Programming and Systems Architecture. The final-year project is worth 30 credits with optional placement support.",
            "university": "University of Nottingham",
            "course_code": "CS505",
            "academic_year": 1,
            "source": "nottingham_catalog_2026.pdf"
        }
    ]

    # Ingest the sample records
    pipeline.process_raw_text_records(sample_university_data)

    # Optional: Scan local data folder for any extra files
    # pipeline.load_and_ingest_files(data_folder="./data")