"""Mistral AI interactions: query generation and LaTeX report generation."""

import re
import json
import logging
from typing import List, Optional, Dict

from mistralai import Mistral

from .latex import clean_latex_body

logger = logging.getLogger("ai_service.ai")


def generate_search_queries(
    api_key: str, model: str, topic: str
) -> List[str]:
    """Ask the LLM to produce short, keyword-style search queries."""
    client = Mistral(api_key=api_key)
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
                cleaned = []
                for q in queries[:6]:
                    q = str(q).strip()
                    words = q.split()
                    if len(words) > 10:
                        q = " ".join(words[:10])
                    cleaned.append(q)
                return cleaned
    except Exception as exc:
        logger.error("Query-generation error: %s", exc)

    short_topic = " ".join(topic.split()[:6])
    return [
        short_topic,
        f"{short_topic} recent research 2025",
        f"{short_topic} expert analysis",
        f"{short_topic} statistics benchmarks",
        f"{short_topic} applications case study",
    ]


def generate_latex_report(
    api_key: str,
    model: str,
    topic: str,
    context: str,
    sources: List[Dict],
) -> Optional[str]:
    """Generate a LaTeX-formatted research report body (no preamble)."""
    client = Mistral(api_key=api_key)

    bib_lines = ""
    for i, s in enumerate(sources, 1):
        safe_title = (
            s.get("title", "N/A")
            .replace("&", r"\&")
            .replace("%", r"\%")
            .replace("#", r"\#")
            .replace("_", r"\_")
        )
        safe_url = s.get("href", "")
        bib_lines += (
            f"  \\bibitem{{source{i}}} {safe_title}. "
            f"\\url{{{safe_url}}}\n"
        )

    system_prompt = r"""You are an expert academic researcher and LaTeX typesetter.
You produce research reports that compile perfectly with pdflatex.

═══════════════════════════════════════════════════════════
CRITICAL COMPILATION RULES — violating ANY of these will
cause the PDF to fail. Follow every single one.
═══════════════════════════════════════════════════════════

OUTPUT FORMAT:
• Output ONLY the LaTeX body content.
• Do NOT include \documentclass, \usepackage, \begin{document},
  \end{document}, \maketitle, \title{}, \author{}, \date{},
  \tableofcontents, or any preamble/postamble.
• Do NOT wrap output in ```latex``` code fences.

STRUCTURE:
• Use \section{Title}, \subsection{Title}, \subsubsection{Title}
  for headings. Do NOT number them manually — LaTeX numbers
  sections automatically.

TEXT FORMATTING:
• Bold: \textbf{text}    — NEVER use **text** (markdown bold)
• Italic: \textit{text}  — NEVER use *text* (markdown italic)
• NEVER mix markdown and LaTeX. This is the #1 cause of failures.
  If you catch yourself writing **, stop and use \textbf{} instead.

SPECIAL CHARACTERS — these MUST be escaped outside of math mode:
• & → \&     (except inside tabular column separators)
• % → \%
• # → \#
• _ → \_     (except inside \url{} or math mode)
• $ → \$     (except when opening/closing math mode)

LISTS:
• Bullet: \begin{itemize} ... \item Text ... \end{itemize}
• Numbered: \begin{enumerate} ... \item Text ... \end{enumerate}
• NO blank lines between \item entries.

MATH:
• Inline: $E = mc^2$
• Display: \[ F = ma \]
• For fractions: $\frac{a}{b}$
• For sums: $\sum_{i=1}^{n} x_i$

TABLES — this is critical, follow exactly:
• ALWAYS use the table + tabular environment:
    \begin{table}[h!]
    \centering
    \caption{Description of table}
    \begin{tabular}{l c c}
    \toprule
    Header 1 & Header 2 & Header 3 \\
    \midrule
    Value 1 & Value 2 & Value 3 \\
    Value 4 & Value 5 & Value 6 \\
    \bottomrule
    \end{tabular}
    \end{table}
• Use \toprule, \midrule, \bottomrule (from booktabs package)
  instead of \hline for professional appearance.
• NEVER write tables as plain text or with | separators.
• NEVER write tables as inline paragraphs with bold headers.

URLs:
• Always wrap URLs in \url{https://example.com}
• Never leave bare URLs in text.

REFERENCES:
• End with a bibliography using:
    \begin{thebibliography}{99}
    \bibitem{source1} Author. Title. \url{https://...}
    \end{thebibliography}
• Cite sources in the text with \cite{source1}, \cite{source2}, etc.

OTHER RULES:
• Do NOT use --- or em-dashes as section separators.
• Do NOT use \newpage except for major section breaks.
• Write at least 1500 words. Be thorough, data-driven, and analytical.
• Use an academic but accessible tone.
• Include concrete examples, statistics, and comparisons where possible.

SELF-CHECK before submitting:
1. Did I use \textbf{} and never **?
2. Did I escape &, %, #, _ outside math/tabular?
3. Are my tables in \begin{table}\begin{tabular} format?
4. Did I include \cite{} references and a \begin{thebibliography}?
5. Did I avoid any preamble commands?
"""

    user_prompt = (
        f"Write a comprehensive LaTeX research report on:\n\n"
        f"  {topic}\n\n"
        f"WEB SEARCH CONTEXT:\n{context}\n\n"
        f"SOURCES FOR BIBLIOGRAPHY:\n{bib_lines}\n\n"
        "Begin writing the LaTeX body now. Remember: NO preamble, "
        "NO markdown, proper tables with tabular environment, "
        "escape all special characters."
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
            # Strip code fences if present
            content = re.sub(r"^```(?:latex|tex)?\s*\n?", "", content)
            content = re.sub(r"\n?\s*```\s*$", "", content)
            return clean_latex_body(content)
    except Exception as exc:
        logger.error("Report generation error: %s", exc)
    return None
