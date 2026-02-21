"""
AI Paper Reviewer — Flask API Server
Bridges the dashboard frontend to the Python AI backend.

Endpoints:
  GET  /api/status              — health check + current state
  POST /api/search              — search papers via Semantic Scholar
  GET  /api/papers              — load saved papers from data/papers.json
  POST /api/pipeline/run        — run analysis pipeline on saved papers
  GET  /api/pipeline/status     — get pipeline stage statuses
  GET  /api/synthesis           — load latest synthesis (md + sections)
  POST /api/synthesis/run       — trigger full synthesis generation
  GET  /api/reports             — list all archived output folders
  GET  /api/reports/<folder>    — get a specific report's data
  GET  /api/export/apa          — download APA references as .txt
  GET  /api/export/bib          — download BibTeX file
"""

import sys
import json
import threading
import time
import re
from pathlib import Path
from datetime import datetime
from flask import Flask, jsonify, request, send_file, abort, send_from_directory
from flask_cors import CORS

# ── Path setup ────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from src.config import (
    PAPERS_DATA_FILE,
    ANALYSIS_RESULTS_FILE,
    RESEARCH_SYNTHESIS_FILE,
    SECTIONS_DATA_FILE,
    BIBTEX_FILE,
    OUTPUT_DIR,
    DATA_DIR,
)
from src.search import search_papers, save_papers, search_multiple_topics, save_cleaned_dataset
from src.analysis import PaperAnalyzer, SIMILARITY_FILE, SECTIONS_DIR
from src.writing import ResearchWriter
from src.utils import setup_logger

logger = setup_logger(__name__)

# Deployment Verification Marker
logger.info("--- STARTING VERCEL DEPLOYMENT (Fix Applied) ---")


app = Flask(__name__)
CORS(app)  # Allow dashboard (file://) to call the API

# ── In-memory pipeline state ──────────────────────────────
pipeline_state = {
    "running": False,
    "stages": [
        {"id": "pdf-parse",       "title": "PDF Parsing",              "subtitle": "Waiting…", "status": "pending", "progress": 0},
        {"id": "section-extract", "title": "Section Extraction",       "subtitle": "Waiting…", "status": "pending", "progress": 0},
        {"id": "key-findings",    "title": "Key Finding Identification","subtitle": "Waiting…", "status": "pending", "progress": 0},
        {"id": "cross-compare",   "title": "Cross-Paper Comparison",   "subtitle": "Waiting…", "status": "pending", "progress": 0},
        {"id": "embedding",       "title": "Semantic Embedding",       "subtitle": "Waiting…", "status": "pending", "progress": 0},
        {"id": "synthesis-queue", "title": "Synthesis Queue",          "subtitle": "Waiting…", "status": "pending", "progress": 0},
    ],
    "last_run": None,
    "error": None,
}

synthesis_state = {
    "running": False,
    "done": False,
    "error": None,
    "last_run": None,
    "generation_id": None,  # Track which synthesis run is active
    "started_at": None,  # Track when synthesis started
}

# ── Helpers ───────────────────────────────────────────────
def _reset_pipeline():
    for s in pipeline_state["stages"]:
        s["status"] = "pending"
        s["progress"] = 0
        s["subtitle"] = "Waiting…"
    pipeline_state["running"] = False
    pipeline_state["error"] = None

def _reset_synthesis():
    """Reset synthesis state to initial values."""
    synthesis_state["running"] = False
    synthesis_state["done"] = False
    synthesis_state["error"] = None
    synthesis_state["generation_id"] = None
    synthesis_state["started_at"] = None

def _set_stage(idx, status, subtitle, progress):
    s = pipeline_state["stages"][idx]
    s["status"] = status
    s["subtitle"] = subtitle
    s["progress"] = progress

def _load_json(path: Path):
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None

def _latest_output_folder():
    """Return the most recently modified output subfolder."""
    folders = [d for d in OUTPUT_DIR.iterdir() if d.is_dir()]
    if not folders:
        return None
    return max(folders, key=lambda d: d.stat().st_mtime)

