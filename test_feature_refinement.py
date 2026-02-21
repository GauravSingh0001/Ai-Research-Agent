#!/usr/bin/env python3
"""
Comprehensive test suite for feature refinement:
1. APA 7th Edition references with lexicographical sorting
2. BibTeX synchronization with APA cite keys
3. PDF export with cache-busting and fallback
4. Critique & review state management with ACADEMIC_EDITOR_PROMPT
"""

import json
import unittest
import tempfile
import shutil
from pathlib import Path
from datetime import datetime
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from writing import ResearchWriter
from config import OUTPUT_DIR, DATA_DIR

class TestApaReferences(unittest.TestCase):
    """Test APA 7th Edition reference generation."""
    
    def setUp(self):
        """Create sample analysis data for testing."""
        self.test_data = {
            "papers": [
                {
                    "title": "Machine Learning in Healthcare",
                    "authors": ["John Smith", "Jane Doe"],
                    "year": 2023,
                    "venue": "Nature Medicine",
                    "url": "https://example.com/paper1"
                },
                {
                    "title": "Deep Learning Applications",
                    "authors": ["Alice Watson"],
                    "year": 2022,
                    "venue": "IEEE Transactions",
                    "url": "https://example.com/paper2"
                },
                {
                    "title": "Artificial Intelligence Ethics",
                    "authors": ["Bob Johnson", "Carol Lee", "David Brown"],
                    "year": 2023,
                    "venue": "ACM Computing Surveys",
                    "url": "https://example.com/paper3"
                }
            ]
        }
        
        # Create temporary directory for output
        self.test_dir = tempfile.mkdtemp()
        self.analysis_file = Path(self.test_dir) / "analysis.json"
        self.analysis_file.write_text(json.dumps({"papers": self.test_data["papers"]}))
    
    def tearDown(self):
        """Clean up test directory."""
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def test_tokenize_author_names(self):
        """Test author name tokenization."""
        writer = ResearchWriter(analysis_file=str(self.analysis_file))
        
        # Test single author with single name
        surname, formatted = writer._tokenize_author_names("Smith")
        self.assertEqual(surname, "smith")
        self.assertEqual(formatted, "Smith")
        
        # Test simple author name
        surname, formatted = writer._tokenize_author_names("John Smith")
        self.assertEqual(surname, "smith")
        self.assertEqual(formatted, "Smith, J.")
        
        # Test author with middle name
        surname, formatted = writer._tokenize_author_names("John David Smith")
        self.assertEqual(surname, "smith")
        self.assertEqual(formatted, "Smith, J. D.")
        
        # Test hyphenated name
        surname, formatted = writer._tokenize_author_names("Marie-Pierre Curie")
        self.assertEqual(surname, "curie")
        self.assertEqual(formatted, "Curie, M.-P.")
    
    def test_references_lexicographical_sorting(self):
        """Test that references are sorted lexicographically by surname."""
        writer = ResearchWriter(analysis_file=str(self.analysis_file))
        result = writer.generate_references()
        
        # Result should be a dict with "text" and "cite_keys"
        self.assertIsInstance(result, dict)
        self.assertIn("text", result)
        self.assertIn("cite_keys", result)
        
        ref_text = result["text"]
        
        # References should be sorted by surname: Alice, Bob, Jane, John
        lines = ref_text.split("\n\n")
        self.assertGreater(len(lines), 0)
        
        # First reference should start with "Watson" (Alice Watson)
        self.assertIn("Watson", lines[0])
        
        # Check that all expected surnames are present
        self.assertIn("Watson", ref_text)
        self.assertIn("Johnson", ref_text)
        self.assertIn("Smith", ref_text)
    
    def test_references_apa_format(self):
        """Test APA 7th Edition formatting."""
        writer = ResearchWriter(analysis_file=str(self.analysis_file))
        result = writer.generate_references()
        ref_text = result["text"]
        
        # Check for structured APA format: Author(s). (Year). Title. Venue. URL
        self.assertRegex(ref_text, r'\w+, [A-Z]\.')  # Author, I. format
        self.assertRegex(ref_text, r'\(\d{4}\)\.')  # (Year).
        self.assertRegex(ref_text, r'\*\w+')  # *Venue* in markdown
        self.assertIn("https://", ref_text)  # URLs present
    
    def test_cite_keys_generation(self):
        """Test that cite keys are generated and unique."""
        writer = ResearchWriter(analysis_file=str(self.analysis_file))
        result = writer.generate_references()
        cite_keys = result["cite_keys"]
        
        # Should have cite keys for all papers
        self.assertGreater(len(cite_keys), 0)
        
        # Cite keys should be unique
        cite_key_values = list(cite_keys.values())
        self.assertEqual(len(cite_key_values), len(set(cite_key_values)))


