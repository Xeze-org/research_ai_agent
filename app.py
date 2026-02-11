"""
Research AI Agent — Robust, LaTeX-formatted research report generator.
Uses Mistral AI + DuckDuckGo for multi-step research with LaTeX output.
"""

import streamlit as st
import os
import re
import json
import sqlite3
import logging
import tempfile
import subprocess
import shutil
from datetime import datetime
from io import BytesIO
from contextlib import contextmanager
from typing import Optional, List, Dict

from dotenv import load_dotenv
from mistralai import Mistral
from duckduckgo_search import DDGS
from tenacity import retry, stop_after_attempt, wait_exponential

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("research_agent")

DB_FILE = "research_history.db"
MAX_RETRIES = 3
DEFAULT_MODEL = "mistral-medium-latest"
FALLBACK_MODEL = "mistral-small-latest"

DEPTH_CONFIG = {
    "Quick": {"queries": 2, "results_per_query": 3},
    "Standard": {"queries": 4, "results_per_query": 5},
    "Deep": {"queries": 6, "results_per_query": 7},
}

# ---------------------------------------------------------------------------
# Streamlit page setup
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Research AI Agent",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
<style>
    /* ── Sidebar: clean neutral background that works in light & dark ── */
    section[data-testid="stSidebar"] {
        background: rgba(128, 128, 128, 0.05);
    }
    section[data-testid="stSidebar"] .stButton > button {
        background: transparent;
        border: 1px solid rgba(128, 128, 128, 0.25);
        border-radius: 8px;
        text-align: left;
        padding: 0.4rem 0.75rem;
        font-size: 0.85rem;
        transition: background 0.15s;
    }
    section[data-testid="stSidebar"] .stButton > button:hover {
        background: rgba(128, 128, 128, 0.12);
    }
    /* ── New-research button accent ── */
    section[data-testid="stSidebar"] .stButton > button[kind="primary"],
    section[data-testid="stSidebar"] [data-testid="stBaseButton-primary"] > button {
        background: #2563eb;
        color: #fff !important;
        border: none;
    }
    /* ── Main area spacing ── */
    .block-container {padding-top: 1.5rem;}
    /* ── Config card ── */
    div[data-testid="stExpander"] {
        border: 1px solid rgba(128, 128, 128, 0.2);
        border-radius: 10px;
    }
    /* ── Buttons / downloads ── */
    .stDownloadButton button {width: 100%;}
    div[data-testid="stTabs"] button {font-size: 1rem;}
    code {font-size: 0.85rem;}
    /* ── Primary action button ── */
    button[kind="primary"],
    [data-testid="stBaseButton-primary"] > button {
        background: #2563eb !important;
        color: #fff !important;
        border: none !important;
        border-radius: 8px !important;
    }
    button[kind="primary"]:hover,
    [data-testid="stBaseButton-primary"] > button:hover {
        background: #1d4ed8 !important;
    }
    /* ── Delete button (small red) ── */
    .del-btn button {
        color: #ef4444 !important;
        border-color: #ef4444 !important;
        padding: 0.15rem 0.5rem !important;
        font-size: 0.75rem !important;
    }
