"""LaTeX document building and PDF compilation via pdflatex."""

import os
import re
import logging
import tempfile
import subprocess
import shutil
from datetime import datetime
from typing import Optional

logger = logging.getLogger("latex_service.latex")


# ---------------------------------------------------------------------------
# Post-processing — fix common AI-generated LaTeX mistakes
# ---------------------------------------------------------------------------

def clean_latex_body(body: str) -> str:
    """Aggressively clean AI-generated LaTeX body so it compiles with pdflatex."""

    # Strip code fences the AI sometimes wraps around the output
    body = re.sub(r"^```(?:latex|tex)?\s*\n?", "", body)
    body = re.sub(r"\n?\s*```\s*$", "", body)

    # Remove any preamble the AI may have included despite instructions
    body = re.sub(r"\\documentclass(\[.*?\])?\{.*?\}", "", body)
    body = re.sub(r"\\usepackage(\[.*?\])?\{.*?\}", "", body)
    body = re.sub(r"\\begin\{document\}", "", body)
    body = re.sub(r"\\end\{document\}", "", body)
    body = re.sub(r"\\maketitle", "", body)
    body = re.sub(r"\\title\{.*?\}", "", body)
    body = re.sub(r"\\author\{.*?\}", "", body)
    body = re.sub(r"\\date\{.*?\}", "", body)

    # Convert leftover markdown bold/italic to LaTeX commands
    body = re.sub(r"\*\*([^\*\n]+?)\*\*", r"\\textbf{\1}", body)
    body = re.sub(r"(?<!\\)(?<!\*)\*([^\*\n]+?)\*(?!\*)", r"\\textit{\1}", body)

    # Remove markdown horizontal rules
    body = re.sub(r"^\s*[—–]{1,3}\s*$", "", body, flags=re.MULTILINE)
    body = re.sub(r"^\s*-{3,}\s*$", "", body, flags=re.MULTILINE)

    # Strip leading numbers from section titles (e.g. "1. Introduction" -> "Introduction")
    body = re.sub(r"(\\(?:sub)*section\{)\d+\.?\s*", r"\1", body)

    # Escape bare % (but not already escaped \%)
    body = re.sub(r"(?<!\\)%", r"\\%", body)

    # Escape bare & outside tabular environments (common AI mistake)
    # We protect tabular blocks first, clean outside, then restore
    tabular_blocks = []
    def _save_tabular(m):
        tabular_blocks.append(m.group(0))
        return f"%%TABULAR_PLACEHOLDER_{len(tabular_blocks) - 1}%%"
    body = re.sub(
        r"\\begin\{(?:tabular|tabularx|longtable)\}.*?\\end\{(?:tabular|tabularx|longtable)\}",
        _save_tabular, body, flags=re.DOTALL
    )
    # Now escape bare & outside tabulars
    body = re.sub(r"(?<!\\)&(?!\s*\\)", r"\\&", body)
    # Restore tabular blocks
    for i, block in enumerate(tabular_blocks):
        body = body.replace(f"%%TABULAR_PLACEHOLDER_{i}%%", block)

    # Escape bare # and _  outside of math and commands
    body = re.sub(r"(?<!\\)#", r"\\#", body)

    # Remove blank lines inside itemize/enumerate (causes LaTeX errors)
    body = re.sub(
        r"(\\begin\{(?:itemize|enumerate)\})"
        r"(.*?)"
        r"(\\end\{(?:itemize|enumerate)\})",
        lambda m: m.group(1) + re.sub(r"\n\s*\n", "\n", m.group(2)) + m.group(3),
        body, flags=re.DOTALL,
    )

    # Fix common broken \textbf{**text} patterns from AI mixing markdown and LaTeX
    body = re.sub(r"\\textbf\{\*\*([^}]*)\}", r"\\textbf{\1}", body)
    body = re.sub(r"\*\*\\textbf\{([^}]*)\}", r"\\textbf{\1}", body)
    body = re.sub(r"\\textbf\{([^}]*)\*\*\}", r"\\textbf{\1}}", body)

    # Fix double-escaped braces
    body = body.replace("\\\\{", "\\{").replace("\\\\}", "\\}")

    return body


# ---------------------------------------------------------------------------
# Full document builder
# ---------------------------------------------------------------------------

def _truncate_title(title: str, max_words: int = 8) -> str:
    words = title.split()
    if len(words) <= max_words:
        return title
    return " ".join(words[:max_words]) + " \\ldots"


def _escape_title(title: str) -> str:
    """Escape special LaTeX characters in a title string."""
    for ch in ["&", "%", "#", "_", "~", "^"]:
        title = title.replace(ch, f"\\{ch}")
    return title


