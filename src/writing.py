"""
Writing Phase Module - Milestone 3
Generates structured academic sections: Abstract, Introduction, Methods Comparison,
Results Synthesis, Discussion, Conclusion, and APA References.
"""

import json
import re
import concurrent.futures
from datetime import datetime
from typing import List, Dict, Any

# Local Imports
from src.config import (
    ANALYSIS_RESULTS_FILE,
    RESEARCH_SYNTHESIS_FILE,
    SECTIONS_DATA_FILE,
    BIBTEX_FILE,
    ABSTRACT_WORD_LIMIT,
    OUTPUT_DIR
)
from src.utils import setup_logger

logger = setup_logger(__name__)

SYSTEM_PROMPT = (
    "You are an expert academic researcher and scientific writer. "
    "Write in formal, precise academic English. Use clear paragraph structure. "
    "Do not use bullet points unless explicitly asked. Do not repeat the section heading."
)


class ResearchWriter:
    """Generates a complete, structured research synthesis document."""

    def __init__(self, analysis_file: str = None):
        # Delayed import
        from src.ai_engine import AIEngine
        self.ai = AIEngine()
        self.analysis_file = analysis_file if analysis_file else ANALYSIS_RESULTS_FILE
        self.analysis_data = self._load_analysis()
        self.output_sections = {
            "abstract": "",
            "introduction": "",
            "methods_comparison": "",
            "results_synthesis": "",
            "discussion": "",
            "conclusion": "",
            "future_implications": "",
            "references": "",
            "bibtex": "",
            "synthesis_report": ""
        }

        self.ai = AIEngine() if AIEngine else None
        if self.ai:
            print(f"   [INFO] AI Provider: {self.ai.provider}")
        else:
            print("   [INFO] Using: Template fallback (no AI provider)")

    # ─────────────────────────────────────────────
    # Data Loading
    # ─────────────────────────────────────────────

    def _load_analysis(self) -> Dict[str, Any]:
        try:
            with open(self.analysis_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            logger.info(f"Loaded analysis for {data['metadata']['total_papers']} papers")
            return data
        except FileNotFoundError:
            logger.error(f"Analysis file not found: {self.analysis_file}")
            return {"metadata": {}, "papers": [], "cross_paper_analysis": {}, "key_themes": []}
        except json.JSONDecodeError:
            logger.error("Invalid JSON in analysis file")
            return {"metadata": {}, "papers": [], "cross_paper_analysis": {}, "key_themes": []}

    # ─────────────────────────────────────────────
    # Helper: Build rich paper context for prompts
    # ─────────────────────────────────────────────

    def _build_paper_context(self, papers: List[Dict]) -> str:
        parts = []
        for i, p in enumerate(papers, 1):
            sections = p.get("sections", {})
            findings = p.get("key_findings", [])
            methods = p.get("methodology", {}).get("approaches", [])
            part = (
                f"Paper {i}: {p['title']} ({p.get('year', 'n.d.')})\n"
                f"  Authors: {', '.join(p.get('authors', ['Unknown'])[:3])}\n"
                f"  Objective: {sections.get('objective', 'N/A')}\n"
                f"  Methods: {'; '.join(methods[:2]) if methods else sections.get('methods', 'N/A')}\n"
                f"  Results: {sections.get('results', 'N/A')}\n"
                f"  Key Findings: {'; '.join(findings[:2]) if findings else 'N/A'}\n"
                f"  Conclusion: {sections.get('conclusion', 'N/A')}\n"
                f"  Citations: {p.get('citations', 0)}"
            )
            parts.append(part)
        return "\n\n".join(parts)

    def _ai_or_fallback(self, prompt: str, fallback: str, max_tokens: int = 1024) -> str:
        """Call AI with prompt; return fallback string if AI unavailable or fails."""
        if self.ai and self.ai.provider != "None":
            try:
                result = self.ai.generate(prompt, system_prompt=SYSTEM_PROMPT, max_tokens=max_tokens)
                if result.get("status") == "success" and result.get("text"):
                    return result["text"]
            except BaseException as e:
                logger.warning(f"AI generation failed ({type(e).__name__}): {str(e)[:100]}, using fallback")
        return fallback

    # ─────────────────────────────────────────────
    # Section Generators
    # ─────────────────────────────────────────────

    def generate_abstract(self) -> str:
        """Generate a structured academic abstract (≤150 words)."""
        logger.info("📝 Generating Abstract...")
        papers = self.analysis_data.get("papers", [])
        themes = self.analysis_data.get("key_themes", [])

        context = self._build_paper_context(papers)
        prompt = (
            f"Write a concise academic abstract (maximum 150 words) for a research synthesis "
            f"that reviews the following {len(papers)} papers on the topic of {', '.join(themes[:3])}.\n\n"
            f"The abstract must cover: (1) purpose of the review, (2) scope and methodology of the synthesis, "
            f"(3) key findings across papers, (4) conclusions and implications.\n\n"
            f"PAPERS:\n{context}"
        )
        fallback = (
            f"This systematic review synthesizes {len(papers)} research papers examining "
            f"{', '.join(themes[:3])}. The review identifies key methodological approaches, "
            f"consolidates empirical findings, and highlights emerging trends. "
            f"Results indicate significant advances in the field with implications for future research directions."
        )
        result = self._ai_or_fallback(prompt, fallback, max_tokens=300)
        self.output_sections["abstract"] = result
        return result

    def generate_introduction(self) -> str:
        """Generate a full introduction section with research context and objectives."""
        logger.info("📝 Generating Introduction...")
        papers = self.analysis_data.get("papers", [])
        themes = self.analysis_data.get("key_themes", [])
        cross = self.analysis_data.get("cross_paper_analysis", {})
        years = list(cross.get("year_distribution", {}).keys())
        year_range = f"{min(years)}–{max(years)}" if years else "recent years"

        paper_list = "\n".join([f"- {p['title']} ({p.get('year','n.d.')})" for p in papers])
        prompt = (
            f"Write a formal Introduction section (3–4 paragraphs) for a research synthesis paper.\n\n"
            f"Topic: {', '.join(themes[:5])}\n"
            f"Time span: {year_range}\n"
            f"Papers reviewed:\n{paper_list}\n\n"
            f"The introduction should: (1) establish the research domain and its importance, "
            f"(2) identify the research gap or motivation for this review, "
            f"(3) state the objectives of the synthesis, "
            f"(4) outline the structure of the paper."
        )
        fallback = (
            f"The rapid advancement of {', '.join(themes[:2])} has generated a substantial body of "
            f"literature spanning {year_range}. This synthesis reviews {len(papers)} seminal works "
            f"to consolidate current knowledge, identify methodological trends, and highlight gaps "
            f"that warrant further investigation. The papers reviewed collectively address {', '.join(themes[:4])}, "
            f"providing a comprehensive foundation for understanding the state of the field."
        )
        result = self._ai_or_fallback(prompt, fallback, max_tokens=800)
        self.output_sections["introduction"] = result
        return result

    def generate_methods_comparison(self) -> str:
        """Generate a detailed methodological comparison across all papers."""
        logger.info("📝 Generating Methods Comparison...")
        papers = self.analysis_data.get("papers", [])

        context = self._build_paper_context(papers)
        prompt = (
            f"Write a detailed Methodological Comparison section (3–5 paragraphs) for a research synthesis.\n\n"
            f"Compare and contrast the research methodologies used across the following papers. "
            f"Discuss: (1) the types of methods used (experimental, theoretical, empirical, etc.), "
            f"(2) commonalities and shared approaches, (3) key differences and unique contributions, "
            f"(4) strengths and limitations of each approach.\n\n"
            f"PAPERS:\n{context}"
        )
        # Fallback: structured table-style
        parts = ["The reviewed papers employ a range of methodological approaches, reflecting the diversity of the field.\n"]
        for i, p in enumerate(papers, 1):
            methods = p.get("methodology", {}).get("approaches", [])
            method_str = "; ".join(methods[:2]) if methods else "General analytical approach"
            parts.append(f"**Paper {i} — {p['title']}:** {method_str}")
        fallback = "\n\n".join(parts)

        result = self._ai_or_fallback(prompt, fallback, max_tokens=1200)
        self.output_sections["methods_comparison"] = result
        return result

    def generate_results_synthesis(self) -> str:
        """Synthesize and integrate results from all papers."""
        logger.info("📝 Generating Results Synthesis...")
        papers = self.analysis_data.get("papers", [])
        themes = self.analysis_data.get("key_themes", [])

        context = self._build_paper_context(papers)
        prompt = (
            f"Write a comprehensive Results Synthesis section (4–6 paragraphs) for a research synthesis paper.\n\n"
            f"Synthesize the findings from the following papers on {', '.join(themes[:3])}. "
            f"The section should: (1) present aggregate findings across papers, "
            f"(2) compare quantitative and qualitative results where available, "
            f"(3) identify convergent findings (where papers agree), "
            f"(4) highlight divergent findings (where papers disagree or differ), "
            f"(5) discuss the significance of the combined results.\n\n"
            f"PAPERS:\n{context}"
        )
        parts = [f"The synthesis of findings across {len(papers)} papers reveals several important patterns.\n"]
        for i, p in enumerate(papers, 1):
            findings = p.get("key_findings", ["No specific findings identified."])
            parts.append(f"**{p['title']} ({p.get('year','n.d.')}):** {findings[0]}")
        fallback = "\n\n".join(parts)

        result = self._ai_or_fallback(prompt, fallback, max_tokens=1500)
        self.output_sections["results_synthesis"] = result
        return result

    def generate_discussion(self) -> str:
        """Generate a critical discussion interpreting the synthesized findings."""
        logger.info("📝 Generating Discussion...")
        papers = self.analysis_data.get("papers", [])
        themes = self.analysis_data.get("key_themes", [])
        cross = self.analysis_data.get("cross_paper_analysis", {})
        trends = cross.get("research_trends", [])

        prompt = (
            f"Write a Discussion section (3–4 paragraphs) for a research synthesis paper on {', '.join(themes[:3])}.\n\n"
            f"The discussion should: (1) interpret the synthesized results in the broader context of the field, "
            f"(2) explain what the aggregate findings mean for theory and practice, "
            f"(3) discuss limitations of the reviewed studies and the synthesis itself, "
            f"(4) compare findings with prior reviews or established knowledge.\n\n"
            f"Research trends identified: {', '.join(trends)}\n"
            f"Number of papers reviewed: {len(papers)}"
        )
        fallback = (
            f"The findings synthesized from {len(papers)} papers provide important insights into "
            f"{', '.join(themes[:2])}. The convergence of methodological approaches suggests a maturing field, "
            f"while divergent results highlight areas requiring further empirical investigation. "
            f"The identified trends — {', '.join(trends[:2])} — align with broader developments in the discipline. "
            f"Limitations include the reliance on abstract-level data and the restricted number of papers reviewed."
        )
        result = self._ai_or_fallback(prompt, fallback, max_tokens=1000)
        self.output_sections["discussion"] = result
        return result

    def generate_conclusion(self) -> str:
        """Generate a conclusion with future research directions."""
        logger.info("📝 Generating Conclusion & Future Implications...")
        themes = self.analysis_data.get("key_themes", [])
        papers = self.analysis_data.get("papers", [])

        prompt = (
            f"Write a Conclusion section (2–3 paragraphs) for a research synthesis on {', '.join(themes[:3])}.\n\n"
            f"The conclusion should: (1) summarize the key takeaways from the synthesis, "
            f"(2) restate the significance of the reviewed work, "
            f"(3) propose specific future research directions and open questions, "
            f"(4) end with a forward-looking statement about the field.\n\n"
            f"Number of papers reviewed: {len(papers)}"
        )
        fallback = (
            f"This synthesis of {len(papers)} papers on {', '.join(themes[:2])} demonstrates the "
            f"significant progress made in the field. Key contributions include advances in "
            f"{', '.join(themes[:3])}. Future research should focus on addressing identified gaps, "
            f"expanding empirical validation, and exploring interdisciplinary applications. "
            f"The field is poised for continued growth as new methodologies and datasets emerge."
        )
        result = self._ai_or_fallback(prompt, fallback, max_tokens=800)
        self.output_sections["conclusion"] = result
        self.output_sections["future_implications"] = result  # alias
        return result

    # ─────────────────────────────────────────────
    # References (APA Style)
    # ─────────────────────────────────────────────

    def generate_references(self) -> str:
        """Generate APA 7th edition formatted references, sorted alphabetically."""
        logger.info("📝 Generating APA References...")
        papers = self.analysis_data.get("papers", [])
        if not papers:
            return ""

        sorted_papers = sorted(
            papers,
            key=lambda p: (p.get("authors") or ["Unknown"])[0].split()[-1].lower()
        )

        refs = []
        for paper in sorted_papers:
            authors = paper.get("authors", [])
            year = paper.get("year", "n.d.")
            title = paper.get("title", "Untitled")
            venue = paper.get("venue", "")
            url = paper.get("url", "")

            # Format: Last, F. I., & Last, F. I.
            formatted = []
            for author in authors:
                parts = author.strip().split()
                if len(parts) >= 2:
                    last = parts[-1]
                    initials = ". ".join(p[0] for p in parts[:-1]) + "."
                    formatted.append(f"{last}, {initials}")
                elif parts:
                    formatted.append(parts[0])

            if not formatted:
                author_str = "Unknown Author"
            elif len(formatted) == 1:
                author_str = formatted[0]
            elif len(formatted) <= 20:
                author_str = ", ".join(formatted[:-1]) + ", & " + formatted[-1]
            else:
                author_str = ", ".join(formatted[:19]) + ", ... " + formatted[-1]

            # Remove trailing period before we add our own
            author_str = author_str.rstrip(".")

            ref = f"{author_str}. ({year}). {title}."
            if venue:
                ref += f" *{venue}*."
            if url:
                ref += f" {url}"

            refs.append(ref)

        ref_text = "\n\n".join(refs)
        self.output_sections["references"] = ref_text
        return ref_text

    # ─────────────────────────────────────────────
    # BibTeX
    # ─────────────────────────────────────────────

    def generate_bibtex(self) -> str:
        """Generate BibTeX entries for all papers."""
        logger.info("📝 Generating BibTeX...")
        papers = self.analysis_data.get("papers", [])
        entries = []

        used_keys = set()
        for paper in papers:
            title = paper.get("title", "Untitled").replace("&", "\\&")
            year = str(paper.get("year", "nd"))
            authors_raw = paper.get("authors", ["Unknown"])
            authors_bib = " and ".join(authors_raw)
            venue = paper.get("venue", "").replace("&", "\\&")
            url = paper.get("url", "")

            # Unique cite key
            first_last = (authors_raw[0].split()[-1].lower() if authors_raw else "unknown")
            first_last = re.sub(r'[^a-z0-9]', '', first_last)
            base_key = f"{first_last}{year}"
            key = base_key
            suffix = 1
            while key in used_keys:
                key = f"{base_key}{chr(96 + suffix)}"
                suffix += 1
            used_keys.add(key)

            entry = f"@article{{{key},\n"
            entry += f"  author  = {{{authors_bib}}},\n"
            entry += f"  title   = {{{title}}},\n"
            entry += f"  journal = {{{venue}}},\n"
            entry += f"  year    = {{{year}}}"
            if url:
                entry += f",\n  url     = {{{url}}}"
            entry += "\n}"
            entries.append(entry)

        bibtex = "\n\n".join(entries)
        self.output_sections["bibtex"] = bibtex
        return bibtex

    # ─────────────────────────────────────────────
    # Main Document Assembly
    # ─────────────────────────────────────────────

    def generate_complete_document(self) -> str:
        """Run all section generators and assemble the full research document."""
        print(f"\n{'='*60}")
        print("  WRITING PHASE — MILESTONE 3 (Structured Academic Synthesis)")
        print(f"{'='*60}\n")

        papers = self.analysis_data.get("papers", [])
        if not papers:
            logger.warning("No papers to write about.")
            return ""

        themes = self.analysis_data.get("key_themes", [])
        topic_str = ", ".join(themes[:3]) if themes else "Research Topic"
        date_str = datetime.now().strftime("%B %d, %Y")

        # Generate all sections in parallel (2-3x faster)
        print("[WRITING] Generating sections in parallel...")
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            abstract_future = executor.submit(self.generate_abstract)
            introduction_future = executor.submit(self.generate_introduction)
            methods_future = executor.submit(self.generate_methods_comparison)
            results_future = executor.submit(self.generate_results_synthesis)
            discussion_future = executor.submit(self.generate_discussion)
            conclusion_future = executor.submit(self.generate_conclusion)
            references_future = executor.submit(self.generate_references)
            bibtex_future = executor.submit(self.generate_bibtex)
            
            # Collect results as completed
            abstract = abstract_future.result()
            introduction = introduction_future.result()
            methods = methods_future.result()
            results = results_future.result()
            discussion = discussion_future.result()
            conclusion = conclusion_future.result()
            references = references_future.result()
            bibtex = bibtex_future.result()

        # Assemble full document
        doc_parts = [
            f"# AI-Generated Research Synthesis Report",
            f"**Topic:** {topic_str.title()}  ",
            f"**Generated:** {date_str}  ",
            f"**Papers Reviewed:** {len(papers)}  ",
            f"**AI Provider:** {self.ai.provider if self.ai else 'Template Fallback'}",
            "---",

            "## Abstract",
            abstract,
            "---",

            "## 1. Introduction",
            introduction,

            "## 2. Methodological Comparison",
            methods,

            "## 3. Results Synthesis",
            results,

            "## 4. Discussion",
            discussion,

            "## 5. Conclusion & Future Implications",
            conclusion,
            "---",

            "## References",
            references,
        ]

        full_doc = "\n\n".join(doc_parts)

        # Store synthesis_report alias for pipeline compatibility
        self.output_sections["synthesis_report"] = full_doc

        self._save_document(full_doc, bibtex)

        print(f"\n{'='*60}")
        print("  ✅ WRITING PHASE COMPLETED SUCCESSFULLY")
        print(f"  Provider: {self.ai.provider if self.ai else 'Template'}")
        print(f"  Sections: Abstract, Introduction, Methods, Results, Discussion, Conclusion, References")
        print(f"{'='*60}\n")

        return full_doc

    # ─────────────────────────────────────────────
    # Revision
    # ─────────────────────────────────────────────

    def revise_document(self, instruction: str) -> str:
        """Revise the existing synthesis report based on user feedback."""
        print(f"\n{'='*60}")
        print("  REVISION PHASE")
        print(f"  Instruction: {instruction}")
        print(f"{'='*60}\n")

        # Load existing
        if not RESEARCH_SYNTHESIS_FILE.exists():
            return "Error: No synthesis found to revise."
        
        current_doc = RESEARCH_SYNTHESIS_FILE.read_text(encoding='utf-8')
        
        if not self.ai or self.ai.provider == "None":
            return "Error: No AI provider available for revision."

        prompt = (
            f"You are a meticulous academic editor. Revise the following research report according to the user's request.\n"
            f"USER INSTRUCTION: \"{instruction}\"\n\n"
            f"IMPORTANT REVISION RULES:\n"
            f"1. Follow the user's instruction EXACTLY and COMPLETELY.\n"
            f"2. If asked to increase word count - expand each section with more detail, examples, and analysis.\n"
            f"3. If asked to add bullet points - convert relevant paragraphs to structured bullet lists using - or *.\n"
            f"4. If asked to add headings - insert new ## or ### Markdown headings to organize content.\n"
            f"5. If asked to add styling - use **bold**, *italic*, blockquotes as appropriate.\n"
            f"6. If asked to add tables - create Markdown tables with | syntax.\n"
            f"7. Maintain formal academic English throughout.\n"
            f"8. Do NOT invent new papers or citations not already in the document.\n"
            f"9. Preserve the overall Markdown structure (## headings, --- dividers).\n"
            f"10. Return ONLY the full revised markdown document - no preamble, no explanation.\n\n"
            f"CURRENT DOCUMENT:\n{current_doc}"
        )

        result = self.ai.generate(prompt, max_tokens=2500)
        
        if result.get("status") == "success" and result.get("text"):
            revised_doc = result["text"]
            # Clean up potential markdown fences
            revised_doc = revised_doc.replace("```markdown", "").replace("```", "").strip()
            
            # Save the revision
            self._save_document(revised_doc, self.output_sections.get("bibtex", ""))
            return revised_doc
        
        return f"Error: Revision failed. {result.get('error', 'Unknown error')}"

    # ─────────────────────────────────────────────
    # Save Outputs
    # ─────────────────────────────────────────────

    def _save_document(self, document: str, bibtex: str):
        """Save Markdown report, JSON sections, and BibTeX file."""
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

        # Markdown report
        with open(RESEARCH_SYNTHESIS_FILE, 'w', encoding='utf-8') as f:
            f.write(document)
        logger.info(f"✅ Report saved: {RESEARCH_SYNTHESIS_FILE}")

        # JSON sections
        with open(SECTIONS_DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.output_sections, f, indent=2, ensure_ascii=False)
        logger.info(f"✅ Sections JSON saved: {SECTIONS_DATA_FILE}")

        # BibTeX
        with open(BIBTEX_FILE, 'w', encoding='utf-8') as f:
            f.write(bibtex)
        logger.info(f"✅ BibTeX saved: {BIBTEX_FILE}")


def main():
    writer = ResearchWriter()
    writer.generate_complete_document()


if __name__ == "__main__":
    main()


# ═══════════════════════════════════════════════════════════
# REFERENCE-COMPATIBLE STANDALONE FUNCTIONS
# (ported from ai_research_agent-riya-dasgupta reference project)
# ═══════════════════════════════════════════════════════════

def extract_common_patterns(cleaned_dataset: list) -> dict:
    """
    Extract common datasets, methods, and algorithms across all papers
    by scanning their abstracts for known keywords.

    Args:
        cleaned_dataset: list of paper dicts (each with an 'abstract' field)

    Returns:
        dict with keys: common_datasets, common_methods, common_algorithms
    """
    datasets   = set()
    methods    = set()
    algorithms = set()

    for paper in cleaned_dataset:
        text = (paper.get("abstract") or "").lower()

        if "dataset" in text:
            datasets.add("public benchmark datasets")

        if "method" in text or "approach" in text:
            methods.add("machine learning based approach")

        if "cnn" in text:
            algorithms.add("Convolutional Neural Network (CNN)")
        if "svm" in text:
            algorithms.add("Support Vector Machine (SVM)")
        if "lstm" in text:
            algorithms.add("Long Short-Term Memory (LSTM)")
        if "transformer" in text:
            algorithms.add("Transformer / Attention Mechanism")
        if "random forest" in text:
            algorithms.add("Random Forest")
        if "bert" in text:
            algorithms.add("BERT / Pre-trained Language Model")

    return {
        "common_datasets":   list(datasets),
        "common_methods":    list(methods),
        "common_algorithms": list(algorithms),
    }


def build_gpt_prompt(patterns: dict, key_findings: dict) -> str:
    """
    Build a structured academic-writing prompt from extracted patterns
    and key findings.  Compatible with the reference project's
    milestone_3/prompt_builder.py.

    Args:
        patterns:     output of extract_common_patterns()
        key_findings: dict mapping paper name → list of finding sentences

    Returns:
        Formatted prompt string ready to send to any LLM.
    """
    return f"""
You are an academic research assistant.

Using the information below:
- Common datasets
- Common methods
- Common algorithms
- Extracted key findings

Write a structured research paper draft with the following sections:
1. Abstract
2. Methods
3. Results

Rules:
- Use formal academic tone
- No assumptions beyond given data
- Write references in APA style
- Avoid plagiarism
- Clearly synthesize findings across papers

Common Patterns:
{patterns}

Key Findings:
{key_findings}
"""


def generate_draft(patterns: dict, key_findings: dict) -> str:
    """
    Generate an academic draft from extracted patterns and key findings.
    Uses the AI engine to create a structured paper outline.
    Compatible with the reference project's milestone_3/draft_generator.py.

    Args:
        patterns:     output of extract_common_patterns()
        key_findings: dict mapping paper name → list of finding sentences

    Returns:
        Generated draft text as a string, or an error message on failure.
    """
    try:
        ai = AIEngine()
    except Exception as e:
        logger.warning(f"AI engine initialization failed: {e}")
        return f"Error: Could not initialize AI engine for draft generation. {str(e)}"

    if not ai or not ai.is_ready():
        return "Error: No AI provider available for draft generation."

    prompt = build_gpt_prompt(patterns, key_findings)
    result = ai.generate(prompt)

    if result.get("status") == "success":
        return result.get("text", "Draft generation returned empty text.")
    else:
        error_msg = result.get("error", "Unknown error")
        return f"Draft generation failed: {error_msg}"


def evaluate_quality(draft_text: str) -> dict:
    """
    Compute a simple quality score for a generated draft.
    Scores the presence of key sections and sufficient word count.
    Compatible with the reference project's milestone_4/quality_evaluator.py.

    Args:
        draft_text: raw string of the generated or revised paper draft

    Returns:
        dict with word_count, quality_score_out_of_100, remarks
    """
    word_count = len(draft_text.split())

    score = 0
    if "abstract" in draft_text.lower():
        score += 20
    if "methods" in draft_text.lower() or "methodology" in draft_text.lower():
        score += 20
    if "results" in draft_text.lower():
        score += 20
    if word_count > 250:
        score += 20
    if word_count > 400:
        score += 20

    return {
        "word_count":              word_count,
        "quality_score_out_of_100": score,
        "remarks": "Higher score indicates better structure and completeness.",
    }


def generate_critique(draft_text: str) -> str:
    """
    Use the AI engine to produce a structured academic critique of the draft.
    Compatible with the reference project's milestone_4/critique_generator.py.

    Args:
        draft_text: the current draft as a string

    Returns:
        Critique string with bullet-point suggestions, or an error message.
    """
    try:
        ai = AIEngine()
    except Exception:
        return "Error: AI engine unavailable for critique generation."

    if not ai or not ai.is_ready():
        return "Error: No AI provider available for critique generation."

    prompt = f"""
You are an expert academic mentor.

Critically review the following draft and provide improvement suggestions.

Your critique must cover:
1. Academic tone
2. Missing details
3. Logical flow
4. Repetition removal
5. APA style improvements

Return output in bullet points.

Draft:
{draft_text}
"""
    result = ai.generate(prompt)
    return result.get("text", "Critique generation failed.")


def split_sections(draft_text: str) -> dict:
    """
    Split a draft string into Abstract, Methods, and Results sections
    using heading-keyword heuristics.  Works even when headings are
    missing or inconsistent.
    Compatible with the reference project's milestone_4/reviewer.py.

    Args:
        draft_text: raw string of the draft

    Returns:
        dict with keys Abstract, Methods, Results (each a str)
    """
    sections: dict = {"Abstract": "", "Methods": "", "Results": ""}
    current = None

    for line in draft_text.split("\n"):
        clean = line.strip().lower()

        if "abstract" in clean:
            current = "Abstract"
            continue
        elif "methods" in clean or "methodology" in clean:
            current = "Methods"
            continue
        elif "results" in clean:
            current = "Results"
            continue

        if current:
            sections[current] += line + "\n"

    return sections


def review_draft(draft_text: str) -> dict:
    """
    Create a structured review object: split sections, measure word count,
    and flag whether each key section has substantive content.
    Compatible with the reference project's milestone_4/reviewer.py.

    Args:
        draft_text: raw string of the draft

    Returns:
        dict with keys: sections, word_count, has_abstract, has_methods, has_results
    """
    sections = split_sections(draft_text)

    return {
        "sections":    sections,
        "word_count":  len(draft_text.split()),
        "has_abstract": len(sections["Abstract"].strip()) > 50,
        "has_methods":  len(sections["Methods"].strip()) > 50,
        "has_results":  len(sections["Results"].strip()) > 50,
    }


def generate_final_report(
    topic: str,
    patterns: dict,
    key_findings: dict,
    draft_text: str,
    refined_text: str,
    quality_report: dict,
    output_path: str = "data/datasets/final_report.json",
) -> str:
    """
    Bundle all pipeline artefacts into a single JSON final report and
    save it to disk.
    Compatible with the reference project's milestone_4/final_report_generator.py.

    Args:
        topic:          research topic string
        patterns:       output of extract_common_patterns()
        key_findings:   dict from analysis phase
        draft_text:     initial AI-generated draft
        refined_text:   human-revised / refined version
        quality_report: output of evaluate_quality()
        output_path:    destination JSON path (default: data/datasets/final_report.json)

    Returns:
        The output_path where the report was saved.
    """
    import os as _os
    from datetime import datetime as _datetime

    report = {
        "topic":           topic,
        "generated_at":    _datetime.now().isoformat(),
        "common_patterns": patterns,
        "key_findings":    key_findings,
        "initial_draft":   draft_text,
        "refined_draft":   refined_text,
        "quality_report":  quality_report,
    }

    _os.makedirs(_os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=4, ensure_ascii=False)

    logger.info(f"Final report saved → {output_path}")
    return output_path


def print_similarity_matrix(similarity_matrix, paper_names):
    """
    Format and print a similarity matrix in a readable table format.
    Compatible with the reference project's main.py helper function.

    Args:
        similarity_matrix: 2D array/list of similarity scores (numpy array or list)
        paper_names:       list of paper names/identifiers
    """
    if similarity_matrix is None or len(similarity_matrix) == 0:
        print("\nCosine similarity could not be computed.")
        return

    print("\n--- Cosine Similarity Matrix ---")
    header = "Paper".ljust(18)
    for name in paper_names:
        header += name[:10].ljust(12)
    print(header)

    # Convert numpy array to list if necessary
    try:
        matrix_list = similarity_matrix.tolist() if hasattr(similarity_matrix, 'tolist') else similarity_matrix
    except (AttributeError, TypeError):
        matrix_list = similarity_matrix

    for i, row in enumerate(matrix_list):
        line = paper_names[i][:15].ljust(18) if i < len(paper_names) else f"Paper {i}".ljust(18)
        for value in row:
            line += f"{float(value):.2f}".ljust(12)
        print(line)