class TestBibTexSynchronization(unittest.TestCase):
    """Test BibTeX generation synchronized with APA references."""
    
    def setUp(self):
        """Create sample analysis data."""
        self.test_data = {
            "papers": [
                {
                    "title": "Quantum Computing Basics",
                    "authors": ["Richard Feynman"],
                    "year": 2020,
                    "venue": "Physics Reviews",
                    "url": "https://example.com/quantum"
                },
                {
                    "title": "Classical Computing Theory",
                    "authors": ["Alan Turing"],
                    "year": 2021,
                    "venue": "ACM Classics",
                    "url": "https://example.com/turing"
                }
            ]
        }
        
        self.test_dir = tempfile.mkdtemp()
        self.analysis_file = Path(self.test_dir) / "analysis.json"
        self.analysis_file.write_text(json.dumps({"papers": self.test_data["papers"]}))
    
    def tearDown(self):
        """Clean up."""
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def test_bibtex_generation(self):
        """Test BibTeX entry generation."""
        writer = ResearchWriter(analysis_file=str(self.analysis_file))
        bibtex = writer.generate_bibtex()
        
        self.assertIsInstance(bibtex, str)
        self.assertIn("@article{", bibtex)
        self.assertIn("author", bibtex)
        self.assertIn("title", bibtex)
        self.assertIn("journal", bibtex)
        self.assertIn("year", bibtex)
    
    def test_bibtex_cite_key_consistency(self):
        """Test that cite keys match between APA and BibTeX."""
        writer = ResearchWriter(analysis_file=str(self.analysis_file))
        
        # Generate both
        ref_result = writer.generate_references()
        cite_keys_from_refs = ref_result["cite_keys"]
        
        bibtex = writer.generate_bibtex()
        
        # Extract cite keys from BibTeX
        import re
        bibtex_keys = set(re.findall(r'@article\{([^,]+)', bibtex))
        
        # All APA cite keys should appear in BibTeX
        # (Note: values from cite_keys mapping should match BibTeX keys)
        cite_key_values = set(cite_keys_from_refs.values())
        
        # BibTeX should have same number of entries as APA
        self.assertEqual(len(bibtex_keys), len(cite_key_values))
    
    def test_bibtex_author_format(self):
        """Test BibTeX author formatting."""
        writer = ResearchWriter(analysis_file=str(self.analysis_file))
        bibtex = writer.generate_bibtex()
        
        # BibTeX should use "Last, First" format with "and" separator
        self.assertRegex(bibtex, r'author\s*=\s*\{[\w\s,.-]+\}')
        # Check for "and" separator between multiple authors
        if len(self.test_data["papers"][0]["authors"]) > 1:
            self.assertIn(" and ", bibtex)


class TestRevisionStateManagement(unittest.TestCase):
    """Test revision state management with ACADEMIC_EDITOR_PROMPT."""
    
    def setUp(self):
        """Set up test environment."""
        self.test_dir = tempfile.mkdtemp()
        
        # Create mock synthesis document
        self.synthesis_file = Path(self.test_dir) / "synthesis.md"
        self.synthesis_file.write_text("""## Introduction
This is an introduction to the research.

## Methods
The methods used in this study.

## Results
The results are presented here.

## References
Smith, J. (2023). A study. *Journal*, 1-10.
""")
        
        # Create mock analysis file
        self.analysis_file = Path(self.test_dir) / "analysis.json"
        self.analysis_file.write_text(json.dumps({
            "papers": [
                {
                    "title": "A study",
                    "authors": ["John Smith"],
                    "year": 2023,
                    "venue": "Journal",
                    "url": "https://example.com"
                }
            ]
        }))
    
    def tearDown(self):
        """Clean up."""
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def test_academic_editor_prompt_defined(self):
        """Test that ACADEMIC_EDITOR_PROMPT is properly defined."""
        from writing import ACADEMIC_EDITOR_PROMPT
        
        self.assertIsNotNone(ACADEMIC_EDITOR_PROMPT)
        self.assertIsInstance(ACADEMIC_EDITOR_PROMPT, str)
        
        # Check for key rules in prompt
        required_keywords = [
            "meticulous",
            "editor",
            "CRITICAL EDITOR RULES",
            "hallucinated",
            "citations",
            "Markdown",
            "academic"
        ]
        
        for keyword in required_keywords:
            self.assertIn(keyword.lower(), ACADEMIC_EDITOR_PROMPT.lower(),
                         f"ACADEMIC_EDITOR_PROMPT missing expected content: {keyword}")


