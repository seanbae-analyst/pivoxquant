"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { MessageSquare, Send, Sparkles, Bot, AlertCircle, RotateCcw } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { API } from "@/lib/endpoints";
import { useAiStatus } from "@/lib/hooks";
import type { AiChatMessage } from "@/lib/types";

/* ── constants ── */

const CHAT_TIMEOUT_MS = 120_000; // 2 minutes — AI can be slow

const SUGGESTIONS = [
  "Analyze my portfolio risk",
  "What should I buy?",
  "Explain my worst performer",
  "Give me a morning summary",
] as const;

/* ── page ── */

export default function AIChatPage() {
  const { data: aiStatus, isLoading: statusLoading } = useAiStatus();
  const [messages, setMessages] = useState<AiChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
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
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    return () => {
      abortRef.current?.abort();
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
    };
  }, []);

  /* send message */
  const send = useCallback(
    async (text: string) => {
      const trimmed = text.trim();
      if (!trimmed || loading) return;

      setInput("");
      setErrorMsg(null);

      // Build history from existing messages (last 10 for context)
      const history = messages
        .filter((m) => m.content.length > 0)
        .slice(-10)
        .map((m) => ({ role: m.role, content: m.content }));

      setMessages((prev) => [...prev, { role: "user", content: trimmed }]);
      setLoading(true);

      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;

      // Timeout — abort if AI takes too long
      timeoutRef.current = setTimeout(() => {
        controller.abort();
        setErrorMsg("Response timed out. The AI server may be overloaded. Please try again.");
      }, CHAT_TIMEOUT_MS);

      try {
        const res = await fetch(API.ai.chat, {
          method: "POST",
          credentials: "include",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ message: trimmed, history }),
          signal: controller.signal,
        });

        if (!res.ok) {
          const body = await res.json().catch(() => ({ error: res.statusText }));
          throw new Error(body.error ?? `Server error (${res.status})`);
        }

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
                let parsed: { done?: boolean; error?: string; text?: string };
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

        // If we got no text at all, show error
        if (!fullText && !streamDone) {
          setMessages((prev) => {
            const updated = [...prev];
            updated[updated.length - 1] = { role: "assistant", content: "No response received. Please try again." };
            return updated;
          });
        }
      } catch (err) {
        if ((err as Error).name === "AbortError") {
          // If no errorMsg already set (timeout sets its own), set a generic one
          if (!errorMsg) {
            setMessages((prev) => {
              const last = prev[prev.length - 1];
              if (last?.role === "assistant" && !last.content) {
                return prev.slice(0, -1); // Remove empty assistant placeholder
              }
              return prev;
            });
          }
          return;
        }
        const errText = (err as Error).message || "Something went wrong. Please try again.";
        setMessages((prev) => {
          const last = prev[prev.length - 1];
          if (last?.role === "assistant" && !last.content) {
            const updated = [...prev];
            updated[updated.length - 1] = { role: "assistant", content: errText };
            return updated;
          }
          return [...prev, { role: "assistant", content: errText }];
        });
      } finally {
        setLoading(false);
        if (timeoutRef.current) clearTimeout(timeoutRef.current);
        inputRef.current?.focus();
      }
    },
    [loading, messages, errorMsg],
  );

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    send(input);
  };

  const handleClear = () => {
    setMessages([]);
    setErrorMsg(null);
    inputRef.current?.focus();
  };

  // AI not available state
  if (!statusLoading && aiStatus && !aiStatus.available) {
    return (
      <div className="flex h-[calc(100vh-80px)] flex-col items-center justify-center gap-4 px-6">
        <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-amber-500/10">
          <AlertCircle className="h-8 w-8 text-amber-500" />
        </div>
        <h2 className="text-lg font-semibold text-slate-900">AI is not available</h2>
        <p className="text-center text-sm text-slate-400 max-w-md">
          The AI service requires an API key to be configured. Please check your server settings.
        </p>
      </div>
    );
  }

  return (
    <div className="flex h-[calc(100vh-80px)] flex-col">
      {/* ── header ── */}
      <div className="shrink-0 border-b border-slate-200 px-4 sm:px-6 py-3 sm:py-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 sm:h-10 sm:w-10 items-center justify-center rounded-xl bg-violet-500/10">
              <MessageSquare className="h-4 w-4 sm:h-5 sm:w-5 text-violet-600" />
            </div>
            <div>
              <h1 className="text-lg sm:text-2xl font-bold tracking-tight text-slate-900">AI Chat</h1>
              <p className="text-[11px] sm:text-[13px] text-slate-400">
                Ask anything about your portfolio
              </p>
            </div>
          </div>
          {messages.length > 0 && (
            <button
              onClick={handleClear}
              className="flex items-center gap-1.5 text-[11px] text-slate-400 hover:text-slate-700 spring-transition transition-colors duration-300"
            >
              <RotateCcw className="h-3.5 w-3.5" />
              <span className="hidden sm:inline">New chat</span>
            </button>
          )}
        </div>
      </div>

      {/* ── error banner ── */}
      {errorMsg && (
        <div className="shrink-0 bg-amber-50 border-b border-amber-200 px-4 sm:px-6 py-2.5">
          <p className="text-[12px] text-amber-700 flex items-center gap-2">
            <AlertCircle className="h-3.5 w-3.5 shrink-0" />
            {errorMsg}
          </p>
        </div>
      )}

      {/* ── messages area ── */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 sm:px-6 py-4 sm:py-6">
        {messages.length === 0 && !loading ? (
          /* empty state */
          <div className="flex h-full flex-col items-center justify-center gap-5 sm:gap-6">
            <div className="flex h-14 w-14 sm:h-16 sm:w-16 items-center justify-center rounded-2xl bg-violet-500/10">
              <Sparkles className="h-7 w-7 sm:h-8 sm:w-8 text-violet-600" />
            </div>
            <div className="text-center">
              <h2 className="text-lg sm:text-xl font-semibold text-slate-900">
                How can I help?
              </h2>
              <p className="mt-1 text-[12px] sm:text-[13px] text-slate-400">
                Ask about your portfolio, market trends, or trading ideas.
              </p>
            </div>

            {/* suggested prompts */}
            <div className="grid w-full max-w-lg grid-cols-1 gap-2 sm:grid-cols-2">
              {SUGGESTIONS.map((s) => (
                <button
                  key={s}
                  onClick={() => send(s)}
                  className="glass-surface rounded-xl px-4 py-3 text-left text-sm text-slate-500 spring-transition transition-all duration-300 hover:shadow-[0_4px_20px_rgba(0,0,0,0.08)] hover:text-slate-900"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        ) : (
          /* message list */
          <div className="mx-auto flex max-w-2xl flex-col gap-3 sm:gap-4">
            {messages.map((msg, i) => (
              <div
                key={i}
                className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
              >
                {msg.role === "assistant" && (
                  <div className="mr-2 mt-1 flex h-6 w-6 sm:h-7 sm:w-7 shrink-0 items-center justify-center rounded-lg bg-violet-500/10">
                    <Bot className="h-3.5 w-3.5 sm:h-4 sm:w-4 text-violet-600" />
                  </div>
                )}
                <div
                  className={`max-w-[85%] sm:max-w-[75%] whitespace-pre-wrap rounded-2xl px-3.5 sm:px-4 py-2.5 sm:py-3 text-[13px] sm:text-sm leading-relaxed ${
                    msg.role === "user"
                      ? "bg-slate-100 text-slate-900"
                      : "glass-surface text-slate-700"
                  }`}
                >
                  {msg.content}
                </div>
              </div>
            ))}

            {/* typing indicator */}
            {loading && messages[messages.length - 1]?.role !== "assistant" && (
              <div className="flex justify-start">
                <div className="mr-2 mt-1 flex h-6 w-6 sm:h-7 sm:w-7 shrink-0 items-center justify-center rounded-lg bg-violet-500/10">
                  <Bot className="h-3.5 w-3.5 sm:h-4 sm:w-4 text-violet-600" />
                </div>
                <div className="flex items-center gap-1.5 glass-surface rounded-2xl px-4 py-3">
                  <span className="h-2 w-2 animate-bounce rounded-full bg-slate-400 [animation-delay:0ms]" />
                  <span className="h-2 w-2 animate-bounce rounded-full bg-slate-400 [animation-delay:150ms]" />
                  <span className="h-2 w-2 animate-bounce rounded-full bg-slate-400 [animation-delay:300ms]" />
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* ── input bar (fixed at bottom) ── */}
      <div className="shrink-0 border-t border-slate-200 bg-slate-50/50 px-4 sm:px-6 py-3 sm:py-4">
        <form
          onSubmit={handleSubmit}
          className="mx-auto flex max-w-2xl items-center gap-2 sm:gap-3"
        >
          <Input
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask about your portfolio..."
            disabled={loading}
            className="flex-1 bg-white border-slate-200 text-slate-900 placeholder:text-slate-400 focus:border-violet-500/30 rounded-xl text-[13px] sm:text-sm"
          />
          <Button
            type="submit"
            size="icon"
            disabled={loading || !input.trim()}
            className="h-9 w-9 sm:h-10 sm:w-10 shrink-0 bg-gradient-to-r from-violet-500/10 to-indigo-500/10 text-violet-600 border border-violet-500/20 rounded-xl spring-transition disabled:opacity-40"
          >
            <Send className="h-4 w-4" />
          </Button>
        </form>
        <p className="mx-auto max-w-2xl mt-1.5 text-[9px] text-slate-300 text-center">
          AI analysis, not financial advice. Responses include your portfolio context.
        </p>
      </div>
    </div>
  );
}