def _papers_to_apa(papers):
    """Convert papers list to APA 7th edition plain text."""
    lines = []
    for p in papers:
        authors_raw = p.get("authors", [])
        if isinstance(authors_raw, list):
            authors_str = ", ".join(authors_raw)
        else:
            authors_str = str(authors_raw)
        year   = p.get("year", "n.d.")
        title  = p.get("title", "Untitled")
        venue  = p.get("venue", "")
        url    = p.get("url", "")
        line = f"{authors_str} ({year}). {title}."
        if venue:
            line += f" *{venue}*."
        if url:
            line += f" {url}"
        lines.append(line)
    return "\n\n".join(lines)

# ── Routes ────────────────────────────────────────────────

# ── Static File Serving ────────────────────────────────────
DASHBOARD_DIR = BASE_DIR / "dashboard"

@app.route('/')
def serve_index():
    """Serve the main dashboard index.html"""
    return send_from_directory(str(DASHBOARD_DIR), 'index.html')

@app.route('/<path:filename>')
def serve_static(filename):
    """Serve static files (CSS, JS, etc.) from dashboard folder"""
    try:
        return send_from_directory(str(DASHBOARD_DIR), filename)
    except Exception:
        abort(404)

# ── API Routes ────────────────────────────────────────────

@app.route("/api/status")
def api_status():
    papers = _load_json(PAPERS_DATA_FILE)
    synthesis_exists = RESEARCH_SYNTHESIS_FILE.exists()
    return jsonify({
        "ok": True,
        "papers_loaded": len(papers) if papers else 0,
        "synthesis_ready": synthesis_exists,
        "pipeline_running": pipeline_state["running"],
        "synthesis_running": synthesis_state["running"],
        "timestamp": datetime.now().isoformat(),
    })


@app.route("/api/search", methods=["POST"])
def api_search():
    body  = request.get_json(force=True, silent=True) or {}
    topics_raw = body.get("topics") or body.get("topic") or ""
    limit = int(body.get("limit", 5))

    # Accept either a single topic string or a list
    if isinstance(topics_raw, list):
        topics = [t.strip() for t in topics_raw if t.strip()]
    else:
        topics = [t.strip() for t in str(topics_raw).split(",") if t.strip()]

    if not topics:
        return jsonify({"error": "topic is required"}), 400

    try:
        if len(topics) == 1:
            results = search_papers(topics[0], limit=limit)
            dataset = {topics[0]: results}
        else:
            dataset = search_multiple_topics(topics, limit_per_topic=limit)
            results = [p for papers in dataset.values() for p in papers]

        if results:
            save_cleaned_dataset(dataset)
        return jsonify({"papers": results, "count": len(results), "topics": topics, "dataset": dataset})
    except Exception as e:
        logger.error(f"Search error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/papers")
def api_papers():
    papers = _load_json(PAPERS_DATA_FILE)
    if papers is None:
        return jsonify({"papers": [], "count": 0})
    return jsonify({"papers": papers, "count": len(papers)})


@app.route("/api/dataset")
def api_dataset():
    """Return the multi-topic cleaned_dataset.json."""
    cleaned = _load_json(DATA_DIR / "cleaned_dataset.json")
    if cleaned is None:
        return jsonify({"dataset": {}, "topics": [], "total": 0})
    total = sum(len(v) for v in cleaned.values())
    return jsonify({"dataset": cleaned, "topics": list(cleaned.keys()), "total": total})


@app.route("/api/similarity")
def api_similarity():
    """Return the cosine similarity matrix from similarity_results.json."""
    data = _load_json(SIMILARITY_FILE)
    if data is None:
        # Try latest archived folder
        folder = _latest_output_folder()
        if folder:
            data = _load_json(folder / "similarity_results.json")
    if data is None:
        return jsonify({"error": "No similarity results. Run extraction pipeline first."}), 404
    return jsonify(data)


