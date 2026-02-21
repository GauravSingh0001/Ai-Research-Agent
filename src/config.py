import os
from pathlib import Path
from dotenv import load_dotenv

# Base Directories
# Base Directories
if os.environ.get("VERCEL"):
    BASE_DIR = Path("/tmp")
    DATA_DIR = BASE_DIR / "data"
    OUTPUT_DIR = BASE_DIR / "output"
    SRC_DIR = Path(__file__).resolve().parent  # Keep source code location
    
    # Ensure directories exist in /tmp
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
else:
    BASE_DIR = Path(__file__).resolve().parent.parent
    DATA_DIR = BASE_DIR / "data"
    OUTPUT_DIR = BASE_DIR / "output"
    SRC_DIR = BASE_DIR / "src"

# Load environment variables
# Load environment variables
if not os.environ.get("VERCEL"):
    load_dotenv(BASE_DIR / ".env")
else:
    # On Vercel, env vars are injected by the platform
    pass

# API Configuration
SEMANTIC_SCHOLAR_API_URL = "https://api.semanticscholar.org/graph/v1/paper/search"
SEMANTIC_SCHOLAR_API_KEY = os.getenv("SEMANTIC_SCHOLAR_API_KEY")
SEMANTIC_SCHOLAR_API_KEY_SECONDARY = os.getenv("SEMANTIC_SCHOLAR_API_KEY_SECONDARY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GPT_MODEL = os.getenv("GPT_MODEL", "meta-llama/Llama-3.1-8B-Instruct")  # HF Router compatible
HF_BASE_URL = "https://router.huggingface.co/v1"  # Use HF router endpoint (recommended)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
COHERE_API_KEY = os.getenv("COHERE_API_KEY")
COHERE_MODEL = os.getenv("COHERE_MODEL", "command-r-plus")  # Primary provider model
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# Search Configuration
SEARCH_FIELDS = "title,authors,year,abstract,url,openAccessPdf,citationCount,venue,publicationDate"
SEARCH_LIMIT_DEFAULT = 3
SEARCH_TIMEOUT_SECONDS = 10

# File Paths
PAPERS_DATA_FILE = DATA_DIR / "papers.json"
ANALYSIS_RESULTS_FILE = DATA_DIR / "analysis_results.json"
RESEARCH_SYNTHESIS_FILE = OUTPUT_DIR / "research_synthesis.md"
SECTIONS_DATA_FILE = OUTPUT_DIR / "document_sections.json"
BIBTEX_FILE = OUTPUT_DIR / "references.bib"

# Writing Configuration
ABSTRACT_WORD_LIMIT = 100
