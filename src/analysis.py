"""
Analysis Module — Milestone 2
Features:
  - PDF text extraction (from local PDFs or abstract fallback)
  - Section-wise extraction: Abstract, Methodology, Conclusion
  - Key-finding extraction using research phrases
  - TF-IDF vectorization
  - Cosine similarity computation → similarity_results.json
  - Section-wise text files saved to data/sections/
  - Validation of extracted sections
"""

import json
import re
import math
import os
from pathlib import Path
from typing import List, Dict, Any, Tuple
from collections import Counter
from datetime import datetime

# ── Config import ─────────────────────────────────────────
try:
    from src.config import (
        PAPERS_DATA_FILE,
        ANALYSIS_RESULTS_FILE,
        DATA_DIR,
    )
    from src.utils import setup_logger
except ImportError:
    from config import PAPERS_DATA_FILE, ANALYSIS_RESULTS_FILE, DATA_DIR
    from utils import setup_logger

logger = setup_logger(__name__)

# ── Output paths ──────────────────────────────────────────
SECTIONS_DIR          = DATA_DIR / "sections"
SIMILARITY_FILE       = DATA_DIR / "similarity_results.json"

# ── NLP constants ─────────────────────────────────────────
SECTION_LABELS = ['abstract', 'background', 'objective', 'methods', 'results', 'conclusion']

FINDING_PHRASES = [
    'outperformed', 'achieved', 'accuracy', 'efficiency', 'reduced', 'improved',
    'demonstrated', 'showed', 'results indicate', 'we found', 'our approach',
    'significantly', 'state-of-the-art', 'benchmark', 'performance',
]

METHOD_PHRASES = [
    'proposed', 'introduced', 'method', 'algorithm', 'framework', 'architecture',
    'approach', 'model', 'technique', 'system', 'pipeline', 'trained', 'fine-tuned',
    'evaluated', 'implemented', 'designed',
]

CONCLUSION_PHRASES = [
    'conclude', 'conclusion', 'summary', 'future work', 'in summary',
    'in conclusion', 'we have shown', 'this paper presents', 'overall',
]

STOPWORDS = set([
    'the', 'and', 'of', 'in', 'to', 'a', 'is', 'for', 'with', 'on', 'that',
    'by', 'as', 'are', 'this', 'it', 'be', 'an', 'at', 'or', 'from', 'we',
    'our', 'can', 'was', 'has', 'have', 'not', 'but', 'which', 'also', 'its',
    'their', 'they', 'such', 'these', 'more', 'been', 'than', 'into', 'paper',
    'show', 'use', 'used', 'using', 'based', 'both', 'each', 'may', 'when',
    'will', 'about', 'between', 'while', 'other', 'how', 'new', 'two',
])


# ═══════════════════════════════════════════════════════════
# TF-IDF ENGINE (pure stdlib — no sklearn dependency)
# ═══════════════════════════════════════════════════════════

def _tokenize(text: str) -> List[str]:
    """Lowercase, strip punctuation, remove stopwords, min length 3."""
    tokens = re.findall(r'\b[a-z]{3,}\b', text.lower())
    return [t for t in tokens if t not in STOPWORDS]


def _compute_tf(tokens: List[str]) -> Dict[str, float]:
    """Term frequency (normalized)."""
    if not tokens:
        return {}
    counts = Counter(tokens)
    total  = len(tokens)
    return {term: count / total for term, count in counts.items()}


def _compute_idf(documents: List[List[str]]) -> Dict[str, float]:
    """Inverse document frequency with smoothing."""
    N = len(documents)
    df: Dict[str, int] = {}
    for doc in documents:
        for term in set(doc):
            df[term] = df.get(term, 0) + 1
    return {term: math.log((N + 1) / (count + 1)) + 1 for term, count in df.items()}


def _tfidf_vector(tf: Dict[str, float], idf: Dict[str, float]) -> Dict[str, float]:
    return {term: tf_val * idf.get(term, 1.0) for term, tf_val in tf.items()}