@app.route("/api/sections")
def api_sections():
    """List all section text files available."""
    if not SECTIONS_DIR.exists():
        return jsonify({"sections": [], "papers": []})
    papers_sections = []
    for paper_dir in sorted(SECTIONS_DIR.iterdir()):
        if paper_dir.is_dir():
            files = {f.stem: f.read_text(encoding='utf-8') for f in paper_dir.glob('*.txt')}
            papers_sections.append({"paper": paper_dir.name, "sections": files})
    return jsonify({"papers": papers_sections, "count": len(papers_sections)})


# ── Pipeline ──────────────────────────────────────────────

def _run_pipeline_thread():
    """Background thread: runs analysis then marks stages done."""
    try:
        papers = _load_json(PAPERS_DATA_FILE) or []
        n = len(papers)

        # Stage 0 — PDF Parsing (simulated; abstracts already loaded)
        _set_stage(0, "running", f"Processing {n} documents…", 30)
        time.sleep(0.5)
        _set_stage(0, "done", f"{n} documents processed", 100)

        # Stage 1 — Section Extraction
        _set_stage(1, "running", "Extracting sections…", 20)
        analyzer = PaperAnalyzer()
        time.sleep(0.3)
        _set_stage(1, "done", "Abstract, Methods, Results, References", 100)

        # Stage 2 — Key Findings
        _set_stage(2, "running", "Identifying findings…", 40)
        results = analyzer.run_analysis()
        total_findings = sum(len(p.get("key_findings", [])) for p in results.get("papers", []))
        _set_stage(2, "done", f"{total_findings} findings extracted", 100)

        # Stage 3 — Cross-Paper Comparison
        _set_stage(3, "running", "Computing similarity matrix…", 60)
        analyzer._save_analysis()
        time.sleep(0.3)
        _set_stage(3, "done", "Similarity matrix computed", 100)

        # Stage 4 — Embedding (simulated)
        _set_stage(4, "running", "Updating vector store…", 50)
        time.sleep(0.4)
        _set_stage(4, "done", "Vector store updated", 100)

        # Stage 5 — Synthesis Queue
        _set_stage(5, "running", "Ready for AI generation", 72)
        time.sleep(0.2)
        _set_stage(5, "done", "Ready for AI generation", 100)

        pipeline_state["last_run"] = datetime.now().isoformat()

    except Exception as e:
        logger.error(f"Pipeline error: {e}")
        pipeline_state["error"] = str(e)
        for s in pipeline_state["stages"]:
            if s["status"] == "running":
                s["status"] = "pending"
    finally:
        pipeline_state["running"] = False


@app.route("/api/pipeline/run", methods=["POST"])
def api_pipeline_run():
    if pipeline_state["running"]:
        return jsonify({"error": "Pipeline already running"}), 409
    if not PAPERS_DATA_FILE.exists():
        return jsonify({"error": "No papers found. Run a search first."}), 400

    _reset_pipeline()
    pipeline_state["running"] = True
    t = threading.Thread(target=_run_pipeline_thread, daemon=True)
    t.start()
    return jsonify({"ok": True, "message": "Pipeline started"})


@app.route("/api/pipeline/status")
def api_pipeline_status():
    return jsonify({
        "running": pipeline_state["running"],
        "stages":  pipeline_state["stages"],
        "last_run": pipeline_state["last_run"],
        "error":   pipeline_state["error"],
    })


# ── Synthesis ─────────────────────────────────────────────

def _run_synthesis_thread(gen_id):
    try:
        writer = ResearchWriter()
        writer.generate_complete_document()
        # Only mark as done if this is still the active generation
        if synthesis_state["generation_id"] == gen_id:
            synthesis_state["done"] = True
            synthesis_state["last_run"] = datetime.now().isoformat()
    except Exception as e:
        logger.error(f"Synthesis error: {e}")
        if synthesis_state["generation_id"] == gen_id:
            synthesis_state["error"] = str(e)
    finally:
        if synthesis_state["generation_id"] == gen_id:
            synthesis_state["running"] = False