def build_full_latex_document(
    body: str, title: str, author: str = "Research AI Agent"
) -> str:
    """Wrap a LaTeX body in a complete, compilable document."""
    # Clean the body before wrapping
    body = clean_latex_body(body)

    safe_title = _escape_title(title)
    short_title = _truncate_title(safe_title)
    date_str = datetime.now().strftime("%B %d, %Y")

    preamble = (
        r"\documentclass[12pt,a4paper]{article}" "\n"
        r"\usepackage[utf8]{inputenc}" "\n"
        r"\usepackage[T1]{fontenc}" "\n"
        r"\usepackage{lmodern}" "\n"
        r"\usepackage[margin=2.5cm]{geometry}" "\n"
        r"\usepackage{parskip}" "\n"
        r"\usepackage{microtype}" "\n"
        r"\usepackage{amsmath,amssymb}" "\n"
        r"\usepackage{booktabs}" "\n"
        r"\usepackage{array}" "\n"
        r"\usepackage{longtable}" "\n"
        r"\usepackage{tabularx}" "\n"
        r"\usepackage{float}" "\n"
        r"\usepackage{enumitem}" "\n"
        r"\usepackage{graphicx}" "\n"
        r"\usepackage{xcolor}" "\n"
        r"\usepackage{fancyhdr}" "\n"
        r"\usepackage{titlesec}" "\n"
        r"\usepackage[breaklinks=true,hidelinks]{hyperref}" "\n"
        r"\usepackage{url}" "\n"
        r"\usepackage{csquotes}" "\n"
        "\n"
        r"\pagestyle{fancy}" "\n"
        r"\fancyhf{}" "\n"
        r"\setlength{\headheight}{15pt}" "\n"
        r"\fancyhead[L]{\small\textit{" + short_title + r"}}" "\n"
        r"\fancyhead[R]{\small\thepage}" "\n"
        r"\fancyfoot[C]{\footnotesize Research AI Agent}" "\n"
        r"\renewcommand{\headrulewidth}{0.4pt}" "\n"
        r"\renewcommand{\footrulewidth}{0.2pt}" "\n"
        "\n"
        r"\definecolor{secblue}{HTML}{1A3A5C}" "\n"
        r"\definecolor{subsecblue}{HTML}{2563EB}" "\n"
        r"\titleformat{\section}{\Large\bfseries\color{secblue}}"
        r"{\thesection}{1em}{}"
        r"[\vspace{-0.5em}\textcolor{secblue}{\rule{\textwidth}{0.5pt}}]" "\n"
        r"\titleformat{\subsection}{\large\bfseries\color{subsecblue}}"
        r"{\thesubsection}{1em}{}" "\n"
        r"\titleformat{\subsubsection}{\normalsize\bfseries\color{subsecblue!70!black}}"
        r"{\thesubsubsection}{1em}{}" "\n"
        "\n"
        r"\hypersetup{colorlinks=true,linkcolor=secblue,"
        r"urlcolor=subsecblue,citecolor=secblue!70!green!50!black}" "\n"
        "\n"
        # Tolerance settings to reduce overfull hboxes
        r"\tolerance=1000" "\n"
        r"\emergencystretch=3em" "\n"
        r"\hbadness=10000" "\n"
    )

    title_page = (
        "\n"
        r"\begin{document}" "\n"
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
        r"\newpage" "\n\n"
    )

    return preamble + title_page + body + "\n\n" + r"\end{document}" + "\n"


# ---------------------------------------------------------------------------
# PDF compilation — pdflatex only (no fallback)
# ---------------------------------------------------------------------------

def compile_latex_to_pdf(latex_body: str, title: str) -> Optional[bytes]:
    """Build a full LaTeX document and compile it to PDF bytes via pdflatex.

    Returns the PDF bytes on success, or None if compilation fails.
    pdflatex is required — there is no HTML fallback.
    """
    full_document = build_full_latex_document(latex_body, title)

    pdflatex = shutil.which("pdflatex")
    if not pdflatex:
        logger.error("pdflatex not found on PATH — cannot compile PDF")
        return None

    with tempfile.TemporaryDirectory() as tmpdir:
        tex_path = os.path.join(tmpdir, "report.tex")
        pdf_path = os.path.join(tmpdir, "report.pdf")
        log_path = os.path.join(tmpdir, "report.log")

        with open(tex_path, "w", encoding="utf-8") as fh:
            fh.write(full_document)

        try:
            # Run pdflatex twice for TOC and cross-references
            for pass_num in range(1, 3):
                result = subprocess.run(
                    [pdflatex, "-interaction=nonstopmode",
                     "-halt-on-error",
                     "-output-directory", tmpdir, tex_path],
                    capture_output=True, text=True, timeout=120,
                )
                logger.info("pdflatex pass %d exit code: %d", pass_num, result.returncode)

            if os.path.exists(pdf_path):
                with open(pdf_path, "rb") as fh:
                    pdf_bytes = fh.read()
                logger.info("PDF compiled successfully (%d bytes)", len(pdf_bytes))
                return pdf_bytes

            # PDF doesn't exist — log the error details
            if os.path.exists(log_path):
                with open(log_path, "r", encoding="utf-8", errors="replace") as fh:
                    log_content = fh.read()
                # Extract error lines from the log
                errors = re.findall(r"^!.*$", log_content, re.MULTILINE)
                if errors:
                    logger.error("pdflatex errors:\n%s", "\n".join(errors[:10]))
                else:
                    # Log the last 30 lines for context
                    last_lines = log_content.strip().split("\n")[-30:]
                    logger.error("pdflatex failed — last 30 lines of log:\n%s",
                                "\n".join(last_lines))
            else:
                logger.error("pdflatex failed and no log file was produced")
                if result.stdout:
                    logger.error("stdout: %s", result.stdout[-2000:])
                if result.stderr:
                    logger.error("stderr: %s", result.stderr[-2000:])

        except subprocess.TimeoutExpired:
            logger.error("pdflatex timed out after 120 seconds")
        except Exception as exc:
            logger.error("pdflatex execution error: %s", exc)

    return None
