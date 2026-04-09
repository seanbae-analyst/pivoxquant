"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { MessageSquare, Send, Sparkles, Bot } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";

/* ── types ── */

interface Message {
  role: "user" | "assistant";
  content: string;
}

/* ── suggested prompts ── */

const SUGGESTIONS = [
  "Analyze my portfolio risk",
  "What should I buy?",
  "Explain my worst performer",
  "Give me a morning summary",
] as const;

/* ── page ── */

export default function AIChatPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  /* auto-scroll on new message */
  useEffect(() => {
    scrollRef.current?.scrollTo({
      top: scrollRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [messages, loading]);

  /* abort controller for SSE cleanup */
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    return () => { abortRef.current?.abort(); };
  }, []);

  /* send message */
  const send = useCallback(
    async (text: string) => {
      const trimmed = text.trim();
      if (!trimmed || loading) return;

      setInput("");
      setMessages((prev) => [...prev, { role: "user", content: trimmed }]);
      setLoading(true);

      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;

      try {
        const res = await fetch("/api/ai/chat", {
          method: "POST",
          credentials: "include",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ message: trimmed }),
          signal: controller.signal,
        });

        if (!res.ok) throw new Error(res.statusText);

        const reader = res.body?.getReader();
        const decoder = new TextDecoder();
        let fullText = "";
        let streamDone = false;

        // Add placeholder assistant message
        setMessages((prev) => [...prev, { role: "assistant", content: "" }]);

        if (reader) {
          try {
            let buffer = "";
            while (!streamDone) {
              const { done, value } = await reader.read();
              if (done) break;
              buffer += decoder.decode(value, { stream: true });

              const lines = buffer.split("\n");
              buffer = lines.pop() ?? "";

              for (const line of lines) {
                if (!line.startsWith("data: ")) continue;
                let parsed;
                try { parsed = JSON.parse(line.slice(6)); } catch { continue; }
                if (parsed.done) { streamDone = true; break; }
                if (parsed.error) throw new Error(parsed.error);
                if (parsed.text) {
                  fullText += parsed.text;
                  setMessages((prev) => {
                    const updated = [...prev];
                    updated[updated.length - 1] = { role: "assistant", content: fullText };
                    return updated;
                  });
                }
              }
            }
          } finally {
            reader.releaseLock();
          }
        }
      } catch (err) {
        if ((err as Error).name === "AbortError") return;
        setMessages((prev) => {
          const last = prev[prev.length - 1];
          if (last?.role === "assistant" && !last.content) {
            const updated = [...prev];
            updated[updated.length - 1] = { role: "assistant", content: "Sorry, something went wrong. Please try again." };
            return updated;
          }
          return [...prev, { role: "assistant", content: "Sorry, something went wrong. Please try again." }];
        });
      } finally {
        setLoading(false);
        inputRef.current?.focus();
      }
    },
    [loading],
  );

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    send(input);
  };

  return (
    <div className="flex h-[calc(100vh-64px)] flex-col">
      {/* ── header ── */}
      <div className="shrink-0 border-b border-white/[0.06] px-6 py-4">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-cyan-500/15">
            <MessageSquare className="h-5 w-5 text-cyan-400" />
          </div>
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-white">AI Chat</h1>
            <p className="text-[13px] text-zinc-600">
              Ask anything about your portfolio
            </p>
          </div>
        </div>
      </div>

      {/* ── messages area ── */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto px-6 py-6">
        {messages.length === 0 && !loading ? (
          /* empty state */
          <div className="flex h-full flex-col items-center justify-center gap-6">
            <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-cyan-500/10">
              <Sparkles className="h-8 w-8 text-cyan-400" />
            </div>
            <div className="text-center">
              <h2 className="text-xl font-semibold text-white">
                How can I help?
              </h2>
              <p className="mt-1 text-[13px] text-zinc-600">
                Ask about your portfolio, market trends, or trading ideas.
              </p>
            </div>

            {/* suggested prompts */}
            <div className="grid w-full max-w-lg grid-cols-1 gap-2 sm:grid-cols-2">
              {SUGGESTIONS.map((s) => (
                <button
                  key={s}
                  onClick={() => send(s)}
                  className="glass-surface rounded-xl px-4 py-3 text-left text-sm text-zinc-300 spring-transition transition-all duration-300 hover:shadow-[0_4px_20px_rgba(0,0,0,0.3)] hover:text-white"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        ) : (
          /* message list */
          <div className="mx-auto flex max-w-2xl flex-col gap-4">
            {messages.map((msg, i) => (
              <div
                key={i}
                className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
              >
                {msg.role === "assistant" && (
                  <div className="mr-2 mt-1 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-cyan-500/15">
                    <Bot className="h-4 w-4 text-cyan-400" />
                  </div>
                )}
                <div
                  className={`max-w-[75%] whitespace-pre-wrap rounded-2xl px-4 py-3 text-sm leading-relaxed ${
                    msg.role === "user"
                      ? "bg-zinc-700/60 text-white"
                      : "glass-surface text-zinc-300"
                  }`}
                >
                  {msg.content}
                </div>
              </div>
            ))}

            {/* typing indicator */}
            {loading && (
              <div className="flex justify-start">
                <div className="mr-2 mt-1 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-cyan-500/15">
                  <Bot className="h-4 w-4 text-cyan-400" />
                </div>
                <div className="flex items-center gap-1.5 glass-surface rounded-2xl px-4 py-3">
                  <span className="h-2 w-2 animate-bounce rounded-full bg-zinc-500 [animation-delay:0ms]" />
                  <span className="h-2 w-2 animate-bounce rounded-full bg-zinc-500 [animation-delay:150ms]" />
                  <span className="h-2 w-2 animate-bounce rounded-full bg-zinc-500 [animation-delay:300ms]" />
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* ── input bar (fixed at bottom) ── */}
      <div className="shrink-0 border-t border-white/[0.06] bg-white/[0.03] px-6 py-4">
        <form
          onSubmit={handleSubmit}
          className="mx-auto flex max-w-2xl items-center gap-3"
        >
          <Input
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask about your portfolio..."
            disabled={loading}
            className="flex-1 bg-white/[0.03] border-white/[0.06] text-white placeholder:text-zinc-700 focus:border-cyan-500/30 rounded-xl"
          />
          <Button
            type="submit"
            size="icon"
            disabled={loading || !input.trim()}
            className="h-10 w-10 shrink-0 bg-gradient-to-r from-cyan-500/10 to-emerald-500/10 text-cyan-400 border border-cyan-500/20 rounded-xl spring-transition disabled:opacity-40"
          >
            <Send className="h-4 w-4" />
          </Button>
        </form>
      </div>
    </div>
  );
}