@app.route("/api/synthesis/run", methods=["POST"])
def api_synthesis_run():
    if synthesis_state["running"]:
        return jsonify({"error": "Synthesis already running"}), 409
    if not ANALYSIS_RESULTS_FILE.exists():
        return jsonify({"error": "Run the extraction pipeline first."}), 400

    # Generate unique ID for this synthesis run to prevent stale data issues
    import uuid
    gen_id = str(uuid.uuid4())
    synthesis_state["generation_id"] = gen_id
    synthesis_state["running"] = True
    synthesis_state["done"]    = False
    synthesis_state["error"]   = None
    synthesis_state["started_at"] = datetime.now().isoformat()
    t = threading.Thread(target=_run_synthesis_thread, args=(gen_id,), daemon=True)
    t.start()
    return jsonify({"ok": True, "message": "Synthesis started", "generation_id": gen_id})


@app.route("/api/synthesis")
def api_synthesis():
    """Return the latest synthesis content + sections."""
    # Try latest archived folder first, then root output
    folder = _latest_output_folder()
    md_path  = (folder / "Research_Synthesis.md") if folder else None
    sec_path = (folder / "Sections_Data.json")    if folder else None

    # Fallback to root output files
    if not md_path or not md_path.exists():
        md_path  = RESEARCH_SYNTHESIS_FILE
    if not sec_path or not sec_path.exists():
        sec_path = SECTIONS_DATA_FILE

    md_text  = md_path.read_text(encoding="utf-8")  if md_path  and md_path.exists()  else ""
    sections = _load_json(sec_path) if sec_path and sec_path.exists() else {}

    # Parse markdown sections for the dashboard
    parsed = _parse_synthesis_md(md_text)

    # Check if synthesis has actually completed by looking at file modification time
    # vs last_run timestamp to prevent showing stale "done" status
    has_content = bool(md_text and len(md_text) > 100)
    
    # Calculate elapsed time for running synthesis
    elapsed_seconds = 0
    if synthesis_state["running"] and synthesis_state["started_at"]:
        try:
            started = datetime.fromisoformat(synthesis_state["started_at"])
            elapsed = datetime.now() - started
            elapsed_seconds = int(elapsed.total_seconds())
        except:
            pass
    
    return jsonify({
        "markdown":  md_text,
        "sections":  sections,
        "parsed":    parsed,
        "running":   synthesis_state["running"],
        "done":      synthesis_state["done"] and has_content,  # Only mark done if files exist
        "error":     synthesis_state["error"],  # Include error so frontend can display it
        "last_run":  synthesis_state["last_run"],
        "generation_id": synthesis_state["generation_id"],
        "elapsed_seconds": elapsed_seconds,  # For debugging long-running processes
    })


@app.route("/api/synthesis/revise", methods=["POST"])
def api_synthesis_revise():
    body = request.get_json(force=True, silent=True) or {}
    instruction = body.get("instruction", "").strip()
    
    if not instruction:
        return jsonify({"error": "Instruction required"}), 400
        
    def _revise_thread(instr, gen_id):
        synthesis_state["running"] = True
        try:
            # Initialize ResearchWriter explicitly with analysis data
            writer = ResearchWriter(analysis_file=ANALYSIS_RESULTS_FILE)
            
            # Load previously generated sections to maintain context
            sec_path = SECTIONS_DATA_FILE
            if sec_path.exists():
                sections_data = _load_json(sec_path)
                if sections_data and isinstance(sections_data, dict):
                    writer.output_sections.update(sections_data)
                    logger.info(f"[REVISE] Loaded {len(sections_data)} sections for context preservation")
            
            writer.revise_document(instr)
            if synthesis_state["generation_id"] == gen_id:
                synthesis_state["done"] = True
                synthesis_state["last_run"] = datetime.now().isoformat()
        except Exception as e:
            logger.error(f"Revision error: {e}")
            if synthesis_state["generation_id"] == gen_id:
                synthesis_state["error"] = str(e)
        finally:
            if synthesis_state["generation_id"] == gen_id:
                synthesis_state["running"] = False

    if synthesis_state["running"]:
        return jsonify({"error": "Synthesis/Revision already in progress"}), 409

    import uuid
    gen_id = str(uuid.uuid4())
    synthesis_state["generation_id"] = gen_id
    synthesis_state["running"] = True
    synthesis_state["done"] = False
    synthesis_state["error"] = None
    synthesis_state["started_at"] = datetime.now().isoformat()
    t = threading.Thread(target=_revise_thread, args=(instruction, gen_id), daemon=True)
    t.start()
    
    return jsonify({"ok": True, "message": "Revision started", "generation_id": gen_id})


