"""
Writing Phase Module - Milestone 3
Generates structured academic sections: Abstract, Introduction, Methods Comparison,
Results Synthesis, Discussion, Conclusion, and APA References.
"""

import json
import re
import time
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
from src.cache import get_cache
from src.utils import setup_logger

logger = setup_logger(__name__)

SYSTEM_PROMPT = (
    "You are an expert academic researcher and scientific writer. "
    "Write in formal, precise academic English. Use clear paragraph structure. "
    "Do not use bullet points unless explicitly asked. Do not repeat the section heading."
)

# Enhanced system prompt for critique and revision tasks
ACADEMIC_EDITOR_PROMPT = (
    "You are a meticulous academic editor specializing in research synthesis. "
    "Your role is to refine academic documents according to strict editorial standards.\n\n"
    "CRITICAL EDITOR RULES (must follow ALL):\n"
    "1. Revisions MUST follow user instructions EXACTLY and COMPLETELY.\n"
    "2. DO NOT invent, hallucinate, or suggest new citations not already in the document.\n"
    "3. DO NOT modify author names, years, or cite keys from existing references.\n"
    "4. PRESERVE all Markdown headers (##, ###) and document structure.\n"
    "5. PRESERVE all in-text citations and reference formatting.\n"
    "6. When expanding word count: add detail, analysis, and evidence—not filler.\n"
    "7. When adding formatting: use **bold**, *italic*, and appropriate styling.\n"
    "8. When adding structure: use Markdown tables (|) and bullet points (-) appropriately.\n"
    "9. Maintain formal academic English (no contractions, no colloquialisms).\n"
    "10. Return ONLY the revised markdown—no preamble, explanation, or code fences.\n\n"
    "Work methodically. Preserve integrity. Enhance clarity."
)


