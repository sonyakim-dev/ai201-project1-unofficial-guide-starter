import os

from dotenv import load_dotenv

load_dotenv()

# Anchor every path to this file's directory so the pipeline works no matter
# what the current working directory is when a script is run.
HERE = os.path.dirname(os.path.abspath(__file__))

# --- LLM ---
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
LLM_MODEL = "llama-3.3-70b-versatile"

# --- Embeddings ---
EMBEDDING_MODEL = "all-MiniLM-L6-v2"

# --- Vector store ---
CHROMA_COLLECTION = "cafes"
CHROMA_PATH = os.path.join(HERE, "chroma_db")   # gitignored local store

# --- Retrieval ---
N_RESULTS = 8

# --- Documents ---
DOCS_PATH = os.path.join(HERE, "documents")
RAW_DOCS_PATH = os.path.join(DOCS_PATH, "raw")
CAFES_PATH = os.path.join(DOCS_PATH, "cafes.json")     # structured records
CHUNKS_PATH = os.path.join(DOCS_PATH, "chunks.jsonl")  # one chunk per line
STAMP_PATH = os.path.join(DOCS_PATH, ".raw_manifest.json")  # tracks raw mtimes/sizes
