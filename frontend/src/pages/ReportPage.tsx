import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { researchApi } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { ReportView } from "@/components/research/ReportView";
import { SourcesList } from "@/components/research/SourcesList";
import type { Research, User } from "@/types";

interface Props {
  user: User;
  onLogout: () => Promise<void>;
}

export default function ReportPage({ user, onLogout }: Props) {
  const { id } = useParams<{ id: string }>();
  const nav = useNavigate();
  const [doc, setDoc] = useState<Research | null>(null);
  const [tab, setTab] = useState<"report" | "sources" | "latex">("report");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!id) return;
    researchApi.get(id).then(setDoc).catch(() => nav("/")).finally(() => setLoading(false));
  }, [id, nav]);

  if (loading) {
    return <div className="flex h-screen items-center justify-center text-muted-foreground">Loading report...</div>;
  }
  if (!doc) {
    return <div className="flex h-screen items-center justify-center text-muted-foreground">Report not found.</div>;
  }

  const tabs = [
    { key: "report" as const, label: "Report" },
    { key: "sources" as const, label: "Sources" },
    { key: "latex" as const, label: "LaTeX Source" },
  ];

  return (
    <div className="flex h-screen flex-col">
      {/* Top bar */}
      <header className="flex items-center justify-between border-b px-6 py-3">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="sm" onClick={() => nav("/")}>
            &larr; Back
          </Button>
          <h1 className="text-lg font-semibold truncate max-w-xl">{doc.topic}</h1>
        </div>
        <div className="flex items-center gap-2">
          {doc.tex_object_key && (
            <a href={researchApi.texUrl(doc.id)} download>
              <Button variant="outline" size="sm">Download .tex</Button>
            </a>
          )}
          {doc.pdf_object_key && (
            <a href={researchApi.pdfUrl(doc.id)} download>
              <Button variant="outline" size="sm">Download PDF</Button>
            </a>
          )}
          <span className="text-sm text-muted-foreground ml-4">{user.username}</span>
          <Button variant="ghost" size="sm" onClick={onLogout}>Logout</Button>
        </div>
      </header>

      {/* Tab bar */}
      <div className="flex border-b px-6">
        {tabs.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${
              tab === t.key
                ? "border-primary text-primary"
                : "border-transparent text-muted-foreground hover:text-foreground"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-6">
        {tab === "report" && <ReportView latex={doc.latex_content} />}
        {tab === "sources" && <SourcesList sources={doc.sources} />}
        {tab === "latex" && (
          <pre className="whitespace-pre-wrap rounded-lg bg-muted p-4 text-sm font-mono overflow-x-auto">
            {doc.latex_content}
          </pre>
        )}
      </div>
    </div>
  );
}
