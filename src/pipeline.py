
import os
import sys
import shutil
import time
from datetime import datetime
from pathlib import Path

# Fix path to ensure src can be imported
current_dir = Path(__file__).resolve().parent
if str(current_dir.parent) not in sys.path:
    sys.path.append(str(current_dir.parent))

try:
    from src.config import (
        PAPERS_DATA_FILE, 
        ANALYSIS_RESULTS_FILE,
        RESEARCH_SYNTHESIS_FILE,
        SECTIONS_DATA_FILE,
        BIBTEX_FILE,
        OUTPUT_DIR,
        DATA_DIR,
        BASE_DIR
    )
    from src.search import search_papers, save_papers, search_multiple_topics, save_cleaned_dataset, download_pdfs_for_dataset
    from src.analysis import PaperAnalyzer
    from src.writing import ResearchWriter
    from src.utils import setup_logger
except ImportError as e:
    print(f"Import error: {e}")
    sys.exit(1)

logger = setup_logger(__name__)

def archive_results(topic=None):
    """Copy results to a timestamped output folder."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    topic_str = topic.replace(" ", "_")[:40] if topic else "Research_Run"
    folder_name = f"{topic_str}_{timestamp}"
    final_output_dir = OUTPUT_DIR / folder_name
    final_output_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n[INFO] Archiving results → output/{folder_name}/")

    # Individual files
    files_to_copy = [
        (RESEARCH_SYNTHESIS_FILE,              "Research_Synthesis.md"),
        (SECTIONS_DATA_FILE,                   "Sections_Data.json"),
        (ANALYSIS_RESULTS_FILE,                "Analysis_Metrics.json"),
        (PAPERS_DATA_FILE,                     "Source_Papers.json"),
        (BIBTEX_FILE,                          "References.bib"),
        (DATA_DIR / "cleaned_dataset.json",    "cleaned_dataset.json"),
        (DATA_DIR / "similarity_results.json", "similarity_results.json"),
    ]

    for src, dest_name in files_to_copy:
        if src.exists():
            try:
                shutil.copy2(src, final_output_dir / dest_name)
                print(f"   ✓ {dest_name}")
            except Exception as e:
                print(f"   ✗ {src.name}: {e}")
        else:
            print(f"   – {dest_name} (not found, skipping)")

    # Copy sections/ directory
    sections_src = DATA_DIR / "sections"
    if sections_src.exists():
        sections_dst = final_output_dir / "sections"
        try:
            shutil.copytree(sections_src, sections_dst, dirs_exist_ok=True)
            print(f"   ✓ sections/ directory")
        except Exception as e:
            print(f"   ✗ sections/: {e}")

    return final_output_dir

def main():
    print(f"\n{'='*50}")
    print("  AI RESEARCH AGENT — COMPLETE PIPELINE")
    print(f"{'='*50}")

    topics = []
    primary_topic = None

    # ── PHASE 1: SEARCH & COLLECTION ──────────────────────
    print("\nPHASE 1: SEARCH & COLLECTION")
    print("-" * 40)

    if PAPERS_DATA_FILE.exists():
        choice = input("   Found existing papers. Search for new ones? (y/N): ").lower().strip()
    else:
        choice = 'y'

    if choice == 'y':
        # Multi-topic input
        while True:
            try:
                n = int(input("   How many research topics? ").strip())
                if n >= 1:
                    break
                print("   Enter a positive number.")
            except ValueError:
                print("   Enter a valid integer.")

        for i in range(n):
            t = input(f"   Topic {i+1}: ").strip()
            if t:
                topics.append(t)

        if not topics:
            print("[ERROR] No valid topics entered.")
            sys.exit(1)

        primary_topic = topics[0]

        # Optional: papers per topic
        from src.config import SEARCH_LIMIT_DEFAULT
        limit = SEARCH_LIMIT_DEFAULT
        try:
            lim_in = input(f"   Papers per topic (default {limit}): ").strip()
            if lim_in:
                limit = max(1, int(lim_in))
        except ValueError:
            pass

        print(f"\n   Searching {len(topics)} topic(s), {limit} papers each…")
        try:
            dataset = search_multiple_topics(topics, limit_per_topic=limit)
            total = sum(len(v) for v in dataset.values())
            if total == 0:
                print("[ERROR] No papers found for any topic.")
                sys.exit(1)

            # Optional PDF download
            dl = input("   Download open-access PDFs? (y/N): ").strip().lower()
            if dl == 'y':
                count = download_pdfs_for_dataset(dataset)
                print(f"   Downloaded {count} PDFs → pdfs/")

            save_cleaned_dataset(dataset)
            print(f"   [SUCCESS] {total} papers saved across {len(topics)} topic(s)")
            print(f"   → data/cleaned_dataset.json")
            print(f"   → data/papers.json")

        except Exception as e:
            print(f"[ERROR] Search failed: {e}")
            sys.exit(1)
    else:
        print("   Using existing papers data.")
        # Try to infer topic from existing data
        primary_topic = "Research_Run"

    start_time = time.time()

    # ── PHASE 2: ANALYSIS ─────────────────────────────────
    print(f"\n{'='*50}")
    print("PHASE 2: TEXT ANALYSIS & CROSS-PAPER COMPARISON")
    try:
        analyzer = PaperAnalyzer()
        analyzer.run_analysis()
        analyzer._save_analysis()
        analyzer.print_summary()
    except Exception as e:
        logger.error(f"Analysis failed: {e}")
        sys.exit(1)

    # ── PHASE 3: WRITING ──────────────────────────────────
    print(f"\n{'='*50}")
    print("PHASE 3: GENERATING RESEARCH DOCUMENT")
    try:
        writer = ResearchWriter()
        writer.generate_complete_document()
    except Exception as e:
        logger.error(f"Writing failed: {e}")
        sys.exit(1)

    # ── PHASE 4: ARCHIVE ──────────────────────────────────
    print(f"\n{'='*50}")
    topic_label = "_".join(t[:15] for t in topics[:2]) if topics else primary_topic
    final_folder = archive_results(topic_label)

    elapsed = time.time() - start_time

    print(f"\n{'='*50}")
    print("PIPELINE COMPLETED SUCCESSFULLY")
    print(f"Total time  : {elapsed:.2f} seconds")
    print(f"Topics      : {', '.join(topics) if topics else primary_topic}")
    print(f"Final Report: {final_folder / 'Research_Synthesis.md'}")
    print(f"Similarity  : {final_folder / 'similarity_results.json'}")
    print(f"Sections    : {final_folder / 'sections/'} (text files)")
    print(f"{'='*50}\n")


if __name__ == "__main__":
    main()
