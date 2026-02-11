import type { Source } from "@/types";

interface Props {
  sources: Source[];
}

export function SourcesList({ sources }: Props) {
  if (!sources || sources.length === 0) {
    return <p className="text-muted-foreground">No sources found.</p>;
  }

  return (
    <div className="space-y-3 max-w-3xl">
      <h2 className="text-lg font-semibold mb-2">Sources ({sources.length})</h2>
      {sources.map((s, i) => (
        <details key={i} className="group border rounded-lg">
          <summary className="flex items-center justify-between cursor-pointer px-4 py-3 hover:bg-muted/50">
            <span className="text-sm font-medium">
              [{i + 1}] {s.title}
            </span>
            <svg
              className="h-4 w-4 shrink-0 text-muted-foreground transition-transform group-open:rotate-180"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </summary>
          <div className="px-4 pb-3 text-sm">
            <p className="text-muted-foreground mb-2">{s.body}</p>
            {s.href && (
              <a
                href={s.href}
                target="_blank"
                rel="noopener noreferrer"
                className="text-primary hover:underline text-xs break-all"
              >
                {s.href}
              </a>
            )}
          </div>
        </details>
      ))}
    </div>
  );
}