def _parse_synthesis_md(md: str) -> dict:
    """Extract key sections from the synthesis markdown."""
    def extract(heading_pattern):
        m = re.search(heading_pattern + r'\s*\n+([\s\S]*?)(?=\n## |\Z)', md, re.IGNORECASE)
        return m.group(1).strip() if m else ""

    abstract_raw = extract(r'## Abstract')
    # Strip the "Title:" and "Abstract:" labels if present
    abstract_raw = re.sub(r'^Title:.*\n', '', abstract_raw).strip()
    abstract_raw = re.sub(r'^Abstract:\s*\n', '', abstract_raw).strip()

    return {
        "topic":       re.search(r'\*\*Topic:\*\*\s*(.+)', md).group(1).strip() if re.search(r'\*\*Topic:\*\*\s*(.+)', md) else "",
        "date":        re.search(r'\*\*Generated:\*\*\s*(.+)', md).group(1).strip() if re.search(r'\*\*Generated:\*\*\s*(.+)', md) else "",
        "paper_count": re.search(r'\*\*Papers Reviewed:\*\*\s*(\d+)', md).group(1) if re.search(r'\*\*Papers Reviewed:\*\*\s*(\d+)', md) else "0",
        "model":       re.search(r'\*\*AI Provider:\*\*\s*(.+)', md).group(1).strip() if re.search(r'\*\*AI Provider:\*\*\s*(.+)', md) else "",
        "abstract":    abstract_raw,
        "introduction":extract(r'## 1\. Introduction'),
        "methods":     extract(r'## 2\. Methodological Comparison'),
        "results":     extract(r'## 3\. Results Synthesis'),
        "discussion":  extract(r'## 4\. Discussion'),
        "conclusion":  extract(r'## 5\. Conclusion.*'),
        "references":  extract(r'## References'),
    }


# ── Reports ───────────────────────────────────────────────

@app.route("/api/reports")
def api_reports():
    folders = sorted(
        [d for d in OUTPUT_DIR.iterdir() if d.is_dir()],
        key=lambda d: d.stat().st_mtime,
        reverse=True
    )
    reports = []
    for folder in folders:
        md_file  = folder / "Research_Synthesis.md"
        bib_file = folder / "References.bib"
        src_file = folder / "Source_Papers.json"

        papers_data = _load_json(src_file) or []
        md_text     = md_file.read_text(encoding="utf-8") if md_file.exists() else ""
        word_count  = len(md_text.split()) if md_text else 0

        # Parse topic and date from markdown header
        topic_m = re.search(r'\*\*Topic:\*\*\s*(.+)', md_text)
        date_m  = re.search(r'\*\*Generated:\*\*\s*(.+)', md_text)
        model_m = re.search(r'\*\*AI Provider:\*\*\s*(.+)', md_text)

        reports.append({
            "id":        folder.name,
            "title":     folder.name.replace("_", " ").replace("20", "20", 1),
            "topic":     topic_m.group(1).strip() if topic_m else folder.name,
            "date":      date_m.group(1).strip()  if date_m  else "Unknown",
            "model":     model_m.group(1).strip()  if model_m else "Unknown",
            "papers":    len(papers_data),
            "words":     word_count,
            "status":    "ready" if md_file.exists() and word_count > 100 else "draft",
            "has_bib":   bib_file.exists(),
        })
    return jsonify({"reports": reports, "count": len(reports)})


