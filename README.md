# 🔬 AI Research Agent

**Automate your literature review process** - Search, analyze, and synthesize academic research papers in minutes.

---

## 🎯 What It Does

This tool helps researchers automatically:
1. **Search** for academic papers on any topic
2. **Analyze** papers to extract key findings and methodologies
3. **Generate** comprehensive research synthesis documents

Perfect for literature reviews, research surveys, and staying up-to-date with academic publications.

---

## ✨ Key Features

### 🔍 Smart Paper Search
- Search Semantic Scholar's database of 200M+ papers
- Automatic retry handling for API rate limits
- Extracts metadata: title, authors, year, citations, abstracts

### 📊 Intelligent Analysis
- Identifies paper sections (Background, Methods, Results, Conclusions)
- Extracts key findings and research methodologies
- Compares multiple papers to find common themes
- Analyzes citation impact and research trends

### ✍️ Automated Writing
- Generates structured research documents
- Creates abstracts, methods comparisons, and results synthesis
- Formats references in APA style (7th edition)
- Produces ready-to-use markdown documents

---

## 🎓 Acknowledgements

*   Developed as part of the **Infosys Springboard Internship** program.
*   Special thanks to the Infosys Springboard team for their mentorship and guidance throughout the development of this AI Research Agent.
*   This project demonstrates the practical application of AI in automating academic research workflows.

---

## 🚀 Quick Start

### Installation

```powershell
# 1. Clone or download the project
cd AI_RESEARCH_AGENT

# 2. Create virtual environment
python -m venv venv

# 3. Activate virtual environment (Windows)
.\venv\Scripts\Activate.ps1

# 4. Install dependencies
pip install -r requirements.txt
```

### Usage

**Option 1: Web Dashboard** (Recommended - Milestone 4)
```powershell
# Start the Flask API server
python server.py

# Then open your browser to:
# http://localhost:5000
```
The dashboard provides an interactive interface to:
- Search for papers
- View results in real-time
- Run analysis pipelines
- View and download reports

**Option 2: CLI Pipeline**
```powershell
python main.py
```

This will:
1. Prompt you for a research topic
2. Search and collect papers
3. Analyze the papers
4. Generate a research synthesis document
5. Archive results with timestamp

**Option 3: Run Individual Phases**
```powershell
# Search for papers
python src/search.py

# Analyze papers
python src/analysis.py

# Generate document
python src/writing.py
```

---

## 📖 Example Workflow

**Using Web Dashboard:**
```powershell
# Activate environment
.\venv\Scripts\Activate.ps1

# Start Flask server
python server.py

# Output:
# * Running on http://localhost:5000
# * Open your browser and start searching!
```

**Using CLI:**
```powershell
# Activate environment
.\venv\Scripts\Activate.ps1

# Run the pipeline
python main.py

# Enter your topic when prompted
Enter research topic: machine learning

# Wait for processing (~5-10 seconds)
🔍 Searching for papers...
📊 Analyzing papers...
✍️ Generating document...

# Find your results in:
# output/machine_learning_20260126_190000/
#   ├── Research_Synthesis.md
#   ├── Analysis_Metrics.json
#   └── Source_Papers.json
```

---

## 📂 Project Structure

```
AI_RESEARCH_AGENT/
├── src/
│   ├── search.py          # Paper search module
│   ├── analysis.py        # Analysis engine
│   ├── writing.py         # Document generator
│   ├── pipeline.py        # Workflow orchestrator
│   ├── config.py          # Configuration
│   ├── utils.py           # Utilities
│   └── ai_engine.py       # LLM integration
├── dashboard/             # Web frontend
│   ├── index.html         # Main UI
│   ├── app.js             # Frontend logic
│   └── styles.css         # Styling
├── data/                  # Temporary data storage
├── output/                # Generated reports (timestamped)
├── main.py                # CLI entry point
├── server.py              # Flask API server
├── requirements.txt       # Dependencies
└── README.md              # This file
```

---

## 📊 What You Get

### Analysis Results (`Analysis_Metrics.json`)
```json
{
  "papers": [
    {
      "title": "Paper Title",
      "sections": {
        "background": "...",
        "methods": "...",
        "results": "..."
      },
      "key_findings": [...],
      "methodology": {...}
    }
  ],
  "cross_paper_analysis": {
    "common_keywords": {...},
    "citation_analysis": {...},
    "research_trends": [...]
  }
}
```