</style>
""",
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Database layer (context-managed, row-factory enabled)
# ---------------------------------------------------------------------------

@contextmanager
def get_db():
    """Yield a SQLite connection with Row factory; auto-commit / rollback."""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    with get_db() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS research (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                topic         TEXT    NOT NULL,
                latex_content TEXT    NOT NULL,
                sources       TEXT,
                model_used    TEXT,
                search_queries TEXT,
                created_at    DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )


def save_research(
    topic: str,
    latex_content: str,
    sources: List[Dict],
    model_used: str,
    search_queries: List[str],
):
    with get_db() as conn:
        conn.execute(
            "INSERT INTO research "
            "(topic, latex_content, sources, model_used, search_queries) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                topic,
                latex_content,
                json.dumps(sources, ensure_ascii=False),
                model_used,
                json.dumps(search_queries, ensure_ascii=False),
            ),
        )


def get_history():
    with get_db() as conn:
        cur = conn.execute(
            "SELECT id, topic, created_at FROM research ORDER BY created_at DESC"
        )
        return cur.fetchall()


def get_research_by_id(r_id: int):
    with get_db() as conn:
        cur = conn.execute("SELECT * FROM research WHERE id = ?", (r_id,))
        return cur.fetchone()


def delete_research(r_id: int):
    with get_db() as conn:
        conn.execute("DELETE FROM research WHERE id = ?", (r_id,))


init_db()

# ---------------------------------------------------------------------------
# Web search with retries
# ---------------------------------------------------------------------------

@retry(
    stop=stop_after_attempt(MAX_RETRIES),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    reraise=True,
)
def _search_web(query: str, max_results: int) -> List[Dict]:
    results = DDGS().text(query, max_results=max_results)
    return results if results else []


def search_web(query: str, max_results: int = 5) -> List[Dict]:
    """Public wrapper that catches final failures gracefully."""
    try:
        return _search_web(query, max_results)
    except Exception as exc:
        logger.warning("Search failed after retries for '%s': %s", query, exc)
        return []


def multi_search(queries: List[str], results_per_query: int = 5) -> List[Dict]:
    """Run several search queries and de-duplicate by URL."""
    all_results: List[Dict] = []
    seen_urls: set = set()
    for q in queries:
        for r in search_web(q, max_results=results_per_query):
            url = r.get("href", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                all_results.append(r)
    return all_results


# ---------------------------------------------------------------------------
# Mistral AI helpers
# ---------------------------------------------------------------------------

def generate_search_queries(
    client: Mistral, model: str, topic: str
) -> List[str]:
    """Ask the LLM to produce short, keyword-style search queries."""
    prompt = (
        "I need to research the following topic using a web search engine.\n"
        "Generate exactly 5 SHORT search-engine queries (max 8 words each).\n"
        "Each query must target a different angle:\n"
        "  1) General overview\n"
        "  2) Recent developments / news\n"
        "  3) Expert opinions or reviews\n"
        "  4) Data, statistics, or benchmarks\n"
        "  5) Practical applications or case studies\n\n"
        "IMPORTANT: Keep queries SHORT like real Google searches — just keywords,\n"
        "no full sentences, no parentheses, no journal names.\n\n"
        f"Topic: {topic}\n\n"
        'Return ONLY a JSON array of strings, e.g.:\n'
        '["photonic spiking neural networks overview", "photonic SNN 2024 advances"]'
    )
    try:
        resp = client.chat.complete(
            model=model,
            messages=[{"role": "user", "content": prompt}],
        )
        if resp and resp.choices:
            text = resp.choices[0].message.content.strip()
            match = re.search(r"\[.*?\]", text, re.DOTALL)
            if match:
                queries = json.loads(match.group())
                # Safety: truncate any query that's still too long
                cleaned = []
                for q in queries[:6]:
                    q = str(q).strip()
                    # Limit to ~60 chars / ~10 words
                    words = q.split()
                    if len(words) > 10:
                        q = " ".join(words[:10])
                    cleaned.append(q)
                return cleaned
    except Exception as exc:
        logger.error("Query-generation error: %s", exc)

    # Fallback: build short keyword queries from the topic
    short_topic = " ".join(topic.split()[:6])  # first 6 words
    return [
        short_topic,
        f"{short_topic} recent research 2025",
        f"{short_topic} expert analysis",
        f"{short_topic} statistics benchmarks",
        f"{short_topic} applications case study",
    ]


def generate_latex_report(
    client: Mistral,
    model: str,
    topic: str,
    context: str,
    sources: List[Dict],
) -> Optional[str]:
    """Generate a LaTeX-formatted research report body (no preamble)."""

    # Build bibliography entries for the prompt
    bib_lines = ""
    for i, s in enumerate(sources, 1):
        safe_title = s.get("title", "N/A").replace("&", r"\&")
        safe_url = s.get("href", "")
        bib_lines += (
            f"  \\bibitem{{source{i}}} {safe_title}. "
            f"\\url{{{safe_url}}}\n"
        )

    system_prompt = r"""You are an expert academic researcher and LaTeX author.
You produce comprehensive, well-structured research reports in LaTeX format.

STRICT RULES — follow every one:
1.  Output ONLY the LaTeX *body* content.  Do NOT include \documentclass,
    \usepackage, \begin{document}, \end{document}, or any preamble.
2.  Use \section{}, \subsection{}, \subsubsection{} for structure.
3.  Use \textbf{} for bold, \textit{} for italic.
    NEVER use markdown bold (**text**) or italic (*text*) — ALWAYS use
    \textbf{} and \textit{}.  This is CRITICAL.
4.  Use \begin{itemize} / \end{itemize} with \item for bullet lists.
5.  Use \begin{enumerate} / \end{enumerate} with \item for numbered lists.
6.  For math use $...$ (inline) and \[ ... \] (display).
7.  For tables, ALWAYS use a proper LaTeX tabular inside a table environment:
      \begin{table}[h!]
      \centering
      \caption{...}
      \begin{tabular}{l c c}
      \hline
      Header1 & Header2 & Header3 \\
      \hline
      val & val & val \\
      \hline
      \end{tabular}
      \end{table}
    NEVER write tables as inline text with **bold headers** on one line.
8.  Include a \section{References} at the end.  Use a
    \begin{thebibliography}{99} ... \end{thebibliography} environment
    citing the sources I provide.  Use \cite{sourceN} in the text.
9.  Do NOT wrap output in ```latex``` code fences.
10. Do NOT use --- or em-dashes as section separators.  Use \bigskip or
    simply start a new \section{} / \subsection{}.
11. Write at least 1500 words.  Be thorough, data-driven, and insightful.
12. Use an academic but accessible tone.  Include concrete examples,
    statistics, and actionable recommendations where appropriate.