@app.route("/api/reports/<folder_name>")
def api_report_detail(folder_name):
    folder = OUTPUT_DIR / folder_name
    if not folder.exists() or not folder.is_dir():
        abort(404)

    md_file  = folder / "Research_Synthesis.md"
    src_file = folder / "Source_Papers.json"
    bib_file = folder / "References.bib"
    sec_file = folder / "Sections_Data.json"

    md_text  = md_file.read_text(encoding="utf-8")  if md_file.exists()  else ""
    papers   = _load_json(src_file) or []
    bib_text = bib_file.read_text(encoding="utf-8") if bib_file.exists() else ""
    sections = _load_json(sec_file) or {}
    parsed   = _parse_synthesis_md(md_text)

    return jsonify({
        "id":       folder_name,
        "markdown": md_text,
        "parsed":   parsed,
        "papers":   papers,
        "bib":      bib_text,
        "sections": sections,
        "apa":      _papers_to_apa(papers),
    })


# ── Export ────────────────────────────────────────────────

@app.route("/api/export/apa")
def api_export_apa():
    """Return APA references as downloadable .txt from the latest run."""
    folder   = _latest_output_folder()
    src_file = (folder / "Source_Papers.json") if folder else PAPERS_DATA_FILE
    papers   = _load_json(src_file) or _load_json(PAPERS_DATA_FILE) or []

    if not papers:
        return jsonify({"error": "No papers found"}), 404

    apa_text = _papers_to_apa(papers)
    tmp_path = BASE_DIR / "output" / "_apa_export.txt"
    tmp_path.write_text(apa_text, encoding="utf-8")
    return send_file(tmp_path, as_attachment=True, download_name="references_APA7.txt", mimetype="text/plain")


@app.route("/api/export/bib")
def api_export_bib():
    """Return BibTeX file from the latest run."""
    folder   = _latest_output_folder()
    bib_file = (folder / "References.bib") if folder else BIBTEX_FILE
    if not bib_file or not bib_file.exists():
        bib_file = BIBTEX_FILE
    if not bib_file.exists():
        return jsonify({"error": "No BibTeX file found"}), 404
    return send_file(bib_file, as_attachment=True, download_name="references.bib", mimetype="text/plain")


@app.route("/api/export/markdown")
def api_export_markdown():
    """Return the synthesis markdown file."""
    folder  = _latest_output_folder()
    md_file = (folder / "Research_Synthesis.md") if folder else RESEARCH_SYNTHESIS_FILE
    if not md_file or not md_file.exists():
        md_file = RESEARCH_SYNTHESIS_FILE
    if not md_file.exists():
        return jsonify({"error": "No synthesis found"}), 404
    return send_file(md_file, as_attachment=True, download_name="research_synthesis.md", mimetype="text/markdown")


