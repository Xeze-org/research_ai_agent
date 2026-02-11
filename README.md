# Research AI Agent

A robust, multi-step research agent that uses **Mistral AI** and **DuckDuckGo** to
produce comprehensive, **LaTeX-formatted** academic reports from any topic.

## Features

- **Multi-step research pipeline** — the AI generates diverse search queries,
  aggregates web sources, then writes a detailed LaTeX report.
- **LaTeX output** — reports are generated in LaTeX, displayed in the browser,
  and exportable as `.tex` or PDF.
- **Retry logic** — API calls and web searches use exponential-backoff retries
  (via `tenacity`) for reliability.
- **Configurable depth** — choose Quick / Standard / Deep research intensity.
- **Model selector** — pick `mistral-medium-latest`, `mistral-small-latest`, or
  `mistral-large-latest`.
- **Research history** — all reports are saved to a local SQLite database and
  can be re-opened or deleted from the sidebar.
- **PDF export** — uses `pdflatex` if available, otherwise falls back to
  `xhtml2pdf` for PDF generation.
- **Source tracking** — every cited source is stored and browsable in a
  dedicated tab.

## Prerequisites

- Python 3.9+
- A Mistral AI API key — get one at [console.mistral.ai](https://console.mistral.ai/)
- *(Optional)* A LaTeX distribution (e.g. TeX Live, MiKTeX) for native PDF
  compilation.  If not installed the app falls back to `xhtml2pdf`.

## Setup

1. **Clone the repository**

2. **Create a virtual environment** (recommended):
   ```bash
   python -m venv venv
   # Windows
   venv\Scripts\activate
   # macOS / Linux
   source venv/bin/activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure your API key** — create a `.env` file:
   ```
   MISTRAL_API_KEY=your_actual_api_key_here
   ```
   Or enter the key directly in the app sidebar.

## Usage

```bash
streamlit run app.py
```

Or on Windows, double-click `run.bat`.

## How It Works

1. You enter a research topic.
2. The agent asks Mistral to generate several diverse search queries.
3. Each query is run against DuckDuckGo (with retry logic).
4. The aggregated results are passed as context to Mistral, which writes a
   full LaTeX report body.
5. The report is rendered in three tabs:
   - **Report** — a nicely formatted view in the browser.
   - **Sources** — expandable list of every cited source.
   - **LaTeX Source** — raw `.tex` code you can copy.
6. Export as `.tex` or PDF with one click.

## Troubleshooting

| Problem | Fix |
|---|---|
| **Authentication error** | Check the API key in `.env` or the sidebar. |
| **Model not found** | Switch to `mistral-small-latest` in the sidebar. |
| **Search failures** | The agent retries automatically; check your internet connection. |
| **PDF download missing** | Install a LaTeX distribution, or ensure `xhtml2pdf` is installed. |
