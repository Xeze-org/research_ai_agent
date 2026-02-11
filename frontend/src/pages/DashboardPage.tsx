import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useResearch } from "@/hooks/useResearch";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent } from "@/components/ui/card";
import type { User } from "@/types";

const DEPTHS = ["Quick", "Standard", "Deep"];

interface Props {
  user: User;
  onLogout: () => Promise<void>;
}

export default function DashboardPage({ user, onLogout }: Props) {
  const { items, creating, create, remove } = useResearch();
  const nav = useNavigate();

  const [topic, setTopic] = useState("");
  const [model, setModel] = useState(() => localStorage.getItem("default_model") || "mistral-medium-latest");
  const [depth, setDepth] = useState("Standard");
  const [error, setError] = useState("");

  const apiKey = localStorage.getItem("mistral_api_key") || "";

  const handleCreate = async () => {
    setError("");
    if (!topic.trim()) {
      setError("Enter a research topic.");
      return;
    }
    if (!apiKey) {
      setError("Set your Mistral API key first.");
      nav("/settings");
      return;
    }
    try {
      const doc = await create({ topic, model, depth, api_key: apiKey });
      setTopic("");
      nav(`/report/${doc.id}`);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Research failed");
    }
  };

  return (
    <div className="flex h-screen">
      {/* Sidebar */}
      <aside className="w-72 shrink-0 border-r bg-card flex flex-col">
        <div className="p-4 border-b">
          <h2 className="font-semibold text-sm text-muted-foreground">Research History</h2>
        </div>
        <div className="flex-1 overflow-y-auto p-2 space-y-1">
          {items.length === 0 && (
            <p className="text-xs text-muted-foreground p-2">No research yet.</p>
          )}
          {items.map((r) => (
            <div key={r.id} className="flex items-center gap-1">
              <button
                onClick={() => nav(`/report/${r.id}`)}
                className="flex-1 text-left text-sm px-3 py-2 rounded-md hover:bg-accent truncate"
              >
                {r.topic.slice(0, 40)}
              </button>
              <button
                onClick={() => remove(r.id)}
                className="text-xs text-destructive hover:text-destructive/80 px-1"
              >
                X
              </button>
            </div>
          ))}
        </div>
        <div className="p-3 border-t flex items-center justify-between">
          <span className="text-sm text-muted-foreground truncate">{user.username}</span>
          <Button variant="ghost" size="sm" onClick={onLogout}>
            Logout
          </Button>
        </div>
      </aside>

      {/* Main */}
      <main className="flex-1 overflow-y-auto flex flex-col">
        {/* Top bar */}
        <header className="flex items-center justify-between px-8 py-4 border-b">
          <div>
            <h1 className="text-2xl font-bold">Research AI Agent</h1>
            <p className="text-sm text-muted-foreground">LaTeX-formatted academic reports</p>
          </div>
          <button
            onClick={() => nav("/settings")}
            className="flex items-center gap-2 px-3 py-2 rounded-lg border border-border hover:bg-accent transition-colors"
            title="Settings"
          >
            <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"/>
              <circle cx="12" cy="12" r="3"/>
            </svg>
            <span className="text-sm">Settings</span>
            {apiKey ? (
              <span className="w-2 h-2 rounded-full bg-green-500" />
            ) : (
              <span className="w-2 h-2 rounded-full bg-red-500" />
            )}
          </button>
        </header>

        {/* Research form */}
        <div className="flex-1 flex items-start justify-center p-8 pt-12">
          <Card className="w-full max-w-2xl">
            <CardContent className="p-6 space-y-5">
              {error && (
                <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">{error}</div>
              )}

              <div className="space-y-2">
                <label className="text-sm font-medium">Research Topic</label>
                <Textarea
                  value={topic}
                  onChange={(e) => setTopic(e.target.value)}
                  placeholder="e.g., Impact of large language models on scientific research..."
                  rows={4}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) handleCreate();
                  }}
                />
                <p className="text-xs text-muted-foreground">Press Ctrl+Enter to start</p>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <label className="text-sm font-medium">Model</label>
                  <select
                    value={model}
                    onChange={(e) => setModel(e.target.value)}
                    className="flex h-10 w-full rounded-md border border-input bg-card px-3 py-2 text-sm text-foreground"
                  >
                    <option value="mistral-medium-latest">mistral-medium-latest</option>
                    <option value="mistral-small-latest">mistral-small-latest</option>
                    <option value="mistral-large-latest">mistral-large-latest</option>
                  </select>
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium">Research Depth</label>
                  <select
                    value={depth}
                    onChange={(e) => setDepth(e.target.value)}
                    className="flex h-10 w-full rounded-md border border-input bg-card px-3 py-2 text-sm text-foreground"
                  >
                    {DEPTHS.map((d) => (
                      <option key={d} value={d}>{d}</option>
                    ))}
                  </select>
                </div>
              </div>

              <Button onClick={handleCreate} disabled={creating} className="w-full">
                {creating ? "Researching... (this may take a minute)" : "Start Research"}
              </Button>
            </CardContent>
          </Card>
        </div>
      </main>
    </div>
  );
}