"""

    user_prompt = (
        f"Write a comprehensive LaTeX research report on:\n\n"
        f"  {topic}\n\n"
        f"WEB SEARCH CONTEXT:\n{context}\n\n"
        f"SOURCES FOR BIBLIOGRAPHY:\n{bib_lines}\n\n"
        "Begin writing the LaTeX body now."
    )

    try:
        resp = client.chat.complete(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        if resp and resp.choices:
            content = resp.choices[0].message.content.strip()
            # Strip accidental code fences
            content = re.sub(r"^```(?:latex)?\s*", "", content)
            content = re.sub(r"\s*```$", "", content)
            return clean_latex_body(content)
    except Exception as exc:
        logger.error("Report generation error: %s", exc)
        st.error(f"Mistral API error: {exc}")
    return None


# ---------------------------------------------------------------------------
# LaTeX body post-processing — fix common AI output issues
# ---------------------------------------------------------------------------

def clean_latex_body(body: str) -> str:
    """Clean up AI-generated LaTeX body to fix common formatting issues."""

    # 1. Convert markdown bold **text** → \textbf{text}
    #    Handle nested content carefully (non-greedy, no newlines)
    body = re.sub(r"\*\*([^\*\n]+?)\*\*", r"\\textbf{\1}", body)

    # 2. Convert markdown italic *text* → \textit{text}  (single *)
    #    Avoid matching already-converted \textbf or list items
    body = re.sub(r"(?<!\\)(?<!\*)\*([^\*\n]+?)\*(?!\*)", r"\\textit{\1}", body)

    # 3. Remove stray em-dash section separators (--- or — on their own line)
    body = re.sub(r"^\s*[—–]{1,3}\s*$", "", body, flags=re.MULTILINE)
    body = re.sub(r"^\s*-{3,}\s*$", "", body, flags=re.MULTILINE)

    # 4. Remove accidental double-numbering in subsections like
    #    \subsubsection{1. Title}  (the numbering comes from LaTeX already)
    body = re.sub(
        r"(\\(?:sub)*section\{)\d+\.\s*",
        r"\1",
        body,
    )

    # 5. Escape bare % and & that the AI forgot to escape
    #    (only if not already preceded by \)
    body = re.sub(r"(?<!\\)%", r"\\%", body)
    # & is tricky — only escape outside tabular environments
    # Skip this to avoid breaking tabulars

    # 6. Remove blank lines inside itemize/enumerate (causes LaTeX errors)
    body = re.sub(
        r"(\\begin\{(?:itemize|enumerate)\})"
        r"(.*?)"
        r"(\\end\{(?:itemize|enumerate)\})",
        lambda m: m.group(1)
        + re.sub(r"\n\s*\n", "\n", m.group(2))
        + m.group(3),
        body,
        flags=re.DOTALL,
    )

    return body


# ---------------------------------------------------------------------------
# LaTeX → full document (for .tex export & PDF compilation)
# ---------------------------------------------------------------------------

def _truncate_title(title: str, max_words: int = 8) -> str:
    """Return first *max_words* words of a title, adding '...' if truncated."""
    words = title.split()
    if len(words) <= max_words:
        return title
    return " ".join(words[:max_words]) + " ..."


def build_full_latex_document(
    body: str, title: str, author: str = "Research AI Agent"
) -> str:
    """Wrap a LaTeX body in a complete, compilable document."""
    safe_title = title.replace("&", r"\&").replace("%", r"\%").replace("#", r"\#")
    short_title = _truncate_title(safe_title)
    date_str = datetime.now().strftime("%B %d, %Y")

    preamble = (
        r"\documentclass[12pt,a4paper]{article}" "\n"
        r"% ── encoding & fonts ──────────────────────────────────" "\n"
        r"\usepackage[utf8]{inputenc}" "\n"
        r"\usepackage[T1]{fontenc}" "\n"
        r"\usepackage{lmodern}" "\n"
        r"% ── layout ───────────────────────────────────────────" "\n"
        r"\usepackage[margin=2.5cm]{geometry}" "\n"
        r"\usepackage{parskip}" "\n"
        r"\usepackage{microtype}" "\n"
        r"% ── maths ────────────────────────────────────────────" "\n"
        r"\usepackage{amsmath,amssymb}" "\n"
        r"% ── tables ───────────────────────────────────────────" "\n"
        r"\usepackage{booktabs}" "\n"
        r"\usepackage{array}" "\n"
        r"\usepackage{longtable}" "\n"
        r"\usepackage{float}" "\n"
        r"% ── lists ────────────────────────────────────────────" "\n"
        r"\usepackage{enumitem}" "\n"
        r"% ── graphics & colour ────────────────────────────────" "\n"
        r"\usepackage{graphicx}" "\n"
        r"\usepackage{xcolor}" "\n"
        r"% ── headers & footers ────────────────────────────────" "\n"
        r"\usepackage{fancyhdr}" "\n"
        r"\usepackage{titlesec}" "\n"
        r"% ── hyperlinks (load last) ─────────────────────────" "\n"
        r"\usepackage[breaklinks=true]{hyperref}" "\n"
        r"\usepackage{url}" "\n"
        "\n"
        r"% ── page header / footer ─────────────────────────────" "\n"
        r"\pagestyle{fancy}" "\n"
        r"\fancyhf{}" "\n"
        r"\setlength{\headheight}{15pt}" "\n"
        r"\fancyhead[L]{\small\textit{" + short_title + r"}}" "\n"
        r"\fancyhead[R]{\small\thepage}" "\n"
        r"\fancyfoot[C]{\footnotesize Research AI Agent}" "\n"
        r"\renewcommand{\headrulewidth}{0.4pt}" "\n"
        r"\renewcommand{\footrulewidth}{0.2pt}" "\n"
        "\n"
        r"% ── section styling ────────────────────────────────────" "\n"
        r"\definecolor{secblue}{HTML}{1A3A5C}" "\n"
        r"\definecolor{subsecblue}{HTML}{2563EB}" "\n"
        r"\titleformat{\section}" "\n"
        r"  {\Large\bfseries\color{secblue}}" "\n"
        r"  {\thesection}{1em}{}" "\n"
        r"  [\vspace{-0.5em}\textcolor{secblue}{\rule{\textwidth}{0.5pt}}]" "\n"
        r"\titleformat{\subsection}" "\n"
        r"  {\large\bfseries\color{subsecblue}}" "\n"
        r"  {\thesubsection}{1em}{}" "\n"
        r"\titleformat{\subsubsection}" "\n"
        r"  {\normalsize\bfseries\color{subsecblue!70!black}}" "\n"
        r"  {\thesubsubsection}{1em}{}" "\n"
        "\n"
        r"% ── hyperlink colours ─────────────────────────────────" "\n"
        r"\hypersetup{" "\n"
        r"  colorlinks  = true," "\n"
        r"  linkcolor   = secblue," "\n"
        r"  urlcolor    = subsecblue," "\n"
        r"  citecolor   = secblue!70!green!50!black," "\n"
        r"}" "\n"
    )

    title_page = (
        "\n"
        r"\begin{document}" "\n"
        "\n"
        r"% ── title page ────────────────────────────────────────" "\n"
        r"\begin{titlepage}" "\n"
        r"  \centering" "\n"
        r"  \vspace*{3cm}" "\n"
        r"  {\Large\textsc{Research Report}}\\" "\n"
        r"  \vspace{0.5cm}" "\n"
        r"  \textcolor{secblue}{\rule{0.8\textwidth}{1.5pt}}\\" "\n"
        r"  \vspace{1cm}" "\n"
        r"  {\LARGE\bfseries " + safe_title + r" \\}" "\n"
        r"  \vspace{1cm}" "\n"
        r"  \textcolor{secblue}{\rule{0.8\textwidth}{1.5pt}}\\" "\n"
        r"  \vspace{2cm}" "\n"
        r"  {\large " + author + r"}\\" "\n"
        r"  \vspace{0.5cm}" "\n"
        r"  {\large " + date_str + r"}\\" "\n"
        r"  \vfill" "\n"
        r"  {\small Generated with Research AI Agent}" "\n"
        r"\end{titlepage}" "\n"
        "\n"
        r"\tableofcontents" "\n"
        r"\newpage" "\n"
        "\n"
    )

    return preamble + title_page + body + "\n\n" + r"\end{document}" + "\n"


# ---------------------------------------------------------------------------
# LaTeX → Streamlit rendering
# ---------------------------------------------------------------------------

def _latex_inline_to_md(text: str) -> str:
    """Convert common LaTeX inline commands to Markdown equivalents."""
    text = re.sub(r"\\textbf\{([^}]*)\}", r"**\1**", text)
    text = re.sub(r"\\textit\{([^}]*)\}", r"*\1*", text)
    text = re.sub(r"\\underline\{([^}]*)\}", r"<u>\1</u>", text)
    text = re.sub(r"\\emph\{([^}]*)\}", r"*\1*", text)
    text = re.sub(r"\\url\{([^}]*)\}", r"[\1](\1)", text)
    text = re.sub(r"\\href\{([^}]*)\}\{([^}]*)\}", r"[\2](\1)", text)
    text = re.sub(r"\\cite\{[^}]*\}", "", text)
    text = re.sub(r"\\label\{[^}]*\}", "", text)
    text = re.sub(r"\\ref\{[^}]*\}", "", text)
    text = text.replace(r"\%", "%").replace(r"\&", "&").replace(r"\#", "#")
    text = text.replace(r"\textbackslash", "\\")
    return text


def render_latex_in_streamlit(latex_body: str) -> None:
    """Parse LaTeX body and render it using Streamlit primitives."""
    lines = latex_body.split("\n")
    buf: List[str] = []
    in_itemize = False
    in_enumerate = False
    enum_ctr = 0
    in_math_block = False
    math_buf: List[str] = []
    in_verbatim = False

    def flush():
        if buf:
            text = "\n".join(buf)
            text = _latex_inline_to_md(text)
            # Remove stray \\ line-breaks
            text = text.replace(r"\\", "  \n")
            if text.strip():
                st.markdown(text, unsafe_allow_html=True)
            buf.clear()

    for raw_line in lines:
        line = raw_line.rstrip()
        stripped = line.strip()

        # ── skip blanks ────────────────────────────────────────
        if not stripped:
            flush()
            continue

        # ── verbatim ───────────────────────────────────────────
        if r"\begin{verbatim}" in stripped:
            flush()
            in_verbatim = True
            continue
        if r"\end{verbatim}" in stripped:
            in_verbatim = False
            continue
        if in_verbatim:
            st.code(stripped, language=None)
            continue

        # ── display math ───────────────────────────────────────
        if stripped.startswith(r"\[") or stripped.startswith(r"\begin{equation"):
            flush()
            in_math_block = True
            rest = re.sub(r"^\\[\[\]]", "", stripped)
            rest = re.sub(r"\\begin\{equation\*?\}", "", rest)
            rest = re.sub(r"\\end\{equation\*?\}", "", rest)
            rest = rest.replace(r"\]", "")
            if rest.strip():
                math_buf.append(rest.strip())
            # Check if single-line
            if r"\]" in stripped or r"\end{equation" in stripped:
                in_math_block = False
                if math_buf:
                    st.latex("\n".join(math_buf))
                math_buf.clear()
            continue
        if in_math_block:
            if r"\]" in stripped or r"\end{equation" in stripped:
                rest = stripped.replace(r"\]", "")
                rest = re.sub(r"\\end\{equation\*?\}", "", rest)
                if rest.strip():
                    math_buf.append(rest.strip())
                in_math_block = False
                if math_buf:
                    st.latex("\n".join(math_buf))
                math_buf.clear()
            else:
                math_buf.append(stripped)
            continue

        # ── section headings ───────────────────────────────────
        m = re.match(r"\\section\*?\{(.+?)\}", stripped)
        if m:
            flush()
            st.markdown(f"## {m.group(1)}")
            continue
        m = re.match(r"\\subsection\*?\{(.+?)\}", stripped)
        if m:
            flush()
            st.markdown(f"### {m.group(1)}")
            continue
        m = re.match(r"\\subsubsection\*?\{(.+?)\}", stripped)
        if m:
            flush()
            st.markdown(f"#### {m.group(1)}")
            continue

        # ── list environments ──────────────────────────────────
        if r"\begin{itemize}" in stripped:
            flush()
            in_itemize = True
            continue
        if r"\end{itemize}" in stripped:
            flush()
            in_itemize = False
            continue
        if r"\begin{enumerate}" in stripped:
            flush()
            in_enumerate = True
            enum_ctr = 0
            continue
        if r"\end{enumerate}" in stripped:
            flush()
            in_enumerate = False
            continue

        # ── list items ─────────────────────────────────────────
        item_m = re.match(r"\\item\s*(.*)", stripped)
        if item_m:
            content = _latex_inline_to_md(item_m.group(1))
            if in_enumerate:
                enum_ctr += 1
                buf.append(f"{enum_ctr}. {content}")
            else:
                buf.append(f"- {content}")
            continue

        # ── bibliography ───────────────────────────────────────
        if r"\begin{thebibliography}" in stripped:
            flush()
            st.markdown("---")
            st.markdown("## References")
            continue
        if r"\end{thebibliography}" in stripped:
            flush()
            continue
        bib_m = re.match(r"\\bibitem\{[^}]*\}\s*(.*)", stripped)
        if bib_m:
            content = _latex_inline_to_md(bib_m.group(1))
            buf.append(f"- {content}")
            continue

        # ── page breaks ────────────────────────────────────────
        if stripped.startswith(r"\newpage") or stripped.startswith(r"\clearpage"):
            flush()
            st.divider()
            continue

        # ── skip preamble-like or meta commands ────────────────
        if re.match(
            r"\\(tableofcontents|maketitle|documentclass|usepackage|begin\{document\}"
            r"|end\{document\}|pagestyle|title|author|date)",
            stripped,
        ):
            continue

        # ── tabular (simplified: render raw) ───────────────────
        if r"\begin{tabular}" in stripped or r"\end{tabular}" in stripped:
            flush()
            continue
        if r"\hline" in stripped or r"\toprule" in stripped or r"\bottomrule" in stripped:
            continue

        # ── fallback: regular text ─────────────────────────────
        buf.append(stripped)

    flush()


# ---------------------------------------------------------------------------
# PDF generation
# ---------------------------------------------------------------------------

def compile_latex_to_pdf(full_document: str) -> Optional[bytes]:
    """Compile a full LaTeX document to PDF via pdflatex (if available)."""
    pdflatex = shutil.which("pdflatex")
    if not pdflatex:
        return None

    with tempfile.TemporaryDirectory() as tmpdir:
        tex_path = os.path.join(tmpdir, "report.tex")
        pdf_path = os.path.join(tmpdir, "report.pdf")
        with open(tex_path, "w", encoding="utf-8") as fh:
            fh.write(full_document)
        try:
            for _ in range(2):  # two passes for TOC
                subprocess.run(
                    [
                        pdflatex,
                        "-interaction=nonstopmode",
                        "-output-directory",
                        tmpdir,
                        tex_path,
                    ],
                    capture_output=True,
                    text=True,
                    timeout=90,
                )
            if os.path.exists(pdf_path):
                with open(pdf_path, "rb") as fh:
                    return fh.read()
        except Exception as exc:
            logger.error("pdflatex compilation failed: %s", exc)
    return None


def _latex_to_html(latex_body: str) -> str:
    """Convert LaTeX body to clean HTML for fallback PDF rendering."""
    html = latex_body

    # ── Sections ───────────────────────────────────────────────────
    html = re.sub(r"\\section\*?\{(.+?)\}", r"<h1>\1</h1>", html)
    html = re.sub(r"\\subsection\*?\{(.+?)\}", r"<h2>\1</h2>", html)
    html = re.sub(r"\\subsubsection\*?\{(.+?)\}", r"<h3>\1</h3>", html)

    # ── Inline formatting ──────────────────────────────────────────
    html = re.sub(r"\\textbf\{([^}]*)\}", r"<strong>\1</strong>", html)
    html = re.sub(r"\\textit\{([^}]*)\}", r"<em>\1</em>", html)
    html = re.sub(r"\\emph\{([^}]*)\}", r"<em>\1</em>", html)
    html = re.sub(r"\\underline\{([^}]*)\}", r"<u>\1</u>", html)
    html = re.sub(r"\\url\{([^}]*)\}", r'<a href="\1">\1</a>', html)
    html = re.sub(r"\\href\{([^}]*)\}\{([^}]*)\}", r'<a href="\1">\2</a>', html)
    # Leftover markdown bold/italic that slipped through
    html = re.sub(r"\*\*([^\*\n]+?)\*\*", r"<strong>\1</strong>", html)
    html = re.sub(r"(?<!\*)\*([^\*\n]+?)\*(?!\*)", r"<em>\1</em>", html)

    # ── Lists ──────────────────────────────────────────────────────
    html = re.sub(r"\\begin\{itemize\}", "<ul>", html)
    html = re.sub(r"\\end\{itemize\}", "</ul>", html)
    html = re.sub(r"\\begin\{enumerate\}", "<ol>", html)
    html = re.sub(r"\\end\{enumerate\}", "</ol>", html)
    html = re.sub(r"\\item\s*", "<li>", html)

    # ── Tables (basic conversion) ──────────────────────────────────
    # Convert \begin{table}...\end{table} + \begin{tabular}...\end{tabular}
    html = re.sub(r"\\begin\{table\}\[.*?\]", "", html)
    html = re.sub(r"\\end\{table\}", "", html)
    html = re.sub(r"\\centering", "", html)
    html = re.sub(r"\\caption\{([^}]*)\}", r"<p><strong>\1</strong></p>", html)

    def _convert_tabular(m: re.Match) -> str:
        """Turn a tabular environment into an HTML table."""
        inner = m.group(1)
        inner = re.sub(r"\\hline|\\toprule|\\midrule|\\bottomrule", "---ROW_SEP---", inner)
        rows = inner.split(r"\\")
        html_rows: list = []
        is_header = True
        for row in rows:
            row = row.replace("---ROW_SEP---", "").strip()
            if not row:
                continue
            cells = [c.strip() for c in row.split("&")]
            tag = "th" if is_header else "td"
            cells_html = "".join(f"<{tag}>{c}</{tag}>" for c in cells)
            html_rows.append(f"<tr>{cells_html}</tr>")
            is_header = False
        return "<table>" + "".join(html_rows) + "</table>"

    html = re.sub(
        r"\\begin\{tabular\}\{[^}]*\}(.*?)\\end\{tabular\}",
        _convert_tabular,
        html,
        flags=re.DOTALL,
    )

    # ── Bibliography ───────────────────────────────────────────────
    html = re.sub(
        r"\\begin\{thebibliography\}\{[^}]*\}",
        "<h2>References</h2><ol>",
        html,
    )
    html = re.sub(r"\\end\{thebibliography\}", "</ol>", html)
    html = re.sub(r"\\bibitem\{[^}]*\}\s*", "<li>", html)

    # ── Math (simplified — render as styled text) ──────────────────
    html = re.sub(
        r"\\\[(.+?)\\\]",
        r'<p style="text-align:center;font-family:serif;font-style:italic;'
        r'margin:15px 40px;padding:8px;background:#f8f8f8;border-radius:4px;">\1</p>',
        html,
        flags=re.DOTALL,
    )
    html = re.sub(
        r"\$(.+?)\$",
        r'<span style="font-family:serif;font-style:italic;">\1</span>',
        html,
    )

    # ── Cleanup remaining LaTeX commands ───────────────────────────
    html = re.sub(r"\\cite\{[^}]*\}", "", html)
    html = re.sub(r"\\label\{[^}]*\}", "", html)
    html = re.sub(r"\\ref\{[^}]*\}", "", html)
    html = re.sub(r"\\bigskip", "<br/>", html)
    html = re.sub(r"\\newpage", '<div style="page-break-after:always;"></div>', html)
    html = html.replace(r"\%", "%").replace(r"\&", "&").replace(r"\#", "#")
    html = html.replace("\\\\", "<br/>")
    # Remove stray em-dash separators
    html = re.sub(r"^\s*[—–-]{3,}\s*$", "", html, flags=re.MULTILINE)
    # Strip any remaining \command{...} or \command
    html = re.sub(r"\\[a-zA-Z]+\{[^}]*\}", "", html)
    html = re.sub(r"\\[a-zA-Z]+", "", html)

    # ── Wrap bare text lines in <p> tags ───────────────────────────
    out_lines: list = []
    for line in html.split("\n"):
        stripped = line.strip()
        if not stripped:
            continue
        # Don't wrap lines that already have block-level tags
        if re.match(r"<(h[1-6]|ul|ol|li|table|tr|th|td|div|p|br)", stripped):
            out_lines.append(stripped)
        elif stripped.startswith("</"):
            out_lines.append(stripped)
        else:
            out_lines.append(f"<p>{stripped}</p>")
    html = "\n".join(out_lines)

    return html


def latex_to_pdf_fallback(latex_body: str, title: str) -> Optional[bytes]:
    """Fallback: LaTeX body → HTML → PDF via xhtml2pdf."""
    try:
        from xhtml2pdf import pisa  # noqa: F811
    except ImportError:
        logger.warning("xhtml2pdf not installed — PDF fallback unavailable")
        return None

    html = _latex_to_html(latex_body)
    date_str = datetime.now().strftime("%B %d, %Y")
    safe_title = title.replace("&", "&amp;")

    full_html = f"""
    <html>
    <head>
        <style>
            @page {{
                size: A4;
                margin: 2.5cm;
                @frame footer_frame {{
                    -pdf-frame-content: footerContent;
                    bottom: 0.5cm;
                    margin-left: 1cm; margin-right: 1cm; height: 1cm;
                }}
            }}
            body {{
                font-family: Helvetica, Arial, sans-serif;
                font-size: 11pt; line-height: 1.6; color: #1a1a1a;
            }}
            h1 {{
                color: #1a3a5c; font-size: 20pt;
                border-bottom: 2px solid #1a3a5c;
                padding-bottom: 8px; margin-top: 30px; margin-bottom: 15px;
            }}
            h2 {{
                color: #1a3a5c; font-size: 15pt;
                border-left: 4px solid #2563eb;
                padding-left: 10px; margin-top: 25px; margin-bottom: 12px;
            }}
            h3 {{
                color: #2c3e50; font-size: 12pt;
                margin-top: 20px; margin-bottom: 10px;
            }}
            p  {{ margin-bottom: 8px; text-align: justify; }}
            a  {{ color: #2563eb; text-decoration: none; }}
            ul, ol {{ padding-left: 25px; margin-bottom: 12px; }}
            li {{ margin-bottom: 5px; }}
            table {{
                width: 100%; border-collapse: collapse;
                margin: 15px 0; font-size: 10pt;
            }}
            th {{
                background: #1a3a5c; color: #fff;
                padding: 8px 10px; text-align: left;
                font-weight: bold;
            }}
            td {{
                padding: 6px 10px; border: 1px solid #ddd;
            }}
            tr:nth-child(even) td {{ background: #f7f8fa; }}
            .title-page {{
                text-align: center;
                padding-top: 150px;
            }}
            .title-page h1 {{
                font-size: 24pt; border: none;
                color: #1a3a5c; line-height: 1.3;
                padding-bottom: 0;
            }}
            .title-line {{
                width: 60%; height: 2px;
                background: #2563eb;
                margin: 20px auto;
            }}
            .title-page p {{ font-size: 13pt; color: #555; }}
            .footer {{ text-align: center; color: #7f8c8d; font-size: 9pt; }}
        </style>
    </head>
    <body>
        <div id="footerContent" class="footer">
            Research AI Agent &mdash; {date_str}
        </div>
        <div class="title-page">
            <p style="font-size:14pt;color:#888;letter-spacing:2px;">RESEARCH REPORT</p>
            <div class="title-line"></div>
            <h1>{safe_title}</h1>
            <div class="title-line"></div>
            <p>Research AI Agent</p>
            <p>{date_str}</p>
        </div>
        <div style="page-break-after:always;"></div>
        {html}
    </body>
    </html>
    """

    pdf_buf = BytesIO()
    status = pisa.CreatePDF(full_html, dest=pdf_buf)
    if status.err:
        return None
    return pdf_buf.getvalue()


# ---------------------------------------------------------------------------
# Session state defaults
# ---------------------------------------------------------------------------
_DEFAULTS = {
    "current_report": None,
    "current_topic": "",
    "current_sources": [],
}
for key, val in _DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = val

# ---------------------------------------------------------------------------
# Sidebar — ONLY history (always visible)
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown("#### Research History")

    if st.button("+ New Research", type="primary", use_container_width=True):
        st.session_state.current_report = None
        st.session_state.current_topic = ""
        st.session_state.current_sources = []
        st.rerun()

    st.markdown("---")

    history = get_history()
    if not history:
        st.caption("No past research yet.")
    else:
        for row in history:
            r_id = row["id"]
            r_topic = row["topic"]
            r_time = row["created_at"]
            try:
                dt = datetime.strptime(r_time, "%Y-%m-%d %H:%M:%S")
                prefix = dt.strftime("%b %d")
            except Exception:
                prefix = ""

            col_lbl, col_del = st.columns([6, 1])
            with col_lbl:
                label = f"{prefix}  {r_topic[:32]}"
                if st.button(label, key=f"hist_{r_id}", use_container_width=True):
                    data = get_research_by_id(r_id)
                    if data:
                        st.session_state.current_topic = data["topic"]
                        st.session_state.current_report = data["latex_content"]
                        st.session_state.current_sources = json.loads(
                            data["sources"] or "[]"
                        )
                        st.rerun()
            with col_del:
                if st.button("X", key=f"del_{r_id}"):
                    delete_research(r_id)
                    if st.session_state.current_topic == r_topic:
                        st.session_state.current_report = None
                        st.session_state.current_topic = ""
                        st.session_state.current_sources = []
                    st.rerun()

# ---------------------------------------------------------------------------
# Main area
# ---------------------------------------------------------------------------
st.title("Research AI Agent")
st.caption("Powered by Mistral AI  —  LaTeX-formatted academic reports")

if st.session_state.current_report is None:
    # ── input form + config in main area ────────────────────────────────

    # API key
    api_key = os.getenv("MISTRAL_API_KEY")
    if not api_key:
        api_key = st.text_input(
            "Mistral API Key",
            type="password",
            help="Get yours at https://console.mistral.ai",
        )
    # Don't show anything if loaded from .env (clean UI)

    # Topic
    topic_input = st.text_area(
        "What would you like to research?",
        placeholder="e.g., Impact of large language models on scientific research ...",
        height=100,
    )

    # Config row — model + depth side-by-side
    cfg_col1, cfg_col2 = st.columns(2)
    with cfg_col1:
        model_choice = st.selectbox(
            "Model",
            [DEFAULT_MODEL, FALLBACK_MODEL, "mistral-large-latest"],
            index=0,
        )
    with cfg_col2:
        search_depth = st.selectbox(
            "Research depth",
            list(DEPTH_CONFIG.keys()),
            index=1,  # Standard
            help="Quick = fast overview · Standard = balanced · Deep = thorough",
        )

    st.markdown("")  # small spacer

    if st.button("Start Research", type="primary", use_container_width=True):
        if not api_key:
            st.error("Please provide your Mistral API key above.")
        elif not topic_input.strip():
            st.warning("Please enter a research topic.")
        else:
            cfg = DEPTH_CONFIG[search_depth]
            with st.status("Researching ...", expanded=True) as status:
                try:
                    client = Mistral(api_key=api_key)

                    # Step 1 — generate search queries
                    st.write("Generating search queries ...")
                    queries = generate_search_queries(
                        client, model_choice, topic_input
                    )
                    queries = queries[: cfg["queries"]]
                    for q in queries:
                        st.write(f"  - {q}")

                    # Step 2 — web search
                    st.write(f"Searching the web ({len(queries)} queries) ...")
                    results = multi_search(
                        queries, results_per_query=cfg["results_per_query"]
                    )
                    st.write(f"  Found {len(results)} unique sources")

                    context = ""
                    sources: List[Dict] = []
                    for r in results:
                        context += (
                            f"- {r.get('title','N/A')}: "
                            f"{r.get('body','N/A')} "
                            f"(Source: {r.get('href','N/A')})\n"
                        )
                        sources.append(
                            {
                                "title": r.get("title", "N/A"),
                                "body": r.get("body", "N/A"),
                                "href": r.get("href", "N/A"),
                            }
                        )

                    # Step 3 — generate LaTeX report
                    st.write("Generating LaTeX report ...")
                    report = generate_latex_report(
                        client, model_choice, topic_input, context, sources
                    )

                    if report:
                        save_research(
                            topic_input, report, sources, model_choice, queries
                        )
                        st.session_state.current_topic = topic_input
                        st.session_state.current_report = report
                        st.session_state.current_sources = sources
                        status.update(
                            label="Research complete!",
                            state="complete",
                            expanded=False,
                        )
                        st.rerun()
                    else:
                        status.update(label="Generation failed", state="error")
                        st.error(
                            "The model did not return a report. "
                            "Try a different model or topic."
                        )
                except Exception as exc:
                    status.update(label="Error", state="error")
                    st.error(f"Research failed: {exc}")
                    logger.exception("Research pipeline error")

else:
    # ── display report ──────────────────────────────────────────────────
    col_title, col_actions = st.columns([3, 2])
    with col_title:
        st.subheader(st.session_state.current_topic)
    with col_actions:
        c1, c2, c3 = st.columns(3)

        full_doc = build_full_latex_document(
            st.session_state.current_report,
            st.session_state.current_topic,
        )

        with c1:
            st.download_button(
                "Download .tex",
                data=full_doc.encode("utf-8"),
                file_name=f"{st.session_state.current_topic[:20].replace(' ','_')}.tex",
                mime="application/x-tex",
                use_container_width=True,
            )
        with c2:
            pdf_bytes = compile_latex_to_pdf(full_doc)
            if pdf_bytes is None:
                pdf_bytes = latex_to_pdf_fallback(
                    st.session_state.current_report,
                    st.session_state.current_topic,
                )
            if pdf_bytes:
                st.download_button(
                    "Download PDF",
                    data=pdf_bytes,
                    file_name=f"{st.session_state.current_topic[:20].replace(' ','_')}.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                )
        with c3:
            if st.button("New Research", key="new_top", use_container_width=True):
                st.session_state.current_report = None
                st.session_state.current_topic = ""
                st.session_state.current_sources = []
                st.rerun()

    st.divider()

    tab_report, tab_sources, tab_latex = st.tabs(
        ["Report", "Sources", "LaTeX Source"]
    )

    with tab_report:
        render_latex_in_streamlit(st.session_state.current_report)

    with tab_sources:
        srcs = st.session_state.current_sources
        if srcs:
            for i, src in enumerate(srcs, 1):
                with st.expander(
                    f"**{i}.** {src.get('title','N/A')}", expanded=False
                ):
                    st.write(src.get("body", "N/A"))
                    st.markdown(
                        f"[Open link]({src.get('href','#')})",
                        unsafe_allow_html=True,
                    )
        else:
            st.info("No sources recorded for this report.")

    with tab_latex:
        st.code(st.session_state.current_report, language="latex")
