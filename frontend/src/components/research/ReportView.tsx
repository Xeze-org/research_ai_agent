import { useMemo } from "react";
import katex from "katex";
import DOMPurify from "dompurify";

interface Props {
  latex: string;
}

/**
 * Converts LaTeX body content to HTML for browser display.
 * Uses KaTeX for math, regex for structural elements.
 */
function latexToHtml(body: string): string {
  let html = body;

  // Render display math \[ ... \]
  html = html.replace(/\\\[([\s\S]*?)\\\]/g, (_m, inner) => {
    try {
      return `<div class="my-4 overflow-x-auto">${katex.renderToString(inner.trim(), { displayMode: true, throwOnError: false })}</div>`;
    } catch {
      return `<div class="my-4 italic text-muted-foreground">${inner.trim()}</div>`;
    }
  });

  // Render inline math $...$
  html = html.replace(/\$([^\$\n]+?)\$/g, (_m, inner) => {
    try {
      return katex.renderToString(inner.trim(), { displayMode: false, throwOnError: false });
    } catch {
      return `<em>${inner.trim()}</em>`;
    }
  });

  // Sections
  html = html.replace(/\\section\*?\{(.+?)\}/g, '<h2 class="text-2xl font-bold mt-8 mb-3 text-[hsl(var(--primary))]">$1</h2>');
  html = html.replace(/\\subsection\*?\{(.+?)\}/g, '<h3 class="text-xl font-semibold mt-6 mb-2">$1</h3>');
  html = html.replace(/\\subsubsection\*?\{(.+?)\}/g, '<h4 class="text-lg font-medium mt-4 mb-1">$1</h4>');

  // Text formatting
  html = html.replace(/\\textbf\{([^}]*)\}/g, "<strong>$1</strong>");
  html = html.replace(/\\textit\{([^}]*)\}/g, "<em>$1</em>");
  html = html.replace(/\\emph\{([^}]*)\}/g, "<em>$1</em>");
  html = html.replace(/\\underline\{([^}]*)\}/g, "<u>$1</u>");

  // Links
  html = html.replace(/\\url\{([^}]*)\}/g, '<a href="$1" target="_blank" rel="noopener" class="text-[hsl(var(--primary))] hover:underline">$1</a>');
  html = html.replace(/\\href\{([^}]*)\}\{([^}]*)\}/g, '<a href="$1" target="_blank" rel="noopener" class="text-[hsl(var(--primary))] hover:underline">$2</a>');

  // Lists
  html = html.replace(/\\begin\{itemize\}/g, '<ul class="list-disc pl-6 my-2 space-y-1">');
  html = html.replace(/\\end\{itemize\}/g, "</ul>");
  html = html.replace(/\\begin\{enumerate\}/g, '<ol class="list-decimal pl-6 my-2 space-y-1">');
  html = html.replace(/\\end\{enumerate\}/g, "</ol>");
  html = html.replace(/\\item\s*/g, "<li>");

  // Bibliography
  html = html.replace(/\\begin\{thebibliography\}\{[^}]*\}/g, '<h2 class="text-2xl font-bold mt-8 mb-3">References</h2><ol class="list-decimal pl-6 space-y-2">');
  html = html.replace(/\\end\{thebibliography\}/g, "</ol>");
  html = html.replace(/\\bibitem\{[^}]*\}\s*/g, '<li class="text-sm">');

  // Table handling: basic pass-through
  html = html.replace(/\\begin\{table\}(\[.*?\])?/g, '<div class="my-4 overflow-x-auto">');
  html = html.replace(/\\end\{table\}/g, "</div>");
  html = html.replace(/\\begin\{tabular\}\{[^}]*\}/g, '<table class="w-full border-collapse border text-sm">');
  html = html.replace(/\\end\{tabular\}/g, "</table>");
  html = html.replace(/\\hline/g, "");
  html = html.replace(/\\caption\{([^}]*)\}/g, '<p class="text-sm text-muted-foreground italic mt-1">$1</p>');
  html = html.replace(/\\centering/g, "");
  html = html.replace(/\\label\{[^}]*\}/g, "");

  // Table rows: & separators, \\ row ends
  const tableRegex = /<table[^>]*>([\s\S]*?)<\/table>/g;
  html = html.replace(tableRegex, (_m, inner: string) => {
    const rows = inner.split("\\\\").filter((r: string) => r.trim());
    const rowsHtml = rows.map((row: string, i: number) => {
      const cells = row.split("&").map((c: string) => c.trim());
      const tag = i === 0 ? "th" : "td";
      const cellClass = i === 0
        ? 'class="border px-3 py-2 bg-muted font-medium text-left"'
        : 'class="border px-3 py-2"';
      return `<tr>${cells.map((c: string) => `<${tag} ${cellClass}>${c}</${tag}>`).join("")}</tr>`;
    }).join("");
    return `<table class="w-full border-collapse border text-sm">${rowsHtml}</table>`;
  });

  // Clean remaining LaTeX commands
  html = html.replace(/\\cite\{[^}]*\}/g, "");
  html = html.replace(/\\newpage/g, "<hr class='my-6'/>");
  html = html.replace(/\\bigskip/g, "<br/>");
  html = html.replace(/\\\\/g, "<br/>");
  html = html.replace(/\\%/g, "%");
  html = html.replace(/\\&/g, "&amp;");
  html = html.replace(/\\#/g, "#");
  // Remove any remaining \command{...} or \command
  html = html.replace(/\\[a-zA-Z]+\{[^}]*\}/g, "");
  html = html.replace(/\\[a-zA-Z]+/g, "");

  // Wrap paragraphs: lines with content not already in tags
  html = html.replace(/\n\n+/g, "</p><p class='my-2 leading-relaxed'>");
  html = `<p class='my-2 leading-relaxed'>${html}</p>`;

  return html;
}

export function ReportView({ latex }: Props) {
  const html = useMemo(() => {
    const raw = latexToHtml(latex);
    return DOMPurify.sanitize(raw, { ADD_TAGS: ["span", "annotation"], ADD_ATTR: ["style", "aria-hidden"] });
  }, [latex]);

  return (
    <article
      className="prose prose-sm max-w-none dark:prose-invert"
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}
