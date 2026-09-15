import os
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

try:
    # Use the OS certificate store (fixes TLS errors behind corporate/antivirus proxies on Windows).
    import truststore

    truststore.inject_into_ssl()
except ImportError:
    pass

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
CHUNKS_PATH = DATA_DIR / "chunks.jsonl"
INDEX_DIR = DATA_DIR / "index"

# Local embedding model (runs on CPU, ~130 MB). BGE expects an instruction prefix on queries only.
EMBED_MODEL = os.getenv("EMBED_MODEL", "BAAI/bge-small-en-v1.5")
BGE_QUERY_PREFIX = "Represent this sentence for searching relevant passages: "

CHUNK_SIZE = 900
CHUNK_OVERLAP = 150
TOP_K = int(os.getenv("TOP_K", "5"))
# Extra passages always searched from the practice's own information, so clinic details are never
# crowded out by the much larger general-guidance corpus.
CLINIC_K = int(os.getenv("CLINIC_K", "2"))
# ...but only when they're actually relevant (cosine similarity), so general questions aren't padded.
CLINIC_MIN_SCORE = float(os.getenv("CLINIC_MIN_SCORE", "0.55"))

USER_AGENT = "oral-health-rag/0.1 (educational prototype; +https://github.com/MuhammadIshaq-AI/oral-health-rag)"
