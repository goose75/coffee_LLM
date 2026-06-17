"use client";

import { useState, useRef, useEffect, useCallback } from "react";



interface Message {
  role: "user" | "assistant" | "system";
  content: string;
  streaming?: boolean;
}

const SUGGESTIONS = [
  "What's a good Ethiopian filter coffee?",
  "Find me an espresso under £15 for 250g",
  "What's the difference between washed and natural?",
  "Which coffees suit both espresso and filter?",
  "What should I try if I liked fruity coffees?",
];

function RenderMessage({ text }: { text: string }) {
  const parts = text.split(/(\[([^\]]+)\]\(([^)]+)\))/g);
  const rendered: React.ReactNode[] = [];
  let i = 0;
  while (i < parts.length) {
    const part = parts[i];
    if (part.startsWith("[") && i + 2 < parts.length) {
      i++;
      const label = parts[i]; i++;
      const href = parts[i]; i++;
      rendered.push(
        <a key={i} href={href}
          className="underline decoration-dotted underline-offset-2"
          style={{ color: "var(--accent)" }}>{label}</a>
      );
    } else {
      const lines = part.split("\n");
      lines.forEach((line, li) => {
        if (line === "") {
          rendered.push(<br key={`${i}-${li}-br`} />);
        } else {
          const boldParts = line.split(/(\*\*[^*]+\*\*)/g);
          boldParts.forEach((bp, bi) => {
            if (bp.startsWith("**") && bp.endsWith("**")) {
              rendered.push(<strong key={`${i}-${li}-${bi}`}>{bp.slice(2, -2)}</strong>);
            } else {
              rendered.push(<span key={`${i}-${li}-${bi}`}>{bp}</span>);
            }
          });
          if (li < lines.length - 1) rendered.push(<br key={`${i}-${li}-nlbr`} />);
        }
      });
      i++;
    }
  }
  return <span className="leading-relaxed">{rendered}</span>;
}