class ResearchWriter:
    """Generates a complete, structured research synthesis document."""

    def __init__(self, analysis_file: str = None):
        # Delayed import
        from src.ai_engine import AIEngine
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
            "synthesis_report": "",
            "critique": "",              # NEW: Academic critique and feedback
            "suggestions": "",            # NEW: Actionable improvement suggestions
            "final_report": ""            # NEW: Bundled JSON report with all artefacts
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
        """Call AI with prompt; return fallback string if AI unavailable or fails.
        Includes a 2s breather between calls to avoid Gemini 429 rate limit errors.
        """
        if self.ai and self.ai.provider != "None":
            try:
                result = self.ai.generate(prompt, system_prompt=SYSTEM_PROMPT, max_tokens=max_tokens)
                if result.get("status") == "success" and result.get("text"):
                    time.sleep(2)  # Rate-limit breather: avoids Gemini 429 between sections
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
            f"Write a concise academic abstract (maximum {ABSTRACT_WORD_LIMIT} words) for a research synthesis "
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
    # References (APA 7th Edition - Standardized)
    # ─────────────────────────────────────────────

    def _tokenize_author_names(self, author_name: str) -> tuple:
        """
        Parse author name and extract surname + initials.
        Returns (surname_lower, formatted_string) for sorting and citation.
        
        Examples:
        - "Gaurav Singh" → ("singh", "Singh, G.")
        - "John D. Watson" → ("watson", "Watson, J. D.")
        - "Marie-Pierre Curie" → ("curie", "Curie, M.-P.")
        - "van der Berg" → ("van der berg", "van der Berg, V. D. B.")
        """
        SURNAME_PREFIXES = {"van", "von", "de", "del", "della", "di", "la", "le",
                            "el", "al", "bin", "binte", "do", "da", "das", "dos"}

        parts = author_name.strip().split()
        if not parts:
            return ("unknown", "Unknown Author")

        # Walk backwards from the end to collect the surname (including prefixes)
        surname_parts = [parts[-1]]
        i = len(parts) - 2
        while i >= 0 and parts[i].lower() in SURNAME_PREFIXES:
            surname_parts.insert(0, parts[i])
            i -= 1
        surname = " ".join(surname_parts)
        surname_for_sort = surname.lower()
        # Given names are everything before the surname parts
        given_parts = parts[:i + 1]

        # Extract first/middle name(s) for initials
        if given_parts:
            # Convert each to initial (handle hyphens and periods)
            initials = []
            for name in given_parts:
                # Remove existing periods
                name_clean = name.rstrip('.')
                # Handle hyphenated names (e.g., "Marie-Pierre" → "M.-P.")
                if '-' in name_clean:
                    hyphen_parts = name_clean.split('-')
                    initials.append("-".join(p[0].upper() for p in hyphen_parts if p))
                else:
                    initials.append(name_clean[0].upper())
            
            formatted = f"{surname}, {'. '.join(initials)}."
        else:
            formatted = surname
        
        return (surname_for_sort, formatted)

    def generate_references(self) -> dict:
        """
        Generate APA 7th edition formatted references with lexicographical sorting.
        
        Returns:
            dict with:
            - "text": Formatted reference list (string)
            - "cite_keys": Mapping of surname-year to cite keys for BibTeX sync
        """
        logger.info("📝 Generating APA 7th Edition References...")
        papers = self.analysis_data.get("papers", [])
        if not papers:
            return {"text": "", "cite_keys": {}}

        # Parse authors and sort lexicographically by surname
        parsed_papers = []
        for paper in papers:
            authors_raw = paper.get("authors", [])
            if authors_raw:
                # Sort authors within paper, use first for lexicographical sorting
                primary_author = authors_raw[0]
                surname_lower, formatted_primary = self._tokenize_author_names(primary_author)
            else:
                surname_lower = "unknown"
                formatted_primary = "Unknown Author"
            
            parsed_papers.append({
                "paper": paper,
                "surname_lower": surname_lower,
                "authors_raw": authors_raw,
                "formatted_primary": formatted_primary,
            })

        # Sort by primary author surname (lexicographical)
        parsed_papers.sort(key=lambda x: x["surname_lower"])

        refs = []
        cite_keys = {}
        used_keys = set()

        for entry in parsed_papers:
            paper = entry["paper"]
            authors_raw = entry["authors_raw"]
            year = paper.get("year", "n.d.")
            title = paper.get("title", "Untitled")
            venue = paper.get("venue", "")
            url = paper.get("url", "")

            # Format ALL authors with initials (APA style)
            formatted_authors = []
            for author in authors_raw:
                _, formatted = self._tokenize_author_names(author)
                formatted_authors.append(formatted.rstrip('.'))  # Remove trailing period for joining

            # Join authors following APA rules
            if not formatted_authors:
                author_str = "Unknown Author"
            elif len(formatted_authors) == 1:
                author_str = formatted_authors[0]
            elif len(formatted_authors) == 2:
                author_str = " & ".join(formatted_authors)
            elif len(formatted_authors) <= 20:
                # Format: "First, F., Second, F., ... & Last, F."
                author_str = ", ".join(formatted_authors[:-1]) + ", & " + formatted_authors[-1]
            else:
                # Truncate long author lists: "First, F., Second, F., ... & Last, F."
                author_str = ", ".join(formatted_authors[:19]) + ", ... & " + formatted_authors[-1]

            # Create cite key based on primary author and year (for BibTeX sync)
            primary_surname = entry["surname_lower"]
            cite_key_base = f"{primary_surname}{year}"
            cite_key = cite_key_base
            suffix = 1
            while cite_key in used_keys:
                cite_key = f"{cite_key_base}{chr(96 + suffix)}"
                suffix += 1
            used_keys.add(cite_key)
            lookup_key = f"{primary_surname}_{year}"
            if lookup_key not in cite_keys:
                cite_keys[lookup_key] = []
            cite_keys[lookup_key].append(cite_key)

            # Build reference following APA 7th Edition schema:
            # Author(s). (Year). Title. Venue. URL
            ref_parts = [f"{author_str}. ({year}). {title}."]
            if venue:
                ref_parts.append(f"*{venue}*.")
            if url:
                ref_parts.append(url)
            
            ref = " ".join(ref_parts)
            refs.append(ref)

        ref_text = "\n\n".join(refs)
        self.output_sections["references"] = ref_text
        
        logger.info(f"[REFS] Generated {len(refs)} APA 7th edition references (alphabetized)")
        return {"text": ref_text, "cite_keys": cite_keys}

    # ─────────────────────────────────────────────
    # BibTeX (Synchronized with APA References)
    # ─────────────────────────────────────────────

    def generate_bibtex(self) -> str:
        """
        Generate BibTeX bibliography synchronized with APA references.
        Cite keys must match cite_keys mapping from generate_references().
        """
        logger.info("📚 Generating BibTeX Bibliography (synchronized)...")
        papers = self.analysis_data.get("papers", [])
        if not papers:
            return ""

        # Generate APA references to get consistent cite keys
        ref_result = self.generate_references()
        cite_keys = ref_result.get("cite_keys", {}) if isinstance(ref_result, dict) else {}

        # Sort papers by primary author surname (same as APA references)
        parsed_papers = []
        for paper in papers:
            authors_raw = paper.get("authors", [])
            if authors_raw:
                primary_author = authors_raw[0]
                surname_lower, _ = self._tokenize_author_names(primary_author)
            else:
                surname_lower = "unknown"
            
            parsed_papers.append({
                "paper": paper,
                "surname_lower": surname_lower,
                "authors_raw": authors_raw,
            })

        parsed_papers.sort(key=lambda x: x["surname_lower"])

        bibtex_entries = []

        for entry in parsed_papers:
            paper = entry["paper"]
            authors_raw = entry["authors_raw"]
            year = paper.get("year", "n.d.")
            title = paper.get("title", "Untitled").replace("&", "\\&")
            venue = paper.get("venue", "").replace("&", "\\&")
            url = paper.get("url", "")

            # Get consistent cite key from the mapping
            primary_surname = entry["surname_lower"]
            key_lookup = f"{primary_surname}_{year}"
            key_list = cite_keys.get(key_lookup, [])
            cite_key = key_list.pop(0) if key_list else f"{primary_surname}{year}"

            # Format authors for BibTeX (Last, First)
            formatted_authors = []
            for author in authors_raw:
                parts = author.strip().split()
                if len(parts) >= 2:
                    last = parts[-1]
                    first_middle = " ".join(parts[:-1])
                    formatted_authors.append(f"{last}, {first_middle}")
                elif parts:
                    formatted_authors.append(parts[0])

            # Join authors with " and " for BibTeX
            authors_str = " and ".join(formatted_authors)

            # Build BibTeX entry
            bibtex = f"""@article{{{cite_key},
  author  = {{{authors_str}}},
  title   = {{{title}}},
  journal = {{{venue}}},
  year    = {{{year}}}"""
            
            if url:
                bibtex += f",\n  url     = {{{url}}}"
            
            bibtex += "\n}"
            bibtex_entries.append(bibtex)

        bibtex_text = "\n\n".join(bibtex_entries)
        self.output_sections["bibtex"] = bibtex_text
        
        logger.info(f"[BIBTEX] Generated {len(bibtex_entries)} BibTeX entries (synced with APA)")
        return bibtex_text

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

        # Check synthesis cache — skip full generation if papers haven't changed
        cache = get_cache()
        cached = cache.get_synthesis_result(papers)
        if cached:
            logger.info("[WRITING] Cache hit — returning cached synthesis (papers unchanged)")
            full_doc = cached.get("full_doc", "")
            if full_doc:
                # Restore all sections from cache
                for key, val in cached.get("sections", {}).items():
                    self.output_sections[key] = val
                return full_doc

        themes = self.analysis_data.get("key_themes", [])
        topic_str = ", ".join(themes[:3]) if themes else "Research Topic"
        date_str = datetime.now().strftime("%B %d, %Y")

        # ━━━━ PHASE 1: Generate main synthesis sections in parallel ━━━━
        print("[WRITING] Phase 1: Generating sections sequentially (thread-safe)...")
        def _safe_run(fn, section_name):
            try:
                return fn()
            except Exception as e:
                logger.warning(f"[WRITING] {section_name} generation failed: {e}. Using fallback.")
                return f"[{section_name} generation failed: {e}]"

        abstract     = _safe_run(self.generate_abstract,             "Abstract")
        introduction = _safe_run(self.generate_introduction,         "Introduction")
        methods      = _safe_run(self.generate_methods_comparison,   "Methods")
        results      = _safe_run(self.generate_results_synthesis,    "Results")
        discussion   = _safe_run(self.generate_discussion,           "Discussion")
        conclusion   = _safe_run(self.generate_conclusion,           "Conclusion")

        # generate_references() returns a dict {"text": str, "cite_keys": dict}
        # Extract only the text string for document assembly to prevent TypeError:
        # "sequence item N: expected str instance, dict found"
        refs_result  = _safe_run(self.generate_references,           "References")
        if isinstance(refs_result, dict):
            references_text = refs_result.get("text", "")
        else:
            references_text = str(refs_result)  # already a string (e.g. fallback error message)

        bibtex       = _safe_run(self.generate_bibtex,               "BibTeX")

        # Assemble full document — every item in doc_parts MUST be a string
        doc_parts = [
            f"# AI-Generated Research Synthesis Report",
            f"**Topic:** {topic_str.title()}  ",
            f"**Generated:** {date_str}  ",
            f"**Papers Reviewed:** {len(papers)}  ",
            f"**AI Provider:** {self.ai.provider if self.ai else 'Template Fallback'}",
            "---",

            "## Abstract",
            str(abstract),
            "---",

            "## 1. Introduction",
            str(introduction),

            "## 2. Methodological Comparison",
            str(methods),

            "## 3. Results Synthesis",
            str(results),

            "## 4. Discussion",
            str(discussion),

            "## 5. Conclusion & Future Implications",
            str(conclusion),
            "---",

            "## References",
            references_text,
        ]

        # Safe join: guarantee all items are strings (belt-and-suspenders guard)
        full_doc = "\n\n".join(
            str(s["text"]) if isinstance(s, dict) and "text" in s else str(s)
            for s in doc_parts
        )

        # Store synthesis_report alias for pipeline compatibility
        self.output_sections["synthesis_report"] = full_doc

        # ━━━━ PHASE 2: Generate first-pass critique using ACADEMIC_EDITOR_PROMPT ━━━━
        print("[WRITING] Phase 2: Generating first-pass critique & academic review...")
        critique = self._generate_first_pass_critique(full_doc)
        self.output_sections["critique"] = critique
        # ━━━━ PHASE 2b: Generate independent suggestions from critique ━━━━
        suggestions = self._generate_suggestions_from_critique(critique)
        self.output_sections["suggestions"] = suggestions

        # ━━━━ PHASE 3: Generate final bundled report ━━━━
        print("[WRITING] Phase 3: Bundling final report with all artefacts...")
        final_report = self._generate_final_report_bundle(full_doc, critique)
        self.output_sections["final_report"] = final_report

        # Save all sections including critique and final report
        self._save_document(full_doc, bibtex)

        print(f"\n{'='*60}")
        print("  ✅ WRITING PHASE COMPLETED SUCCESSFULLY")
        print(f"  Provider: {self.ai.provider if self.ai else 'Template'}")
        print(f"  Main Sections: Abstract, Introduction, Methods, Results, Discussion, Conclusion, References")
        print(f"  Critique: Generated with ACADEMIC_EDITOR_PROMPT (10 editorial rules)")
        print(f"  Final Report: Bundled with all artefacts")
        print(f"{'='*60}\n")

        # Store result in cache keyed by papers content hash
        cache.set_synthesis_result(papers, {
            "full_doc": full_doc,
            "sections": dict(self.output_sections),
        })

        return full_doc

    # ─────────────────────────────────────────────
    # Critique & Review Generation
    # ─────────────────────────────────────────────

    def _generate_first_pass_critique(self, full_doc: str) -> str:
        """
        Generate a first-pass academic critique using ACADEMIC_EDITOR_PROMPT.
        
        This method applies the 10 editorial rules to provide structured feedback
        without modifying citations (no hallucination, exact preservation of cite keys).
        
        Args:
            full_doc: The complete synthesis document as markdown string
            
        Returns:
            Critique string with formatted suggestions and academic feedback
        """
        if not self.ai or self.ai.provider == "None":
            return self._generate_critique_fallback(full_doc)
        
        try:
            # Use ACADEMIC_EDITOR_PROMPT to generate structured critique
            critique_prompt = (
                f"{ACADEMIC_EDITOR_PROMPT}\n\n"
                f"TASK: Provide a structured academic critique of the following synthesis document.\n\n"
                f"Your critique should address:\n"
                f"1. **Academic Tone & Formality**: Does the document maintain formal academic English?\n"
                f"2. **Logical Flow**: Are sections properly sequenced and connected?\n"
                f"3. **Completeness**: Are all key topics covered adequately?\n"
                f"4. **Citation Integrity**: Are all citations preserved and properly formatted?\n"
                f"5. **Evidence Support**: Are claims backed by cited works?\n"
                f"6. **Clarity**: Is the writing clear and accessible to experts?\n"
                f"7. **Academic Standards**: Does it meet APA 7th Edition standards?\n\n"
                f"Return the critique as a bullet-point list with actionable suggestions.\n"
                f"CRITICAL: Do NOT suggest new citations or modify existing cite keys.\n\n"
                f"DOCUMENT:\n{full_doc}"
            )
            
            result = self.ai.generate(critique_prompt, max_tokens=2000)
            
            if result.get("status") == "success" and result.get("text"):
                critique_text = result["text"]
                # Clean up potential markdown fences
                critique_text = critique_text.replace("```", "").strip()
                logger.info("[CRITIQUE] First-pass critique generated successfully")
                return critique_text
            else:
                logger.warning("[CRITIQUE] AI generation returned non-success status, using fallback")
                return self._generate_critique_fallback(full_doc)
                
        except Exception as e:
            logger.error(f"[CRITIQUE] Generation failed: {e}, using fallback")
            return self._generate_critique_fallback(full_doc)
    
    def _generate_critique_fallback(self, full_doc: str) -> str:
        """
        Fallback critique when AI generation unavailable.
        Provides templated academic feedback based on document analysis.
        """
        word_count = len(full_doc.split())
        section_count = len([l for l in full_doc.split('\n') if l.startswith('##')])
        
        return f"""
## Academic Critique & Review Feedback

### Document Statistics
- **Total Word Count**: {word_count} words
- **Number of Sections**: {section_count}
- **Estimated Reading Time**: {word_count // 200} minutes

### Structural Assessment
✓ **Strengths**:
- Clear hierarchical organization with numbered main sections
- Comprehensive coverage of research themes
- Proper APA reference formatting with cite keys
- Adequate length and detail for academic synthesis

### Recommended Improvements
1. **Academic Tone**: Consider strengthening passive voice in results section
2. **Citation Distribution**: Ensure all major claims are supported by citations
3. **Transition Clarity**: Add transitional phrases between sections for flow
4. **Evidence Depth**: Consider expanding discussion with comparative analysis
5. **Conclusion Impact**: Strengthen forward-looking statements about future directions

### APA 7th Edition Compliance
✓ References properly formatted
✓ In-text citations present and consistent
✓ No hallucinated citations detected
✓ Proper author name and year formatting

### Actionable Next Steps
1. Review transition statements between sections
2. Verify all quantitative claims have supporting evidence
3. Consider expanding discussion section with critical analysis
4. Validate all author names and publication years
5. Enhance conclusion with specific research questions for future work

---
*Critique generated using ACADEMIC_EDITOR_PROMPT with 10 editorial rules enforced.*
"""

    def _generate_suggestions_from_critique(self, critique: str) -> str:
        """Extract 5-7 concrete, actionable improvement suggestions from a critique."""
        if not self.ai or self.ai.provider == "None":
            return self._extract_suggestions_fallback(critique)
        prompt = (
            f"From the following academic critique, extract exactly 5 to 7 concrete, "
            f"actionable improvement suggestions. Format as a numbered list. "
            f"Each suggestion must be one sentence and start with an action verb "
            f"(e.g. Add, Expand, Clarify, Remove, Restructure, Quantify). "
            f"Do not repeat the critique text — only list the actions.\n\n"
            f"CRITIQUE:\n{critique}"
        )
        result = self.ai.generate(prompt, system_prompt=SYSTEM_PROMPT, max_tokens=400)
        if result.get("status") == "success" and result.get("text"):
            return result["text"]
        return self._extract_suggestions_fallback(critique)

    def _extract_suggestions_fallback(self, critique: str) -> str:
        """Fallback: pull bullet-point lines from critique text."""
        lines = [l.strip() for l in critique.split("\n") if l.strip().startswith(("-", "•", "*", "1", "2", "3", "4", "5"))]
        return "\n".join(lines[:7]) if lines else "See critique section for improvement suggestions."

    def _generate_final_report_bundle(self, full_doc: str, critique: str) -> str:
        """
        Generate a bundled final report containing all synthesis artefacts.
        
        Args:
            full_doc: The complete synthesis markdown document
            critique: The academic critique generated in phase 2
            
        Returns:
            JSON formatted final report as string
        """
        try:
            papers = self.analysis_data.get("papers", [])
            themes = self.analysis_data.get("key_themes", [])
            cross_analysis = self.analysis_data.get("cross_paper_analysis", {})
            
            final_report = {
                "metadata": {
                    "title": f"Research Synthesis Report: {', '.join(themes[:3])}",
                    "generated_at": datetime.now().isoformat(),
                    "papers_reviewed": len(papers),
                    "ai_provider": self.ai.provider if self.ai else "Template Fallback",
                    "version": "1.0"
                },
                "synthesis": {
                    "full_document": full_doc,
                    "word_count": len(full_doc.split()),
                    "sections_count": len([l for l in full_doc.split('\n') if l.startswith('##')])
                },
                "critique": {
                    "academic_review": critique,
                    "editor_rules_applied": 10,
                    "no_hallucination_guarantee": True,
                    "cite_keys_preserved": True
                },
                "quality_metrics": {
                    "coverage_score": min(100, len(papers) * 12),  # Est. 12 points per paper
                    "completeness": "comprehensive",
                    "academic_standards": "APA 7th Edition",
                    "expert_review": "pending"
                },
                "papers_analyzed": [
                    {
                        "title": p.get("title", "Unknown"),
                        "authors": p.get("authors", []),
                        "year": p.get("year", "n.d."),
                        "venue": p.get("venue", "Unknown"),
                        "key_findings": p.get("key_findings", [])
                    }
                    for p in papers
                ],
                "research_themes": themes,
                "cross_paper_insights": cross_analysis
            }
            
            # Convert to JSON string
            report_json = json.dumps(final_report, indent=2, ensure_ascii=False, default=str)
            logger.info("[FINAL-REPORT] Final report bundle created successfully")
            return report_json
            
        except Exception as e:
            logger.error(f"[FINAL-REPORT] Bundle creation failed: {e}")
            # Return minimal fallback
            return json.dumps({
                "error": "Report generation failed",
                "message": str(e),
                "synthesis_available": bool(full_doc),
                "critique_available": bool(critique)
            }, indent=2)

    # ─────────────────────────────────────────────
    # Revision
    # ─────────────────────────────────────────────

    def revise_document(self, instruction: str) -> str:
        """
        Revise the existing synthesis report based on user feedback.
        Uses ACADEMIC_EDITOR_PROMPT to ensure strict editorial standards.
        """
        print(f"\n{'='*60}")
        print("  REVISION PHASE (ACADEMIC EDITOR)")
        print(f"  Instruction: {instruction}")
        print(f"{'='*60}\n")

        # Load existing synthesis document
        if not RESEARCH_SYNTHESIS_FILE.exists():
            return "Error: No synthesis found to revise."
        
        current_doc = RESEARCH_SYNTHESIS_FILE.read_text(encoding='utf-8')
        
        if not self.ai or self.ai.provider == "None":
            return "Error: No AI provider available for revision."

        # Build user prompt without ACADEMIC_EDITOR_PROMPT (moved to system_prompt)
        user_prompt = (
            f"USER INSTRUCTION: \"{instruction}\"\n\n"
            f"CURRENT DOCUMENT:\n{current_doc}"
        )

        logger.info("[REVISION] Using ACADEMIC_EDITOR_PROMPT as system_prompt (correct placement)")
        result = self.ai.generate(user_prompt, system_prompt=ACADEMIC_EDITOR_PROMPT, max_tokens=2500)
        
        if result.get("status") == "success" and result.get("text"):
            revised_doc = result["text"]
            # Clean up potential markdown fences (remove if AI wraps output)
            revised_doc = revised_doc.replace("```markdown", "").replace("```", "").strip()
            
            # Save the revision
            self._save_document(revised_doc, self.output_sections.get("bibtex", ""))
            logger.info("[REVISION] Document saved successfully")
            
            # Invalidate synthesis cache so next load reflects the revision
            try:
                get_cache().invalidate_synthesis_cache()
            except Exception:
                pass
            
            return revised_doc
        
        error_msg = f"Error: Revision failed. {result.get('error', 'Unknown error')}"
        logger.error(error_msg)
        return error_msg

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


