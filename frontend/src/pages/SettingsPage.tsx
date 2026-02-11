import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";

const MODELS = ["mistral-medium-latest", "mistral-small-latest", "mistral-large-latest"];

export default function SettingsPage() {
  const nav = useNavigate();

  const [apiKey, setApiKey] = useState(() => localStorage.getItem("mistral_api_key") || "");
  const [model, setModel] = useState(() => localStorage.getItem("default_model") || MODELS[0]);
  const [saved, setSaved] = useState(false);

  const handleSave = () => {
    if (apiKey.trim()) {
      localStorage.setItem("mistral_api_key", apiKey.trim());
    } else {
      localStorage.removeItem("mistral_api_key");
    }
    localStorage.setItem("default_model", model);
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  const isKeySet = apiKey.trim().length > 0;

  return (
    <div className="min-h-screen flex flex-col">
      {/* Header */}
      <header className="flex items-center gap-4 px-6 py-4 border-b">
        <button
          onClick={() => nav("/")}
          className="flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground transition-colors"
        >
          <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="m12 19-7-7 7-7"/><path d="M19 12H5"/>
          </svg>
          Back to Dashboard
        </button>
      </header>

      {/* Content */}
      <div className="flex-1 flex justify-center px-6 py-10">
        <div className="w-full max-w-xl space-y-6">
          <div>
            <h1 className="text-2xl font-bold">Settings</h1>
            <p className="text-sm text-muted-foreground mt-1">Configure your AI provider and preferences</p>
          </div>

          {/* Provider Card */}
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle className="text-lg">AI Provider</CardTitle>
                <div className="flex items-center gap-2">
                  <span className={`w-2.5 h-2.5 rounded-full ${isKeySet ? "bg-green-500" : "bg-red-500"}`} />
                  <span className="text-xs text-muted-foreground">{isKeySet ? "Connected" : "Not configured"}</span>
                </div>
              </div>
            </CardHeader>
            <CardContent className="space-y-5">
              {/* Provider info */}
              <div className="flex items-center gap-4 p-3 rounded-lg border border-border">
                <div className="w-10 h-10 rounded-lg bg-accent flex items-center justify-center font-bold text-primary text-lg">
                  M
                </div>
                <div className="flex-1">
                  <p className="text-sm font-medium">Mistral AI</p>
                  <a
                    href="https://console.mistral.ai"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-xs text-primary hover:underline"
                  >
                    console.mistral.ai
                  </a>
                </div>
              </div>

              {/* API Key */}
              <div className="space-y-2">
                <label className="text-sm font-medium">API Key</label>
                <Input
                  type="password"
                  value={apiKey}
                  onChange={(e) => setApiKey(e.target.value)}
                  placeholder="sk-..."
                  onKeyDown={(e) => e.key === "Enter" && handleSave()}
                />
                <p className="text-xs text-muted-foreground">
                  Your key is stored locally in this browser. It is never sent to our servers — only directly to the Mistral API.
                </p>
              </div>

              {/* Default Model */}
              <div className="space-y-2">
                <label className="text-sm font-medium">Default Model</label>
                <select
                  value={model}
                  onChange={(e) => setModel(e.target.value)}
                  className="flex h-10 w-full rounded-md border border-input bg-card px-3 py-2 text-sm text-foreground"
                >
                  {MODELS.map((m) => (
                    <option key={m} value={m}>{m}</option>
                  ))}
                </select>
                <p className="text-xs text-muted-foreground">
                  This model will be pre-selected when you start a new research.
                </p>
              </div>

              {/* Save */}
              <div className="flex items-center gap-3">
                <Button onClick={handleSave} className="px-6">
                  Save Settings
                </Button>
                {saved && (
                  <span className="text-sm text-green-500 flex items-center gap-1">
                    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M20 6 9 17l-5-5"/>
                    </svg>
                    Saved
                  </span>
                )}
              </div>
            </CardContent>
          </Card>

          {/* Info Card */}
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">About</CardTitle>
            </CardHeader>
            <CardContent className="text-sm text-muted-foreground space-y-2">
              <p>Research AI Agent generates LaTeX-formatted academic reports using multi-step AI research.</p>
              <p>
                Your API key is used to call Mistral AI for query generation and report writing.
                Web search is performed via DuckDuckGo. PDF compilation uses TeX Live.
              </p>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