export default function AssistantPanel() {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [sessionId] = useState(() => crypto.randomUUID());
  const [error, setError] = useState<string | null>(null);
  const [hasInteracted, setHasInteracted] = useState(false);

  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    if (open) setTimeout(() => inputRef.current?.focus(), 200);
  }, [open]);

  // Lock body scroll when sheet is open
  useEffect(() => {
    if (open) {
      document.body.style.overflow = "hidden";
    } else {
      document.body.style.overflow = "";
    }
    return () => { document.body.style.overflow = ""; };
  }, [open]);

  const send = useCallback(async (text: string) => {
    if (!text.trim() || streaming) return;
    const userMsg = text.trim();
    setInput("");
    setError(null);
    setHasInteracted(true);
    setMessages(prev => [...prev, { role: "user", content: userMsg }]);
    setMessages(prev => [...prev, { role: "assistant", content: "", streaming: true }]);
    setStreaming(true);

    const ctrl = new AbortController();
    abortRef.current = ctrl;

    try {
      const historyForApi = messages
        .filter(m => m.role !== "system")
        .map(m => ({ role: m.role as "user" | "assistant", content: m.content }));

      const res = await fetch(`/api/assistant/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: userMsg, session_id: sessionId, history: historyForApi }),
        signal: ctrl.signal,
      });

      if (!res.ok) throw new Error(`API error ${res.status}`);
      if (!res.body) throw new Error("No response body");

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let accumulated = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        const raw = decoder.decode(value, { stream: true });
        for (const line of raw.split("\n")) {
          if (!line.startsWith("data: ")) continue;
          const data = line.slice(6).trim();
          if (data === "[DONE]") break;
          try {
            const parsed = JSON.parse(data);
            if (parsed.error) { setError(parsed.error); break; }
            if (parsed.text) {
              accumulated += parsed.text;
              const chunk = accumulated;
              setMessages(prev => {
                const updated = [...prev];
                const last = updated[updated.length - 1];
                if (last?.streaming) updated[updated.length - 1] = { ...last, content: chunk };
                return updated;
              });
            }
          } catch {}
        }
      }
      setMessages(prev => {
        const updated = [...prev];
        const last = updated[updated.length - 1];
        if (last?.streaming) updated[updated.length - 1] = { ...last, streaming: false };
        return updated;
      });
    } catch (err: any) {
      if (err.name !== "AbortError") setError("Couldn't reach the assistant. Try again.");
      setMessages(prev => {
        const updated = [...prev];
        const last = updated[updated.length - 1];
        if (last?.streaming) updated[updated.length - 1] = { ...last, streaming: false };
        return updated;
      });
    } finally {
      setStreaming(false);
    }
  }, [messages, streaming, sessionId]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send(input);
    }
  };

  const stopStreaming = () => {
    abortRef.current?.abort();
    setStreaming(false);
    setMessages(prev => {
      const updated = [...prev];
      const last = updated[updated.length - 1];
      if (last?.streaming) updated[updated.length - 1] = { ...last, streaming: false };
      return updated;
    });
  };

  // ── Trigger button — floats just above the tab bar ────────────────────────
  // Positioned at bottom: calc(tab-h + safe-bottom + 12px) so it clears the nav
  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        aria-label="Open coffee assistant"
        className="fixed right-4 z-40 flex items-center gap-2 px-4 py-2.5 rounded-full shadow-lg press-active"
        style={{
          bottom: "calc(var(--tab-h) + var(--safe-bottom) + 12px)",
          backgroundColor: "var(--accent)",
          color: "#fff",
          boxShadow: "0 4px 20px rgba(181,136,42,0.35)",
        }}
      >
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
          <path d="M17 8h1a4 4 0 0 1 0 8h-1" />
          <path d="M3 8h14v9a4 4 0 0 1-4 4H7a4 4 0 0 1-4-4Z" />
          <line x1="6" y1="2" x2="6" y2="4" />
          <line x1="10" y1="2" x2="10" y2="4" />
          <line x1="14" y1="2" x2="14" y2="4" />
        </svg>
        <span className="text-[13px] font-medium">Ask</span>
      </button>
    );
  }

  // ── Open state — full-screen bottom sheet on mobile ───────────────────────
  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 z-40 bg-black/40"
        style={{ backdropFilter: "blur(4px)" }}
        onClick={() => setOpen(false)}
      />

      {/* Bottom sheet */}
      <div
        className="fixed left-0 right-0 z-50 flex flex-col slide-up"
        style={{
          bottom: 0,
          // On larger screens: float as a panel; on mobile: full-height sheet
          top: "10vh",
          maxWidth: 480,
          margin: "0 auto",
          borderRadius: "20px 20px 0 0",
          backgroundColor: "var(--surface)",
          border: "1px solid var(--border-light)",
          borderBottom: "none",
          boxShadow: "0 -8px 40px rgba(0,0,0,0.18)",
        }}
      >
        {/* Drag handle */}
        <div className="flex justify-center pt-3 pb-1 flex-shrink-0">
          <div className="w-10 h-1 rounded-full" style={{ backgroundColor: "var(--border)" }} />
        </div>

        {/* Header */}
        <div
          className="flex items-center justify-between px-4 py-3 flex-shrink-0"
          style={{ borderBottom: "1px solid var(--border-light)" }}
        >
          <div className="flex items-center gap-2.5">
            <div
              className="w-7 h-7 rounded-full flex items-center justify-center"
              style={{ backgroundColor: "var(--accent-dim)" }}
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--accent)" strokeWidth="2" strokeLinecap="round">
                <path d="M17 8h1a4 4 0 0 1 0 8h-1" />
                <path d="M3 8h14v9a4 4 0 0 1-4 4H7a4 4 0 0 1-4-4Z" />
              </svg>
            </div>
            <div>
              <div className="text-sm font-medium" style={{ color: "var(--text)" }}>Coffee assistant</div>
              <div className="text-[10px]" style={{ color: "var(--text-faint)" }}>Live catalogue · updated daily</div>
            </div>
          </div>
          <button
            onClick={() => setOpen(false)}
            className="w-8 h-8 flex items-center justify-center rounded-full press-active"
            style={{ backgroundColor: "var(--bg-warm)", color: "var(--text-faint)" }}
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
              <path d="M18 6 6 18M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Disclosure */}
        <div
          className="px-4 py-2 text-[10px] flex items-start gap-1.5 flex-shrink-0"
          style={{ backgroundColor: "var(--accent-dim)", borderBottom: "1px solid var(--border-light)", color: "var(--accent)" }}
        >
          <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="mt-0.5 flex-shrink-0">
            <circle cx="12" cy="12" r="10" /><path d="M12 16v-4M12 8h.01" />
          </svg>
          <span>Answers grounded in live platform data. Prices cited from verified daily records.</span>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4" style={{ WebkitOverflowScrolling: "touch" }}>
          {!hasInteracted && (
            <div>
              <p className="text-xs mb-4 leading-relaxed" style={{ color: "var(--text-muted)" }}>
                Ask me anything about our coffee catalogue — recommendations, comparisons, prices, and brewing.
              </p>
              <div className="space-y-2">
                {SUGGESTIONS.map(s => (
                  <button key={s} onClick={() => send(s)}
                    className="w-full text-left text-xs px-3 py-2.5 rounded-xl press-active"
                    style={{ backgroundColor: "var(--bg-warm)", border: "1px solid var(--border-light)", color: "var(--text-muted)" }}>
                    {s}
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((msg, i) => (
            <div key={i} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
              {msg.role === "assistant" && (
                <div className="w-5 h-5 rounded-full flex-shrink-0 flex items-center justify-center mr-2 mt-0.5"
                  style={{ backgroundColor: "var(--accent-dim)" }}>
                  <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="var(--accent)" strokeWidth="2.5">
                    <path d="M17 8h1a4 4 0 0 1 0 8h-1" /><path d="M3 8h14v9a4 4 0 0 1-4 4H7a4 4 0 0 1-4-4Z" />
                  </svg>
                </div>
              )}
              <div
                className="max-w-[85%] rounded-2xl px-3.5 py-2.5 text-[13px]"
                style={msg.role === "user" ? {
                  backgroundColor: "var(--accent)", color: "#fff", borderBottomRightRadius: 4,
                } : {
                  backgroundColor: "var(--bg-warm)", color: "var(--text)",
                  border: "1px solid var(--border-light)", borderBottomLeftRadius: 4,
                }}
              >
                {msg.role === "assistant" ? (
                  <>
                    <RenderMessage text={msg.content || (msg.streaming ? "" : "…")} />
                    {msg.streaming && msg.content === "" && (
                      <span className="inline-flex gap-1">
                        {[0, 150, 300].map(d => (
                          <span key={d} className="w-1 h-1 rounded-full animate-bounce"
                            style={{ backgroundColor: "var(--text-faint)", animationDelay: `${d}ms` }} />
                        ))}
                      </span>
                    )}
                    {msg.streaming && msg.content.length > 0 && (
                      <span className="inline-block w-0.5 h-3 ml-0.5 align-middle animate-pulse"
                        style={{ backgroundColor: "var(--accent)" }} />
                    )}
                  </>
                ) : <span>{msg.content}</span>}
              </div>
            </div>
          ))}

          {error && (
            <div className="text-xs px-3 py-2 rounded-xl"
              style={{ backgroundColor: "#ff000015", color: "#f87171", border: "1px solid #ef444430" }}>
              {error}
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        {/* Input */}
        <div
          className="px-3 pb-4 pt-2 flex-shrink-0"
          style={{
            borderTop: "1px solid var(--border-light)",
            paddingBottom: "calc(0.75rem + var(--safe-bottom))",
          }}
        >
          <div
            className="flex items-end gap-2 rounded-2xl px-3 py-2"
            style={{ backgroundColor: "var(--bg-warm)", border: "1px solid var(--border)" }}
          >
            <textarea
              ref={inputRef}
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask about coffees, prices, brewing…"
              rows={1}
              disabled={streaming}
              className="flex-1 resize-none text-sm bg-transparent outline-none leading-5 max-h-24"
              style={{ color: "var(--text)", caretColor: "var(--accent)" }}
            />
            {streaming ? (
              <button onClick={stopStreaming}
                className="flex-shrink-0 w-8 h-8 flex items-center justify-center rounded-xl press-active"
                style={{ backgroundColor: "var(--border)", color: "var(--text-muted)" }}>
                <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor"><rect x="4" y="4" width="16" height="16" rx="2" /></svg>
              </button>
            ) : (
              <button onClick={() => send(input)} disabled={!input.trim()}
                className="flex-shrink-0 w-8 h-8 flex items-center justify-center rounded-xl press-active disabled:opacity-30"
                style={{ backgroundColor: "var(--accent)", color: "#fff" }}>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
                  <path d="M5 12h14M12 5l7 7-7 7" />
                </svg>
              </button>
            )}
          </div>
        </div>
      </div>
    </>
  );
}
