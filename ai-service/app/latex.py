"""LaTeX post-processing used by the AI report generator.

This runs BEFORE the body is sent to the latex-service for compilation.
It fixes common mistakes the LLM makes so that pdflatex can compile cleanly.
"""

import re


def clean_latex_body(body: str) -> str:
    """Aggressively clean AI-generated LaTeX body so it compiles with pdflatex."""

    # ── Strip code fences ──────────────────────────────────────
    body = re.sub(r"^```(?:latex|tex)?\s*\n?", "", body)
    body = re.sub(r"\n?\s*```\s*$", "", body)

    # ── Remove preamble the AI may have included ───────────────
    body = re.sub(r"\\documentclass(\[.*?\])?\{.*?\}\s*\n?", "", body)
    body = re.sub(r"\\usepackage(\[.*?\])?\{.*?\}\s*\n?", "", body)
    body = re.sub(r"\\begin\{document\}\s*\n?", "", body)
    body = re.sub(r"\\end\{document\}\s*\n?", "", body)
    body = re.sub(r"\\maketitle\s*\n?", "", body)
    body = re.sub(r"\\title\{[^}]*\}\s*\n?", "", body)
    body = re.sub(r"\\author\{[^}]*\}\s*\n?", "", body)
    body = re.sub(r"\\date\{[^}]*\}\s*\n?", "", body)
    body = re.sub(r"\\tableofcontents\s*\n?", "", body)
    body = re.sub(r"\\newpage\s*\n?", "", body, count=1)  # only first

    # ── Convert leftover markdown bold/italic to LaTeX ─────────
    # Handle **bold** -> \textbf{bold}
    body = re.sub(r"\*\*([^\*\n]+?)\*\*", r"\\textbf{\1}", body)
    # Handle *italic* -> \textit{italic}
    body = re.sub(r"(?<!\\)(?<!\*)\*([^\*\n]+?)\*(?!\*)", r"\\textit{\1}", body)

    # Fix broken mixed patterns like \textbf{**text} or **\textbf{text}
    body = re.sub(r"\\textbf\{\*\*([^}]*)\}", r"\\textbf{\1}", body)
    body = re.sub(r"\*\*\\textbf\{([^}]*)\}", r"\\textbf{\1}", body)
    body = re.sub(r"\\textbf\{([^}]*)\*\*\}", r"\\textbf{\1}}", body)

    # ── Remove markdown horizontal rules ───────────────────────
    body = re.sub(r"^\s*[—–]{1,3}\s*$", "", body, flags=re.MULTILINE)
    body = re.sub(r"^\s*-{3,}\s*$", "", body, flags=re.MULTILINE)
    body = re.sub(r"^\s*\*{3,}\s*$", "", body, flags=re.MULTILINE)

    # ── Strip leading numbers from section titles ──────────────
    body = re.sub(r"(\\(?:sub)*section\{)\d+\.?\s*", r"\1", body)

    # ── Escape bare special characters ─────────────────────────
    # Protect tabular/table blocks from & escaping
    tabular_blocks: list[str] = []
    def _save_tabular(m: re.Match) -> str:
        tabular_blocks.append(m.group(0))
        return f"%%TABULAR_PLACEHOLDER_{len(tabular_blocks) - 1}%%"
    body = re.sub(
        r"\\begin\{(?:tabular|tabularx|longtable)\}.*?\\end\{(?:tabular|tabularx|longtable)\}",
        _save_tabular, body, flags=re.DOTALL
    )
    # Escape bare & outside tabulars (but not \&)
    body = re.sub(r"(?<!\\)&", r"\\&", body)
    # Restore tabulars
    for i, block in enumerate(tabular_blocks):
        body = body.replace(f"%%TABULAR_PLACEHOLDER_{i}%%", block)

    # Escape bare % (but not \%)
    body = re.sub(r"(?<!\\)%", r"\\%", body)
    # Escape bare # (but not \#)
    body = re.sub(r"(?<!\\)#", r"\\#", body)

    # ── Fix blank lines inside list environments ───────────────
    body = re.sub(
        r"(\\begin\{(?:itemize|enumerate)\})"
        r"(.*?)"
        r"(\\end\{(?:itemize|enumerate)\})",
        lambda m: m.group(1) + re.sub(r"\n\s*\n", "\n", m.group(2)) + m.group(3),
        body, flags=re.DOTALL,
    )

    # ── Fix common URL issues ──────────────────────────────────
    # Escape underscores inside \url{} — they break pdflatex
    # Actually \url handles _ fine, but bare URLs without \url don't
    # Wrap bare http(s) URLs in \url{} if not already wrapped
    body = re.sub(
        r"(?<!\\url\{)(?<!\\href\{)(https?://[^\s\}]+)",
        r"\\url{\1}",
        body,
    )

    return body