### Research Document (`Research_Synthesis.md`)
- **Abstract** - 100-word summary
- **Introduction** - Research context
- **Methods Comparison** - Methodology analysis
- **Results Synthesis** - Key findings
- **Discussion** - Insights and implications
- **References** - APA-formatted citations

---

## ⚙️ Configuration

Edit `src/config.py` to customize:

```python
SEARCH_LIMIT_DEFAULT = 3        # Number of papers to retrieve
ABSTRACT_WORD_LIMIT = 100       # Abstract word count
SEARCH_TIMEOUT_SECONDS = 10     # API timeout
```

---

## 🎨 Dashboard Features

The web dashboard (`dashboard/`) provides:

- **Search Interface** - Query academic papers with autocomplete
- **Real-time Pipeline** - Monitor analysis progress with status indicators
- **Results Visualization** - Browse papers, key findings, and synthesized insights
- **Report Management** - View and download archived analyses
- **Export Options** - Get results in APA or BibTeX format
- **Responsive Design** - Works on desktop and mobile browsers

Access it at: **http://localhost:5000** (after running `python server.py`)

---

## 💡 Tips for Best Results

**Dashboard Tips:**
- Start the server with `python server.py` before opening the dashboard
- Browser console (F12) shows API logs for troubleshooting
- Reports are auto-saved and archived for future reference
- Use the export features to share results in standard formats

**Search Tips:**
- Use specific keywords (e.g., "deep learning image classification" vs "AI")
- Try different phrasings if results aren't relevant
- 3-5 papers work best for quick analysis

**Analysis Tips:**
- Papers with detailed abstracts produce better results
- Recent papers (2020+) typically have more structured abstracts
- Review `Analysis_Metrics.json` before reading the synthesis

**Output Tips:**
- Results are automatically archived with timestamps
- Each run creates a new folder in `output/`
- Edit generated markdown files as needed

---

## 🔧 Troubleshooting

**"No papers found"**
- Try broader search terms
- Check your internet connection
- Verify the topic has academic papers

**"API rate limit exceeded"**
- Wait 1-2 minutes and try again
- The system auto-retries with backoff

**"Import errors"**
- Ensure virtual environment is activated
- Run `pip install -r requirements.txt` again

---

---

## 🔗 Flask API Server

The `server.py` runs a Flask API that powers the web dashboard. Available endpoints:

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/api/status` | Health check & current state |
| POST | `/api/search` | Search papers via Semantic Scholar |
| GET | `/api/papers` | Load saved papers |
| POST | `/api/pipeline/run` | Run analysis pipeline |
| GET | `/api/pipeline/status` | Get pipeline stages |
| GET | `/api/synthesis` | Load latest synthesis |
| POST | `/api/synthesis/run` | Trigger synthesis generation |
| GET | `/api/reports` | List all archived reports |
| GET | `/api/reports/<folder>` | Get specific report data |
| GET | `/api/export/apa` | Download APA references |
| GET | `/api/export/bib` | Download BibTeX file |

Start the server with: `python server.py` (runs on http://localhost:5000)

---

## 📚 Dependencies

- `requests>=2.31.0` - HTTP library for API calls
- `openai>=1.0.0` - GPT integration
- `google-genai>=1.0.0` - Gemini integration
- `python-dotenv>=1.0.0` - Environment variables
- `cohere>=5.0.0` - Cohere AI integration
- `flask>=3.0.0` - Web server
- `flask-cors>=4.0.0` - CORS support for dashboard

---

## 🎓 Project Status

- ✅ **Milestone 1** - Paper Search & Collection (Complete)
- ✅ **Milestone 2** - Analysis & Extraction (Complete)
- ✅ **Milestone 3** - LLM Integration & Writing (Complete)
- ✅ **Milestone 4** - Web Dashboard & API (Complete)

**Latest Features:**
- Web-based dashboard interface
- Flask REST API for backend operations
- Interactive paper search and analysis
- Real-time pipeline status tracking
- Report archival and export functionality

---

## 📝 License & Credits

**API:** [Semantic Scholar](https://www.semanticscholar.org/)  
**Documentation:** [API Docs](https://api.semanticscholar.org/)

---

## 🤝 Contributing

This is an academic project. For questions or issues:
1. Check the troubleshooting section
2. Review the code comments in `src/` files
3. Contact the project maintainer

---

**Built with ❤️ for researchers who want to spend less time searching and more time discovering.**