def _cosine_similarity(vec_a: Dict[str, float], vec_b: Dict[str, float]) -> float:
    """Cosine similarity between two TF-IDF vectors."""
    common = set(vec_a) & set(vec_b)
    if not common:
        return 0.0
    dot    = sum(vec_a[t] * vec_b[t] for t in common)
    norm_a = math.sqrt(sum(v**2 for v in vec_a.values()))
    norm_b = math.sqrt(sum(v**2 for v in vec_b.values()))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return round(dot / (norm_a * norm_b), 4)


# ═══════════════════════════════════════════════════════════
# PDF TEXT EXTRACTION
# ═══════════════════════════════════════════════════════════

def _extract_text_from_pdf(pdf_path: str) -> str:
    """
    Extract plain text from a local PDF file.
    Uses PyPDF2 if available, otherwise falls back gracefully.
    """
    try:
        import PyPDF2  # optional dependency
        text_parts = []
        with open(pdf_path, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            for page in reader.pages:
                text_parts.append(page.extract_text() or "")
        return "\n".join(text_parts)
    except ImportError:
        logger.warning("[ANALYSIS] PyPDF2 not installed — using abstract as text source")
        return ""
    except Exception as e:
        logger.warning(f"[ANALYSIS] PDF extraction failed for {pdf_path}: {e}")
        return ""


# ═══════════════════════════════════════════════════════════
# SECTION EXTRACTOR
# ═══════════════════════════════════════════════════════════

def extract_sections(text: str) -> Dict[str, str]:
    """
    Extract logical sections from text using keyword heuristics.
    Works on both full PDF text and abstracts.
    """
    # Try to find explicit section headers first (for full PDF text)
    header_patterns = {
        'abstract':    r'(?i)\babstract\b',
        'background':  r'(?i)\b(introduction|background)\b',
        'objective':   r'(?i)\b(objective|aim|goal|motivation)\b',
        'methods':     r'(?i)\b(method|methodology|approach|experiment|implementation)\b',
        'results':     r'(?i)\b(result|evaluation|finding|performance|experiment)\b',
        'conclusion':  r'(?i)\b(conclusion|summary|discussion|future work)\b',
    }

    sections: Dict[str, str] = {k: "" for k in SECTION_LABELS}

    # Split into sentences
    sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', text) if s.strip()]
    current = 'abstract'

    for sent in sentences:
        lower = sent.lower()
        # Detect section transitions
        if any(re.search(p, lower) for p in [r'\bintroduction\b', r'\bbackground\b']):
            current = 'background'
        elif any(w in lower for w in ['objective', 'aim', 'goal', 'propose', 'motivation']):
            current = 'objective'
        elif any(w in lower for w in METHOD_PHRASES):
            current = 'methods'
        elif any(w in lower for w in ['result', 'show', 'demonstrate', 'achieve', 'outperform', 'evaluate']):
            current = 'results'
        elif any(w in lower for w in CONCLUSION_PHRASES):
            current = 'conclusion'

        sections[current] += sent + " "

    return {k: v.strip() for k, v in sections.items()}


def _validate_sections(sections: Dict[str, str]) -> Dict[str, bool]:
    """Validate that key sections have meaningful content (>20 chars)."""
    return {k: len(v) > 20 for k, v in sections.items()}


# ═══════════════════════════════════════════════════════════
# KEY FINDINGS
# ═══════════════════════════════════════════════════════════

def identify_key_findings(paper: Dict[str, Any]) -> List[str]:
    """
    Extract key findings from a paper's abstract/results section.
    Prioritizes sentences with performance metrics or research phrases.
    """
    text = paper.get('abstract', '')
    sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', text) if s.strip()]
    findings = []

    for sent in sentences:
        lower = sent.lower()
        has_metric  = bool(re.search(r'\d+\.?\d*\s*%', sent))  # percentage
        has_number  = bool(re.search(r'\b\d+\.?\d+\b', sent))  # any number
        has_keyword = any(phrase in lower for phrase in FINDING_PHRASES)

        if has_keyword or (has_metric and has_number):
            findings.append(sent)

    if not findings:
        # Fallback: take the last 2 sentences (often conclusions/results)
        findings = sentences[-2:] if len(sentences) >= 2 else sentences
        if not findings:
            findings = ["No specific findings identified."]

    return findings[:5]  # cap at 5 findings per paper


# ═══════════════════════════════════════════════════════════
# SECTION FILE WRITER
# ═══════════════════════════════════════════════════════════

def _save_section_files(papers_analysis: List[Dict]) -> None:
    """
    Save section-wise text files to data/sections/<paper_idx>/<section>.txt
    """
    SECTIONS_DIR.mkdir(parents=True, exist_ok=True)

    for paper in papers_analysis:
        idx   = paper.get('id', 0)
        title = re.sub(r'[^\w\s-]', '', paper.get('title', f'paper_{idx}'))[:50].strip()
        title = re.sub(r'\s+', '_', title)
        paper_dir = SECTIONS_DIR / f"{idx:02d}_{title}"
        paper_dir.mkdir(parents=True, exist_ok=True)

        sections = paper.get('sections', {})
        for section_name, content in sections.items():
            if content:
                out_path = paper_dir / f"{section_name}.txt"
                out_path.write_text(content, encoding='utf-8')

        # Also write key findings
        findings = paper.get('key_findings', [])
        if findings:
            findings_path = paper_dir / "key_findings.txt"
            findings_path.write_text("\n\n".join(f"• {f}" for f in findings), encoding='utf-8')

    logger.info(f"[ANALYSIS] Section files saved → {SECTIONS_DIR}")


# ═══════════════════════════════════════════════════════════
# MAIN ANALYZER CLASS
# ═══════════════════════════════════════════════════════════

class PaperAnalyzer:
    """
    Milestone 2 analyzer:
    - PDF text extraction (with abstract fallback)
    - Section-wise extraction + validation
    - Key finding identification
    - TF-IDF vectorization
    - Cosine similarity matrix
    - Outputs: analysis_results.json, similarity_results.json, sections/
    """

    def __init__(self, papers_file: str = None):
        self.papers_file = Path(papers_file) if papers_file else PAPERS_DATA_FILE
        self.papers: List[Dict] = []
        self.results: Dict = {}
        self._initialize_results()
        self._load_papers()

    def _initialize_results(self):
        self.results = {
            "metadata": {
                "generated_at": datetime.now().isoformat(),
                "total_papers": 0,
                "successful_analyses": 0,
            },
            "papers": [],
            "cross_paper_analysis": {},
            "key_themes": [],
            "tfidf_vocabulary_size": 0,
        }

    def _load_papers(self):
        try:
            with open(self.papers_file, 'r', encoding='utf-8') as f:
                self.papers = json.load(f)
            logger.info(f"[ANALYSIS] Loaded {len(self.papers)} papers")
            self.results["metadata"]["total_papers"] = len(self.papers)
        except FileNotFoundError:
            logger.error(f"[ANALYSIS] Papers file not found: {self.papers_file}")
            self.papers = []
        except json.JSONDecodeError:
            logger.error(f"[ANALYSIS] Invalid JSON: {self.papers_file}")
            self.papers = []

    # ── Per-paper analysis ─────────────────────────────────
    def analyze_paper(self, paper: Dict, index: int) -> Dict:
        """Full analysis of a single paper."""
        # 1. Get text: prefer local PDF, fall back to abstract
        text = ""
        local_pdf = paper.get("local_pdf")
        if local_pdf and Path(local_pdf).exists():
            text = _extract_text_from_pdf(local_pdf)
            logger.info(f"[ANALYSIS] Extracted text from PDF: {Path(local_pdf).name}")

        if not text:
            text = paper.get("abstract", "")

        # 2. Extract sections
        sections = extract_sections(text)

        # 3. Validate sections
        validation = _validate_sections(sections)

        # 4. Key findings
        findings = identify_key_findings(paper)

        # 5. Methodology extraction
        methodology = self._extract_methodology(text)

        return {
            "id":           index,
            "title":        paper.get("title", "Unknown"),
            "year":         paper.get("year", "Unknown"),
            "authors":      paper.get("authors", []),
            "venue":        paper.get("venue", ""),
            "citations":    paper.get("citations", 0),
            "url":          paper.get("url", ""),
            "source":       paper.get("source", "unknown"),
            "has_pdf":      bool(local_pdf and Path(local_pdf).exists()),
            "sections":     sections,
            "section_validation": validation,
            "key_findings": findings,
            "methodology":  methodology,
            "text_length":  len(text),
        }

    def _extract_methodology(self, text: str) -> Dict[str, List[str]]:
        """Extract methodology-related sentences."""
        sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', text) if s.strip()]
        approaches = []
        for sent in sentences:
            lower = sent.lower()
            if any(phrase in lower for phrase in METHOD_PHRASES):
                approaches.append(sent)
        return {"approaches": approaches[:5]}

    # ── TF-IDF + Cosine Similarity ─────────────────────────
    def compute_tfidf_and_similarity(self) -> Dict:
        """
        Build TF-IDF vectors for all papers and compute pairwise cosine similarity.
        Returns the full similarity matrix and ranked pairs.
        """
        papers = self.results['papers']
        if len(papers) < 2:
            logger.warning("[ANALYSIS] Need ≥2 papers for similarity computation")
            return {}

        # Build document corpus: title + abstract + all sections
        corpus_texts = []
        for p in papers:
            combined = p['title'] + " " + " ".join(p['sections'].values())
            corpus_texts.append(combined)

        # Tokenize
        tokenized = [_tokenize(t) for t in corpus_texts]

        # IDF over corpus
        idf = _compute_idf(tokenized)
        self.results['tfidf_vocabulary_size'] = len(idf)
        logger.info(f"[ANALYSIS] TF-IDF vocabulary: {len(idf)} terms")

        # TF-IDF vectors
        vectors = []
        for tokens in tokenized:
            tf  = _compute_tf(tokens)
            vec = _tfidf_vector(tf, idf)
            vectors.append(vec)

        # Pairwise cosine similarity matrix
        n = len(papers)
        matrix = [[0.0] * n for _ in range(n)]
        pairs  = []

        for i in range(n):
            for j in range(n):
                if i == j:
                    matrix[i][j] = 1.0
                elif j > i:
                    sim = _cosine_similarity(vectors[i], vectors[j])
                    matrix[i][j] = sim
                    matrix[j][i] = sim
                    pairs.append({
                        "paper_a_idx":   i,
                        "paper_b_idx":   j,
                        "paper_a_title": papers[i]['title'],
                        "paper_b_title": papers[j]['title'],
                        "similarity":    sim,
                    })

        # Sort pairs by similarity descending
        pairs.sort(key=lambda x: x['similarity'], reverse=True)

        # Top keywords per paper (top TF-IDF terms)
        top_terms = []
        for i, vec in enumerate(vectors):
            sorted_terms = sorted(vec.items(), key=lambda x: x[1], reverse=True)[:10]
            top_terms.append({
                "paper_idx": i,
                "title":     papers[i]['title'],
                "top_terms": [{"term": t, "score": round(s, 4)} for t, s in sorted_terms],
            })

        return {
            "matrix":    matrix,
            "pairs":     pairs,
            "top_terms": top_terms,
            "paper_titles": [p['title'] for p in papers],
        }

    # ── Cross-paper comparison ─────────────────────────────
    def cross_paper_comparison(self):
        """Keyword frequency, year distribution, citation stats."""
        papers = self.results['papers']
        if not papers:
            return

        all_text = " ".join(
            p['title'] + " " + " ".join(p['sections'].values())
            for p in papers
        ).lower()

        words = re.findall(r'\b[a-z]{4,}\b', all_text)
        filtered = [w for w in words if w not in STOPWORDS]
        common_keywords = Counter(filtered).most_common(10)

        years = [p.get('year') for p in papers if p.get('year') not in ('N/A', None)]
        year_dist = Counter(years)

        citations = [p.get('citations', 0) for p in papers if isinstance(p.get('citations'), int)]
        citation_stats = {
            "average": round(sum(citations) / len(citations), 1) if citations else 0,
            "max":     max(citations) if citations else 0,
            "min":     min(citations) if citations else 0,
            "total":   sum(citations),
        }

        self.results['cross_paper_analysis'] = {
            "common_keywords":  dict(common_keywords),
            "year_distribution": {str(k): v for k, v in year_dist.items()},
            "citation_analysis": citation_stats,
            "research_trends":  [f"Focus on '{k[0]}'" for k in common_keywords[:3]],
        }
        self.results['key_themes'] = [k[0] for k in common_keywords[:5]]

    # ── Main pipeline ──────────────────────────────────────
    def run_analysis(self) -> Dict:
        """Run the complete Milestone 2 analysis pipeline."""
        if not self.papers:
            logger.warning("[ANALYSIS] No papers to analyze.")
            return self.results

        print("\n[ANALYSIS] Starting Milestone 2 pipeline…")

        # Phase 1: Per-paper analysis
        print(f"[ANALYSIS] Phase 1: Analyzing {len(self.papers)} papers…")
        processed = []
        for i, paper in enumerate(self.papers):
            try:
                result = self.analyze_paper(paper, i)
                processed.append(result)
                self.results["metadata"]["successful_analyses"] += 1
                valid_count = sum(1 for v in result['section_validation'].values() if v)
                print(f"  [{i+1}/{len(self.papers)}] '{paper.get('title','?')[:50]}' "
                      f"— {valid_count}/{len(SECTION_LABELS)} sections, "
                      f"{len(result['key_findings'])} findings")
            except Exception as e:
                logger.error(f"[ANALYSIS] Error on paper {i}: {e}")

        self.results['papers'] = processed

        # Phase 2: Cross-paper comparison
        print("[ANALYSIS] Phase 2: Cross-paper comparison…")
        self.cross_paper_comparison()

        # Phase 3: TF-IDF + Cosine Similarity
        print("[ANALYSIS] Phase 3: TF-IDF vectorization + cosine similarity…")
        similarity_data = self.compute_tfidf_and_similarity()
        if similarity_data:
            self.results['similarity'] = {
                "matrix":      similarity_data['matrix'],
                "paper_titles": similarity_data['paper_titles'],
            }
            # Save similarity_results.json
            self._save_similarity(similarity_data)

        # Phase 4: Save section-wise text files
        print("[ANALYSIS] Phase 4: Saving section-wise text files…")
        _save_section_files(processed)

        print(f"\n[ANALYSIS] ✅ Complete: {self.results['metadata']['successful_analyses']} papers analyzed")
        return self.results

    # ── Persistence ────────────────────────────────────────
    def _save_analysis(self):
        """Save full analysis results to data/analysis_results.json."""
        try:
            ANALYSIS_RESULTS_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(ANALYSIS_RESULTS_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.results, f, indent=2, ensure_ascii=False)
            logger.info(f"[ANALYSIS] Saved → {ANALYSIS_RESULTS_FILE}")
        except Exception as e:
            logger.error(f"[ANALYSIS] Save error: {e}")

    def _save_similarity(self, similarity_data: Dict):
        """Save similarity_results.json to data/."""
        try:
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            with open(SIMILARITY_FILE, 'w', encoding='utf-8') as f:
                json.dump(similarity_data, f, indent=2, ensure_ascii=False)
            logger.info(f"[ANALYSIS] Similarity results saved → {SIMILARITY_FILE}")
        except Exception as e:
            logger.error(f"[ANALYSIS] Similarity save error: {e}")

    def print_summary(self):
        print(f"\n{'='*50}")
        print("ANALYSIS SUMMARY — Milestone 2")
        print(f"{'='*50}")
        m = self.results['metadata']
        print(f"Papers Analyzed : {m['successful_analyses']} / {m['total_papers']}")
        print(f"TF-IDF Vocab    : {self.results.get('tfidf_vocabulary_size', 0)} terms")

        if self.results.get('key_themes'):
            print(f"Key Themes      : {', '.join(self.results['key_themes'])}")

        sim = self.results.get('similarity', {})
        matrix = sim.get('matrix', [])
        if matrix and len(matrix) >= 2:
            print("\nCosine Similarity Matrix:")
            titles = sim.get('paper_titles', [])
            for i, row in enumerate(matrix):
                label = (titles[i][:30] + '…') if i < len(titles) else f"Paper {i}"
                scores = "  ".join(f"{v:.3f}" for v in row)
                print(f"  [{i}] {label:<33} {scores}")

        cross = self.results.get('cross_paper_analysis', {})
        if cross.get('research_trends'):
            print("\nResearch Trends:")
            for t in cross['research_trends']:
                print(f"  • {t}")

        print(f"\nOutputs:")
        print(f"  → data/analysis_results.json")
        print(f"  → data/similarity_results.json")
        print(f"  → data/sections/  (section-wise text files)")
        print(f"{'='*50}\n")


# ── CLI ───────────────────────────────────────────────────
def main():
    analyzer = PaperAnalyzer()
    analyzer.run_analysis()
    analyzer._save_analysis()
    analyzer.print_summary()


if __name__ == "__main__":
    main()


# ═══════════════════════════════════════════════════════════
# REFERENCE-COMPATIBLE STANDALONE FUNCTIONS
# (ported from ai_research_agent-riya-dasgupta reference project)
# ═══════════════════════════════════════════════════════════

def extract_sections_from_text(text: str) -> Dict[str, str]:
    """
    Extract abstract, methodology, and conclusion sections from raw text
    using simple keyword-boundary heuristics.
    Compatible with the reference project's text_extraction/section_extractor.py.

    Args:
        text: raw string extracted from a PDF or abstract

    Returns:
        dict with keys: abstract, methodology, conclusion
    """
    text_lower = text.lower()
    sections: Dict[str, str] = {"abstract": "", "methodology": "", "conclusion": ""}

    # Abstract: from "abstract" up to "introduction"
    if "abstract" in text_lower:
        start = text_lower.find("abstract")
        end   = text_lower.find("introduction", start)
        sections["abstract"] = text[start:end].strip() if end != -1 else text[start:start + 1500].strip()

    # Methodology: from "method" up to "result"
    if "method" in text_lower:
        start = text_lower.find("method")
        end   = text_lower.find("result", start)
        sections["methodology"] = text[start:end].strip() if end != -1 else text[start:start + 2000].strip()

    # Conclusion: from "conclusion" to end of document
    if "conclusion" in text_lower:
        start = text_lower.find("conclusion")
        sections["conclusion"] = text[start:].strip()

    return sections


def process_all_text_files(input_folder: str, output_folder: str) -> None:
    """
    Read every .txt file in input_folder, extract sections, and save each
    result as a <name>_sections.json file in output_folder.
    Compatible with the reference project's text_extraction/section_extractor.py.

    Args:
        input_folder:  directory containing extracted .txt files
        output_folder: directory to write *_sections.json files
    """
    import os as _os

    _os.makedirs(output_folder, exist_ok=True)

    for filename in _os.listdir(input_folder):
        if not filename.endswith(".txt"):
            continue

        file_path = _os.path.join(input_folder, filename)
        with open(file_path, "r", encoding="utf-8") as fh:
            text = fh.read()

        sections = extract_sections_from_text(text)

        out_name = filename.replace(".txt", "_sections.json")
        out_path = _os.path.join(output_folder, out_name)
        with open(out_path, "w", encoding="utf-8") as fh:
            json.dump(sections, fh, indent=4, ensure_ascii=False)

        logger.info(f"[ANALYSIS] Section-wise data saved: {out_name}")


def validate_results(key_findings: dict, similarity_matrix) -> None:
    """
    Print a validation report to stdout showing how many findings were
    extracted per paper and whether the similarity matrix was generated.
    Compatible with the reference project's text_extraction/tfidf_similarity.py.

    Args:
        key_findings:     dict mapping paper name → list of finding sentences
        similarity_matrix: 2-D list/ndarray or None
    """
    print("\n--- Validation Report ---")

    for paper, findings in key_findings.items():
        if findings:
            print(f"{paper}: ✅ {len(findings)} key findings extracted")
        else:
            print(f"{paper}: ❌ No key findings extracted")

    if similarity_matrix is None:
        print("❌ Similarity matrix could not be generated")
    else:
        print("✅ Similarity matrix generated successfully")


def save_similarity_results(
    key_findings: dict,
    similarity_matrix,
    output_path: str = "data/datasets/similarity_results.json",
) -> None:
    """
    Persist key findings and the cosine similarity matrix to a JSON file.
    Compatible with the reference project's text_extraction/tfidf_similarity.py.

    Args:
        key_findings:     dict mapping paper name → list of finding sentences
        similarity_matrix: 2-D list/ndarray or None
        output_path:      destination path (default: data/datasets/similarity_results.json)
    """
    import os as _os

    _os.makedirs(_os.path.dirname(output_path) or ".", exist_ok=True)

    # Convert numpy array to plain list if necessary
    try:
        matrix_list = similarity_matrix.tolist()
    except AttributeError:
        matrix_list = similarity_matrix if similarity_matrix is not None else []

    results = {
        "key_findings":      key_findings,
        "cosine_similarity": matrix_list,
    }

    with open(output_path, "w", encoding="utf-8") as fh:
        json.dump(results, fh, indent=4, ensure_ascii=False)

    logger.info(f"[ANALYSIS] Similarity results saved → {output_path}")


def extract_key_findings(section_folder: str):
    """
    Walk through *_sections.json files in section_folder, extract sentences
    that contain research finding phrases, and collect all section text for
    TF-IDF similarity.
    Compatible with the reference project's text_extraction/tfidf_similarity.py.

    Args:
        section_folder: directory containing *_sections.json files

    Returns:
        tuple(key_findings: dict, documents_for_similarity: list[str])
    """
    import os as _os

    KEY_PHRASES_REF = [
        "we propose", "we introduce", "our approach", "our method",
        "we demonstrate", "outperforms", "achieves state-of-the-art",
    ]

    key_findings: Dict[str, List[str]] = {}
    documents_for_similarity: List[str] = []

    for filename in _os.listdir(section_folder):
        if not filename.endswith("_sections.json"):
            continue

        file_path = _os.path.join(section_folder, filename)
        with open(file_path, "r", encoding="utf-8") as fh:
            sections = json.load(fh)

        combined = (
            sections.get("abstract", "") + " " +
            sections.get("methodology", "") + " " +
            sections.get("conclusion", "")
        ).lower()

        sentences = combined.split(".")
        matched: List[str] = []

        for sentence in sentences:
            for phrase in KEY_PHRASES_REF:
                if phrase in sentence:
                    matched.append(sentence.strip())
                    break

        paper_name = filename.replace("_sections.json", "")
        key_findings[paper_name] = matched
        documents_for_similarity.append(" ".join(matched))

    return key_findings, documents_for_similarity


def compare_papers_tfidf(documents: List[str]):
    """
    Compute a cosine-similarity matrix between papers using TF-IDF vectors.
    Compatible with the reference project's text_extraction/tfidf_similarity.py.

    Args:
        documents: list of strings (one per paper, e.g. joined key findings)

    Returns:
        numpy ndarray (n×n) or None if all documents are empty
    """
    if not documents or all(doc.strip() == "" for doc in documents):
        return None

    # Prefer sklearn if available; fall back to the pure-stdlib engine
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity as sk_cosine

        vectorizer   = TfidfVectorizer(stop_words="english")
        tfidf_matrix = vectorizer.fit_transform(documents)
        return sk_cosine(tfidf_matrix)

    except ImportError:
        # Fallback: use the module's own pure-stdlib TF-IDF engine
        tokenized = [_tokenize(doc) for doc in documents]
        idf       = _compute_idf(tokenized)
        vectors   = [_tfidf_vector(_compute_tf(tok), idf) for tok in tokenized]
        n = len(vectors)
        matrix = [[0.0] * n for _ in range(n)]
        for i in range(n):
            for j in range(n):
                if i == j:
                    matrix[i][j] = 1.0
                elif j > i:
                    sim = _cosine_similarity(vectors[i], vectors[j])
                    matrix[i][j] = sim
                    matrix[j][i] = sim
        return matrix

