"""
Search Module — Milestone 1
Features:
  - User input for multiple research topics
  - Semantic Scholar (primary) with arXiv fallback on rate-limit
  - Open-access PDF downloading to /pdfs
  - Topic-wise dataset creation → cleaned_dataset.json
  - Graceful handling: API rate limits, missing PDFs, empty results
"""

import json
import time
import re
import requests
from pathlib import Path
from typing import List, Dict, Any, Optional
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ── Config import ─────────────────────────────────────────
try:
    from src.config import (
        SEMANTIC_SCHOLAR_API_URL,
        SEMANTIC_SCHOLAR_API_KEY,
        SEARCH_FIELDS,
        SEARCH_LIMIT_DEFAULT,
        SEARCH_TIMEOUT_SECONDS,
        PAPERS_DATA_FILE,
        DATA_DIR,
    )
    from src.utils import setup_logger
except ImportError:
    from config import (
        SEMANTIC_SCHOLAR_API_URL,
        SEMANTIC_SCHOLAR_API_KEY,
        SEARCH_FIELDS,
        SEARCH_LIMIT_DEFAULT,
        SEARCH_TIMEOUT_SECONDS,
        PAPERS_DATA_FILE,
        DATA_DIR,
    )
    from utils import setup_logger

logger = setup_logger(__name__)

# ── Constants ─────────────────────────────────────────────
ARXIV_API_URL  = "http://export.arxiv.org/api/query"
PDFS_DIR       = DATA_DIR.parent / "pdfs"
CLEANED_DATASET_FILE = DATA_DIR / "cleaned_dataset.json"
PDF_TIMEOUT    = 30   # seconds per PDF download
MAX_PDF_SIZE   = 20 * 1024 * 1024  # 20 MB cap


# ── Session factory ───────────────────────────────────────
def _get_session() -> requests.Session:
    """Session with retry logic for transient errors."""
    session = requests.Session()
    retries = Retry(
        total=3,
        backoff_factor=1.5,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
        raise_on_status=False,
    )
    session.mount("https://", HTTPAdapter(max_retries=retries))
    session.mount("http://",  HTTPAdapter(max_retries=retries))
    if SEMANTIC_SCHOLAR_API_KEY:
        session.headers.update({"x-api-key": SEMANTIC_SCHOLAR_API_KEY})
    return session


# ── Semantic Scholar ──────────────────────────────────────
def _search_semantic_scholar(topic: str, limit: int, session: requests.Session) -> List[Dict]:
    """Search Semantic Scholar. Returns [] on rate-limit (caller falls back to arXiv)."""
    try:
        resp = session.get(
            SEMANTIC_SCHOLAR_API_URL,
            params={"query": topic.strip(), "limit": limit, "fields": SEARCH_FIELDS},
            timeout=SEARCH_TIMEOUT_SECONDS,
        )
        if resp.status_code == 429:
            logger.warning("[SEARCH] Semantic Scholar rate-limited (429) — will try arXiv fallback")
            return []
        resp.raise_for_status()
        data = resp.json().get("data", [])
        logger.info(f"[SEARCH] Semantic Scholar: {len(data)} papers for '{topic}'")
        return [_normalize_ss_paper(p) for p in data]
    except requests.exceptions.RequestException as e:
        logger.warning(f"[SEARCH] Semantic Scholar error: {e} — will try arXiv fallback")
        return []


def _normalize_ss_paper(p: dict) -> dict:
    return {
        "title":            p.get("title", "N/A"),
        "year":             p.get("year", "N/A"),
        "authors":          [a.get("name", "Unknown") for a in p.get("authors", [])],
        "abstract":         p.get("abstract") or "No abstract",
        "pdf":              (p.get("openAccessPdf") or {}).get("url"),
        "url":              p.get("url", ""),
        "citations":        p.get("citationCount", 0),
        "venue":            p.get("venue", "Unknown"),
        "publication_date": p.get("publicationDate", "Unknown"),
        "source":           "semantic_scholar",
    }