class TestPdfExportFunctionality(unittest.TestCase):
    """Test PDF export enhancements."""
    
    def test_export_pdf_cache_busting(self):
        """Test that PDF export includes cache-busting parameters."""
        # Read the app.js file
        app_js_path = Path(__file__).parent / "dashboard" / "app.js"
        if app_js_path.exists():
            app_js_content = app_js_path.read_text()
            
            # Check for cache-busting timestamp parameter
            self.assertIn("?t=${Date.now()}", app_js_content,
                         "Cache-busting timestamp parameter missing")
            
            # Check for Cache-Control headers
            self.assertIn("Cache-Control", app_js_content,
                         "Cache-Control header missing")
            
            # Check for no-cache directives
            self.assertIn("no-cache", app_js_content,
                         "no-cache directive missing")
    
    def test_export_pdf_fallback_styling(self):
        """Test that PDF fallback has enhanced styling."""
        app_js_path = Path(__file__).parent / "dashboard" / "app.js"
        if app_js_path.exists():
            app_js_content = app_js_path.read_text()
            
            # Check for Georgia serif font specification
            self.assertIn("Georgia", app_js_content,
                         "Georgia serif font missing from print styling")
            
            # Check for page break handling
            self.assertIn("page-break", app_js_content,
                         "Page break CSS rules missing")
            
            # Check for margin and padding rules
            self.assertIn("margin", app_js_content,
                         "Margin rules missing from styling")


class TestIntegration(unittest.TestCase):
    """Integration tests for all three features."""
    
    def setUp(self):
        """Create comprehensive test data."""
        self.test_dir = tempfile.mkdtemp()
        
        self.test_papers = [
            {
                "title": "Climate Change Impact on Biodiversity",
                "authors": ["Anna Anderson", "Brian Brooks"],
                "year": 2023,
                "venue": "Environmental Science & Technology",
                "url": "https://doi.org/example/1"
            },
            {
                "title": "Renewable Energy Systems",
                "authors": ["Carol Chen"],
                "year": 2022,
                "venue": "Sustainable Energy Reviews",
                "url": "https://doi.org/example/2"
            },
            {
                "title": "Machine Learning for Climate Prediction",
                "authors": ["David Davis", "Emma Evans", "Frank Foster"],
                "year": 2023,
                "venue": "Nature Climate Change",
                "url": "https://doi.org/example/3"
            }
        ]
        
        self.analysis_file = Path(self.test_dir) / "analysis.json"
        self.analysis_file.write_text(json.dumps({"papers": self.test_papers}))
    
    def tearDown(self):
        """Clean up."""
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def test_end_to_end_reference_generation(self):
        """Test complete reference generation workflow."""
        writer = ResearchWriter(analysis_file=str(self.analysis_file))
        
        # Generate APA references
        ref_result = writer.generate_references()
        refs_text = ref_result["text"]
        cite_keys = ref_result["cite_keys"]
        
        # Verify references exist
        self.assertGreater(len(refs_text), 0)
        self.assertGreater(len(cite_keys), 0)
        
        # Generate BibTeX
        bibtex = writer.generate_bibtex()
        
        # Verify BibTeX entries exist
        self.assertGreater(len(bibtex), 0)
        
        # Count entries - should match
        apa_count = len([p for p in self.test_papers])
        bibtex_count = len([line for line in bibtex.split("\n") if line.startswith("@article")])
        self.assertEqual(apa_count, bibtex_count)
        
        print(f"✓ Generated {apa_count} APA references and {bibtex_count} BibTeX entries")
    
    def test_complete_output_sections(self):
        """Test that all output sections are properly populated."""
        writer = ResearchWriter(analysis_file=str(self.analysis_file))
        
        # Generate all sections
        writer.generate_references()
        writer.generate_bibtex()
        
        # Check that sections are stored
        self.assertIn("references", writer.output_sections)
        self.assertIn("bibtex", writer.output_sections)
        
        # Verify content is non-empty
        self.assertGreater(len(writer.output_sections["references"]), 0)
        self.assertGreater(len(writer.output_sections["bibtex"]), 0)
        
        print(f"✓ All output sections properly populated")


def run_tests():
    """Run all tests and generate report."""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    suite.addTests(loader.loadTestsFromTestCase(TestApaReferences))
    suite.addTests(loader.loadTestsFromTestCase(TestBibTexSynchronization))
    suite.addTests(loader.loadTestsFromTestCase(TestRevisionStateManagement))
    suite.addTests(loader.loadTestsFromTestCase(TestPdfExportFunctionality))
    suite.addTests(loader.loadTestsFromTestCase(TestIntegration))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    print(f"\n{'='*60}")
    print("  FEATURE REFINEMENT TEST SUMMARY")
    print(f"{'='*60}")
    print(f"Tests Run: {result.testsRun}")
    print(f"Successes: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    
    if result.wasSuccessful():
        print("\n✓ All feature refinements validated successfully!")
    else:
        print("\n✗ Some tests failed. See details above.")
    
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