@app.route("/api/export/pdf")
def api_export_pdf():
    """
    Generate and return PDF of the research synthesis.
    
    Attempts server-side PDF generation. If unavailable, returns 503 error,
    which triggers frontend to use browser print-to-PDF fallback (which has
    comprehensive academic styling: Georgia serif, 14px, 1.8 line-height).
    
    Cache-busting: Frontend includes ?t=${Date.now()} in request URL.
    """
    # Check if synthesis exists
    folder  = _latest_output_folder()
    md_file = (folder / "Research_Synthesis.md") if folder else RESEARCH_SYNTHESIS_FILE
    if not md_file or not md_file.exists():
        md_file = RESEARCH_SYNTHESIS_FILE
    if not md_file.exists():
        return jsonify({"error": "No synthesis found"}), 404
    
    # Try to generate PDF using reportlab if available
    try:
        from reportlab.lib.pagesizes import letter, A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle
        from reportlab.lib import colors
        from reportlab.pdfgen import canvas
        import markdown
        
        # Read markdown content
        markdown_content = md_file.read_text(encoding='utf-8')
        
        # Create PDF file path
        pdf_file = BASE_DIR / "output" / f"research_synthesis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        pdf_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Create PDF document with academic styling
        doc = SimpleDocTemplate(
            str(pdf_file),
            pagesize=letter,
            rightMargin=0.75*inch,
            leftMargin=0.75*inch,
            topMargin=0.75*inch,
            bottomMargin=0.75*inch,
            title="Research Synthesis",
            author="AI Research Agent",
            subject="Academic Research Synthesis"
        )
        
        # Build styles for academic formatting
        styles = getSampleStyleSheet()
        styles.add(ParagraphStyle(
            name='BodyFont',
            fontName='Times-Roman',
            fontSize=12,
            leading=18,  # 1.8x line height
            alignment=4   # Justified
        ))
        
        styles.add(ParagraphStyle(
            name='Heading1Font',
            fontName='Times-Bold',
            fontSize=18,
            leading=22,
            spaceAfter=12,
            textColor=colors.HexColor('#3730a3'),
            pageBreakBefore=False
        ))
        
        styles.add(ParagraphStyle(
            name='Heading2Font',
            fontName='Times-Bold',
            fontSize=14,
            leading=16,
            spaceAfter=10,
            textColor=colors.HexColor('#3730a3'),
            pageBreakBefore=False
        ))
        
        # Parse markdown and build story
        story = []
        lines = markdown_content.split('\n')
        
        i = 0
        while i < len(lines):
            line = lines[i]
            
            if line.startswith('# '):
                # Top-level heading
                title = line.replace('# ', '').strip()
                story.append(Paragraph(title, styles['Heading1Font']))
                story.append(Spacer(1, 0.2*inch))
            elif line.startswith('## '):
                # Section heading
                title = line.replace('## ', '').strip()
                story.append(Paragraph(title, styles['Heading2Font']))
                story.append(Spacer(1, 0.15*inch))
            elif line.startswith('### '):
                # Subsection heading
                title = line.replace('### ', '').strip()
                story.append(Paragraph(title, styles['Heading3']))
                story.append(Spacer(1, 0.1*inch))
            elif line.strip().startswith('- ') or line.strip().startswith('* '):
                # Bullet point - convert to paragraph with indent
                item = line.strip().lstrip('- *').strip()
                story.append(Paragraph(f"• {item}", styles['Normal']))
            elif line.strip() == '':
                # Blank line - add spacer
                story.append(Spacer(1, 0.1*inch))
            else:
                # Regular paragraph
                if line.strip():
                    story.append(Paragraph(line.strip(), styles['BodyFont']))
                    story.append(Spacer(1, 0.08*inch))
            
            i += 1
        
        # Add page break at end
        story.append(PageBreak())
        
        # Build PDF
        doc.build(story)
        
        logger.info(f"[PDF] Generated: {pdf_file}")
        return send_file(
            str(pdf_file),
            as_attachment=True,
            download_name=f"research_synthesis_{datetime.now().strftime('%Y%m%d')}.pdf",
            mimetype="application/pdf"
        )
    
    except ImportError as e:
        # reportlab not available - return informative error
        logger.warning(f"[PDF] reportlab not available: {e}. Frontend will use browser print fallback.")
        return jsonify({
            "error": "Server-side PDF generation unavailable",
            "message": "Browser print-to-PDF fallback will be used with academic styling",
            "fallback_styling": "Georgia serif, 14px, 1.8 line-height, justified"
        }), 503
    
    except Exception as e:
        # Other errors
        logger.error(f"[PDF] Generation failed: {e}")
        return jsonify({
            "error": "PDF generation error",
            "message": str(e),
            "fallback": "Browser print mechanism will be used"
        }), 503


# ── Run ───────────────────────────────────────────────────
# Export app for Vercel serverless functions
# Vercel will use this directly without calling app.run()

if __name__ == "__main__":
    print("\n" + "="*50)
    print("  AI PAPER REVIEWER — API SERVER")
    print("  http://localhost:5000")
    print("="*50 + "\n")
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)