# ── arXiv fallback ────────────────────────────────────────
def _search_arxiv(topic: str, limit: int, session: requests.Session) -> List[Dict]:
    """Search arXiv as fallback. Parses Atom XML response."""
    try:
        resp = session.get(
            ARXIV_API_URL,
            params={"search_query": f"all:{topic}", "start": 0, "max_results": limit},
            timeout=SEARCH_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        return _parse_arxiv_xml(resp.text)
    except requests.exceptions.RequestException as e:
        logger.error(f"[SEARCH] arXiv error: {e}")
        return []


def _parse_arxiv_xml(xml: str) -> List[Dict]:
    """Minimal XML parser — avoids lxml/BeautifulSoup dependency."""
    papers = []
    entries = re.findall(r'<entry>(.*?)</entry>', xml, re.DOTALL)
    for entry in entries:
        def _tag(t):
            m = re.search(rf'<{t}[^>]*>(.*?)</{t}>', entry, re.DOTALL)
            return m.group(1).strip() if m else ""

        title    = re.sub(r'\s+', ' ', _tag('title'))
        abstract = re.sub(r'\s+', ' ', _tag('summary'))
        year_raw = _tag('published')[:4]
        authors  = re.findall(r'<name>(.*?)</name>', entry)
        pdf_link = re.search(r'<link[^>]+title="pdf"[^>]+href="([^"]+)"', entry)
        pdf_url  = pdf_link.group(1) if pdf_link else None
        arxiv_id = re.search(r'<id>(.*?)</id>', entry)
        url      = arxiv_id.group(1).strip() if arxiv_id else ""

        if title:
            papers.append({
                "title":            title,
                "year":             int(year_raw) if year_raw.isdigit() else "N/A",
                "authors":          authors,
                "abstract":         abstract or "No abstract",
                "pdf":              pdf_url,
                "url":              url,
                "citations":        0,
                "venue":            "arXiv",
                "publication_date": _tag('published')[:10],
                "source":           "arxiv",
            })
    logger.info(f"[SEARCH] arXiv: {len(papers)} papers parsed")
    return papers


# ── PDF downloader ────────────────────────────────────────
def download_pdf(paper: dict, topic_slug: str, session: requests.Session) -> Optional[Path]:
    """
    Download open-access PDF for a paper.
    Returns the local path on success, None on failure.
    """
    pdf_url = paper.get("pdf")
    if not pdf_url:
        return None

    PDFS_DIR.mkdir(parents=True, exist_ok=True)
    topic_dir = PDFS_DIR / topic_slug
    topic_dir.mkdir(parents=True, exist_ok=True)

    # Safe filename from title
    safe_title = re.sub(r'[^\w\s-]', '', paper.get("title", "paper"))[:60].strip()
    safe_title = re.sub(r'\s+', '_', safe_title)
    dest = topic_dir / f"{safe_title}.pdf"

    if dest.exists():
        logger.info(f"[PDF] Already downloaded: {dest.name}")
        paper["local_pdf"] = str(dest)
        return dest

    try:
        resp = session.get(pdf_url, timeout=PDF_TIMEOUT, stream=True)
        resp.raise_for_status()

        # Check content-type
        ct = resp.headers.get("Content-Type", "")
        if "pdf" not in ct and "octet-stream" not in ct:
            logger.warning(f"[PDF] Unexpected content-type '{ct}' for {pdf_url[:60]}")
            return None

        # Stream with size cap
        size = 0
        with open(dest, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                size += len(chunk)
                if size > MAX_PDF_SIZE:
                    logger.warning(f"[PDF] File too large (>{MAX_PDF_SIZE//1024//1024}MB), skipping")
                    dest.unlink(missing_ok=True)
                    return None
                f.write(chunk)

        logger.info(f"[PDF] Downloaded: {dest.name} ({size//1024} KB)")
        paper["local_pdf"] = str(dest)
        return dest

    except requests.exceptions.RequestException as e:
        logger.warning(f"[PDF] Download failed for '{paper.get('title','?')[:40]}': {e}")
        dest.unlink(missing_ok=True)
        return None


# ── Public API ────────────────────────────────────────────
def search_papers(topic: str, limit: int = SEARCH_LIMIT_DEFAULT) -> List[Dict[str, Any]]:
    """
    Search for papers on a topic.
    Primary: Semantic Scholar
    Fallback: arXiv (when rate-limited or empty result)
    """
    if not topic.strip():
        logger.error("[SEARCH] Topic cannot be empty")
        return []

    session = _get_session()

    # Primary: Semantic Scholar
    results = _search_semantic_scholar(topic, limit, session)

    # Fallback: arXiv
    if not results:
        logger.info("[SEARCH] Falling back to arXiv…")
        results = _search_arxiv(topic, limit, session)

    if not results:
        logger.warning(f"[SEARCH] No papers found for '{topic}' from any source")

    return results


def search_multiple_topics(topics: List[str], limit_per_topic: int = SEARCH_LIMIT_DEFAULT) -> Dict[str, List[Dict]]:
    """
    Search multiple topics and return a topic-keyed dict.
    Adds a 1-second delay between topics to respect rate limits.
    """
    dataset: Dict[str, List[Dict]] = {}
    for i, topic in enumerate(topics):
        topic = topic.strip()
        if not topic:
            continue
        logger.info(f"\n[SEARCH] Topic {i+1}/{len(topics)}: '{topic}'")
        papers = search_papers(topic, limit=limit_per_topic)
        dataset[topic] = papers
        logger.info(f"[SEARCH] Found {len(papers)} papers for '{topic}'")
        if i < len(topics) - 1:
            time.sleep(1)   # polite delay between topics
    return dataset


def download_pdfs_for_dataset(dataset: Dict[str, List[Dict]]) -> int:
    """
    Download PDFs for all papers in a multi-topic dataset.
    Returns count of successfully downloaded PDFs.
    """
    session = _get_session()
    total = 0
    for topic, papers in dataset.items():
        slug = re.sub(r'[^\w]', '_', topic)[:40]
        logger.info(f"\n[PDF] Downloading PDFs for topic: '{topic}'")
        for paper in papers:
            path = download_pdf(paper, slug, session)
            if path:
                total += 1
            time.sleep(0.3)  # small delay between downloads
    return total


def save_papers(papers: List[Dict[str, Any]]) -> bool:
    """Save flat papers list to data/papers.json (single-topic convenience)."""
    if not papers:
        logger.warning("[SEARCH] No papers to save")
        return False
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        with open(PAPERS_DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(papers, f, indent=2, ensure_ascii=False)
        logger.info(f"[SEARCH] Saved {len(papers)} papers → {PAPERS_DATA_FILE}")
        return True
    except Exception as e:
        logger.error(f"[SEARCH] Error saving papers: {e}")
        return False


def save_cleaned_dataset(dataset: Dict[str, List[Dict]]) -> bool:
    """
    Save multi-topic dataset to data/cleaned_dataset.json.
    Structure: { "topic": [...papers...], ... }
    Also flattens all papers into data/papers.json for downstream modules.
    """
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)

        # Save topic-wise cleaned dataset
        with open(CLEANED_DATASET_FILE, "w", encoding="utf-8") as f:
            json.dump(dataset, f, indent=2, ensure_ascii=False)
        logger.info(f"[SEARCH] Saved cleaned dataset → {CLEANED_DATASET_FILE}")

        # Also flatten into papers.json for analysis/writing modules
        all_papers = [p for papers in dataset.values() for p in papers]
        save_papers(all_papers)

        return True
    except Exception as e:
        logger.error(f"[SEARCH] Error saving cleaned dataset: {e}")
        return False


# ── CLI entry point ───────────────────────────────────────
def main():
    print(f"\n{'='*50}\n  PAPER SEARCH MODULE — Milestone 1\n{'='*50}")

    # User input: number of topics
    while True:
        try:
            n = int(input("\nHow many research topics do you want to search? ").strip())
            if n < 1:
                raise ValueError
            break
        except ValueError:
            print("  Please enter a positive integer.")

    topics = []
    for i in range(n):
        t = input(f"  Topic {i+1}: ").strip()
        if t:
            topics.append(t)

    if not topics:
        print("[ERROR] No valid topics entered.")
        return

    limit = SEARCH_LIMIT_DEFAULT
    try:
        lim_input = input(f"\nPapers per topic (default {limit}): ").strip()
        if lim_input:
            limit = max(1, int(lim_input))
    except ValueError:
        pass

    print(f"\n[INFO] Searching {len(topics)} topic(s), {limit} papers each…")
    dataset = search_multiple_topics(topics, limit_per_topic=limit)

    # Download PDFs
    dl = input("\nDownload open-access PDFs? (y/N): ").strip().lower()
    if dl == 'y':
        count = download_pdfs_for_dataset(dataset)
        print(f"[INFO] Downloaded {count} PDFs → pdfs/")

    # Save
    save_cleaned_dataset(dataset)
    total = sum(len(v) for v in dataset.values())
    print(f"\n[DONE] {total} papers saved across {len(topics)} topic(s)")
    print(f"  → data/cleaned_dataset.json")
    print(f"  → data/papers.json")


if __name__ == "__main__":
    main()


# ═══════════════════════════════════════════════════════════
# REFERENCE-COMPATIBLE STANDALONE FUNCTIONS
# (ported from ai_research_agent-riya-dasgupta reference project)
# ═══════════════════════════════════════════════════════════

def show_papers(topic: str, papers: List[Dict]) -> None:
    """
    Print a formatted summary of fetched papers to stdout.
    Compatible with the reference project's paper_search/paper_search.py.

    Args:
        topic:  the original search query string
        papers: list of paper dicts as returned by any search function
    """
    print(f"\nTopic: {topic}")

    for i, paper in enumerate(papers, start=1):
        authors = paper.get("authors", [])
        if isinstance(authors, list):
            authors_str = ", ".join(
                a.get("name", a) if isinstance(a, dict) else str(a)
                for a in authors
            )
        else:
            authors_str = str(authors)

        print(f"\nPaper {i}")
        print("Title:    ", paper.get("title", "N/A"))
        print("Authors:  ", authors_str or "N/A")
        print("Year:     ", paper.get("year", "N/A"))
        print("Abstract: ", (paper.get("abstract") or "")[:200])
        print("Link:     ", paper.get("url") or paper.get("pdf") or "N/A")
        print("-" * 40)


def show_references(references: List[Dict]) -> None:
    """
    Print a formatted reference list to stdout.
    Compatible with the reference project's paper_search/paper_search.py.

    Args:
        references: list of paper/reference dicts
    """
    for i, ref in enumerate(references, start=1):
        authors = ref.get("authors", [])
        if isinstance(authors, list):
            authors_str = ", ".join(
                a.get("name", a) if isinstance(a, dict) else str(a)
                for a in authors
            )
        else:
            authors_str = str(authors)

        print(f"\nReference {i}")
        print("Title:   ", ref.get("title", "N/A"))
        print("Authors: ", authors_str or "N/A")
        print("Year:    ", ref.get("year", "N/A"))
        print("Link:    ", ref.get("url") or ref.get("pdf") or "N/A")
        print("-" * 50)


def fetch_from_semantic_scholar(topic: str, limit: int = 5) -> Optional[List[Dict]]:
    """
    Simple Semantic Scholar fetch compatible with the reference project's
    paper_search/paper_search.py (no retry adapter, plain requests).

    Returns:
        list of raw paper dicts on success, None on rate-limit (429), [] on error
    """
    url = SEMANTIC_SCHOLAR_API_URL
    params = {
        "query": topic,
        "limit": limit,
        "fields": SEARCH_FIELDS,
    }
    headers = {}
    if SEMANTIC_SCHOLAR_API_KEY:
        headers["x-api-key"] = SEMANTIC_SCHOLAR_API_KEY

    try:
        resp = requests.get(url, params=params, headers=headers, timeout=SEARCH_TIMEOUT_SECONDS)

        if resp.status_code == 200:
            return resp.json().get("data", [])

        if resp.status_code == 429:
            logger.warning("[SEARCH] Semantic Scholar rate limited (429).")
            return None          # caller should switch to arXiv

    except requests.exceptions.RequestException as e:
        logger.warning(f"[SEARCH] Semantic Scholar exception: {e}")
        return None

    return []


def fetch_from_arxiv(topic: str, limit: int = 5) -> List[Dict]:
    """
    Fetch papers from the arXiv API.  Uses feedparser if installed;
    falls back to the module's built-in XML parser.
    Compatible with the reference project's paper_search/arxiv_search.py.

    Args:
        topic: search query string
        limit: max number of results to return

    Returns:
        list of paper dicts with keys: title, authors, year, abstract,
        paper_url/url, openAccessPdf
    """
    encoded = requests.utils.quote(topic)
    query   = f"search_query=all:{encoded}&start=0&max_results={limit}"
    url     = f"{ARXIV_API_URL}?{query}"

    # ── Try feedparser first (reference project uses it) ──
    try:
        import feedparser
        feed   = feedparser.parse(url)
        papers = []
        for entry in feed.entries:
            pdf_url = None
            for link in getattr(entry, "links", []):
                if getattr(link, "type", "") == "application/pdf":
                    pdf_url = link.href
                    break
            if not pdf_url and len(getattr(entry, "links", [])) > 1:
                pdf_url = entry.links[1].href

            papers.append({
                "title":         entry.title,
                "authors":       [a.name for a in getattr(entry, "authors", [])],
                "year":          entry.published[:4],
                "abstract":      entry.summary,
                "paper_url":     entry.link,
                "url":           entry.link,
                "openAccessPdf": {"url": pdf_url},
                "pdf":           pdf_url,
                "venue":         "arXiv",
                "source":        "arxiv",
            })
        logger.info(f"[SEARCH] arXiv (feedparser): {len(papers)} papers for '{topic}'")
        return papers

    except ImportError:
        # feedparser not installed — use the built-in XML parser
        pass

    session = _get_session()
    return _search_arxiv(topic, limit, session)


def fetch_papers_hybrid(topic: str, limit: int = 5) -> List[Dict]:
    """
    Try Semantic Scholar first; fall back to arXiv if rate-limited or on failure.
    Compatible with the reference project's paper_search/hybrid_search.py.

    Args:
        topic: search query string
        limit: max results per source

    Returns:
        list of paper dicts (possibly from different sources)
    """
    logger.info(f"[SEARCH] Hybrid search for: '{topic}'")
    print(f"\nSearching Semantic Scholar for: {topic}")

    papers = fetch_from_semantic_scholar(topic, limit)

    if papers:
        print("Papers fetched from Semantic Scholar")
        # Normalize to consistent schema
        return [_normalize_ss_paper(p) if "paperId" in p else p for p in papers]

    print("Switching to arXiv fallback…")
    papers = fetch_from_arxiv(topic, limit)

    if papers:
        print("Papers fetched from arXiv")
        return papers

    print("No papers found from any source.")
    return []

