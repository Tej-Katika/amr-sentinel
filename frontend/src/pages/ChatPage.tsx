import { useState } from "react";
import { agent } from "../services/api";
import type { AgentResponse } from "../types";

interface Turn {
  role: "user" | "assistant";
  text: string;
  meta?: AgentResponse;
}

export default function ChatPage() {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);

  async function send() {
    if (!input.trim() || busy) return;
    const q = input.trim();
    setInput("");
    setTurns((t) => [...t, { role: "user", text: q }]);
    setBusy(true);
    try {
      const resp = await agent.query(q);
      setTurns((t) => [...t, { role: "assistant", text: resp.recommendation, meta: resp }]);
    } catch (e) {
      setTurns((t) => [...t, { role: "assistant", text: "Error: agent service unavailable." }]);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-col h-full max-w-4xl mx-auto">
      <h1 className="text-2xl font-semibold mb-1">Stewardship Assistant</h1>
      <p className="text-sm text-gray-500 mb-4">
        Ask about empiric therapy, resistance trends, or de-escalation. Decision support only — clinical judgment overrides.
      </p>
      <div className="flex-1 overflow-y-auto space-y-3 pr-2">
        {turns.map((t, i) => (
          <div
            key={i}
            className={`max-w-[85%] rounded-lg p-3 text-sm ${
              t.role === "user"
                ? "bg-sentinel-700 text-white ml-auto"
                : "bg-white shadow"
            }`}
          >
            <div className="whitespace-pre-wrap">{t.text}</div>
            {t.meta && (
              <div className="mt-2 pt-2 border-t border-gray-200 text-xs text-gray-500">
                Confidence: {(t.meta.confidence_score * 100).toFixed(0)}% · Tools: {t.meta.tools_called.join(", ") || "none"}
              </div>
            )}
          </div>
        ))}
        {busy && <div className="text-gray-500 text-sm">Thinking…</div>}
      </div>
      <div className="mt-4 flex gap-2">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && send()}
          placeholder="e.g. What should I prescribe for an ICU patient with E. coli BSI?"
          className="flex-1 border rounded px-3 py-2 text-sm"
        />
        <button
          onClick={send}
          disabled={busy}
          className="bg-sentinel-700 text-white px-4 rounded text-sm disabled:opacity-50"
        >
          Send
        </button>
      </div>
    </div>
  );
}
