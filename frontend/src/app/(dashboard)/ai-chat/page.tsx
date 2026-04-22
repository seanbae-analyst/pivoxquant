"use client";

/**
 * AI Chat — Vantablack ink assistant console.
 *
 * Claude-powered conversational observation assistant. Streams SSE
 * from /api/ai/chat. No advice/recommendation language — the model
 * is constrained to neutral observation.
 */

import {
  useState,
  useRef,
  useCallback,
  useEffect,
  type FormEvent,
  type KeyboardEvent,
} from "react";
import { Send, Sparkles, StopCircle } from "lucide-react";
import { ErrorBoundary } from "@/components/ui/error-boundary";
import { TierGate } from "@/components/ui/tier-gate";
import { DisclaimerBanner } from "@/components/ui/disclaimer-banner";
import { API } from "@/lib/endpoints";

/* ── Types ── */

interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: Date;
}

/* ── Helpers ── */

function generateId(): string {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

function getCsrfToken(): string | undefined {
  if (typeof document === "undefined") return undefined;
  const match = document.cookie
    .split("; ")
    .find((c) => c.startsWith("csrf_token="));
  return match ? decodeURIComponent(match.split("=")[1]) : undefined;
}

function weekTag(): string {
  const d = new Date();
  const first = new Date(d.getFullYear(), 0, 1);
  const days = Math.floor((d.getTime() - first.getTime()) / 86400000);
  const w = Math.ceil((days + first.getDay() + 1) / 7);
  return `${d.getFullYear()} · W${String(w).padStart(2, "0")}`;
}

/* ── Suggested prompts ── */

const SUGGESTIONS = [
  "Summarize my portfolio risk exposure",
  "What observations stand out on AAPL?",
  "Explain the current market regime",
  "Walk me through my largest drawdown",
] as const;

/* ── Streaming indicator ── */

function StreamingDots() {
  return (
    <span className="inline-flex items-center gap-1" aria-label="Thinking">
      <span className="h-1 w-1 rounded-full bg-[var(--pq-bronze)] animate-pulse" />
      <span
        className="h-1 w-1 rounded-full bg-[var(--pq-bronze)] animate-pulse"
        style={{ animationDelay: "0.2s" }}
      />
      <span
        className="h-1 w-1 rounded-full bg-[var(--pq-bronze)] animate-pulse"
        style={{ animationDelay: "0.4s" }}
      />
    </span>
  );
}

/* ── Message ── */

function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === "user";

  return (
    <div
      className={"flex w-full " + (isUser ? "justify-end" : "justify-start")}
    >
      <div
        className={
          "max-w-[85%] px-4 py-3 font-serif text-[14px] leading-relaxed " +
          (isUser
            ? "border-l-[2px] border-[var(--pq-bronze)] bg-[rgba(245,240,232,0.04)] text-[var(--pq-ivory)]"
            : "text-[rgba(245,240,232,0.85)]")
        }
      >
        {!isUser && (
          <div className="mb-2 flex items-center gap-2">
            <span className="pq-ink-label" style={{ fontSize: "9px" }}>
              Assistant
            </span>
            <span className="font-mono text-[9px] uppercase tracking-[0.22em] text-[rgba(245,240,232,0.35)]">
              Claude · Observation
            </span>
          </div>
        )}
        {message.content ? (
          <div className="whitespace-pre-wrap break-words">{message.content}</div>
        ) : (
          <StreamingDots />
        )}
      </div>
    </div>
  );
}

/* ── Welcome ── */

function Welcome({ onPick }: { onPick: (text: string) => void }) {
  return (
    <div className="mx-auto max-w-xl text-center">
      <Sparkles
        className="mx-auto h-7 w-7 text-[var(--pq-bronze)]"
        strokeWidth={1.25}
      />
      <div className="mt-4 pq-ink-label">Assistant · Observation</div>
      <h2 className="mt-2 font-serif italic text-[28px] text-[var(--pq-ivory)]">
        Ask about your portfolio observation.
      </h2>
      <p className="mt-3 font-serif italic text-[14px] leading-relaxed text-[rgba(245,240,232,0.55)]">
        Powered by Claude. Responses are informational observations, not
        investment advice.
      </p>

      <div className="mt-8 grid grid-cols-1 gap-2 sm:grid-cols-2">
        {SUGGESTIONS.map((text) => (
          <button
            key={text}
            type="button"
            onClick={() => onPick(text)}
            className="border border-[rgba(245,240,232,0.1)] px-4 py-3 text-left font-serif text-[13px] leading-relaxed text-[rgba(245,240,232,0.7)] transition-colors hover:border-[var(--pq-bronze)] hover:text-[var(--pq-ivory)]"
          >
            &ldquo;{text}&rdquo;
          </button>
        ))}
      </div>
    </div>
  );
}

/* ── Main Page ── */

function ChatInner() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleTextareaInput = useCallback(() => {
    const el = inputRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 140)}px`;
  }, []);

  const sendMessage = useCallback(
    async (text: string) => {
      const trimmed = text.trim();
      if (!trimmed || streaming) return;

      const userMsg: ChatMessage = {
        id: generateId(),
        role: "user",
        content: trimmed,
        timestamp: new Date(),
      };
      const aiMsg: ChatMessage = {
        id: generateId(),
        role: "assistant",
        content: "",
        timestamp: new Date(),
      };

      setMessages((prev) => [...prev, userMsg, aiMsg]);
      setInput("");
      setStreaming(true);

      if (inputRef.current) {
        inputRef.current.style.height = "auto";
      }

      const controller = new AbortController();
      abortRef.current = controller;

      try {
        const csrfToken = getCsrfToken();
        const headers: Record<string, string> = {
          "Content-Type": "application/json",
        };
        if (csrfToken) headers["X-CSRF-Token"] = csrfToken;

        const response = await fetch(API.ai.chat, {
          method: "POST",
          credentials: "include",
          headers,
          body: JSON.stringify({ message: trimmed }),
          signal: controller.signal,
        });

        if (!response.ok) {
          const errorBody = await response.json().catch(() => ({}));
          const errorText =
            (errorBody as Record<string, string>).error ??
            `Server error (${response.status})`;
          setMessages((prev) => {
            const updated = [...prev];
            updated[updated.length - 1] = {
              ...updated[updated.length - 1],
              content: `Error: ${errorText}`,
            };
            return updated;
          });
          setStreaming(false);
          return;
        }

        const reader = response.body?.getReader();
        if (!reader) throw new Error("No response body");

        const decoder = new TextDecoder();
        let accumulated = "";
        let buffer = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n");
          buffer = lines.pop() ?? "";

          for (const line of lines) {
            if (line.startsWith("data: ")) {
              const data = line.slice(6);
              if (data === "[DONE]") break;
              accumulated += data;
              setMessages((prev) => {
                const updated = [...prev];
                updated[updated.length - 1] = {
                  ...updated[updated.length - 1],
                  content: accumulated,
                };
                return updated;
              });
            }
          }
        }

        if (buffer.startsWith("data: ")) {
          const data = buffer.slice(6);
          if (data !== "[DONE]") {
            accumulated += data;
            setMessages((prev) => {
              const updated = [...prev];
              updated[updated.length - 1] = {
                ...updated[updated.length - 1],
                content: accumulated,
              };
              return updated;
            });
          }
        }
      } catch (err: unknown) {
        if (err instanceof DOMException && err.name === "AbortError") {
          // user cancelled
        } else {
          const errorMessage =
            err instanceof Error ? err.message : "Request failed";
          setMessages((prev) => {
            const updated = [...prev];
            const lastMsg = updated[updated.length - 1];
            if (lastMsg && !lastMsg.content) {
              updated[updated.length - 1] = {
                ...lastMsg,
                content: `Error: ${errorMessage}`,
              };
            }
            return updated;
          });
        }
      } finally {
        abortRef.current = null;
        setStreaming(false);
      }
    },
    [streaming],
  );

  const stopStreaming = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    setStreaming(false);
  }, []);

  const handleSubmit = useCallback(
    (e: FormEvent) => {
      e.preventDefault();
      sendMessage(input);
    },
    [input, sendMessage],
  );

  const handleKeyDown = useCallback(
    (e: KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        sendMessage(input);
      }
    },
    [input, sendMessage],
  );

  const hasMessages = messages.length > 0;

  return (
    <div className="flex h-[calc(100dvh-8rem)] flex-col">
      <header className="mb-6 flex items-center justify-between">
        <div>
          <div className="pq-ink-kicker">ASSISTANT · 2026 · {weekTag().split("·")[1]?.trim() ?? ""}</div>
          <h1 className="pq-ink-h1 mt-2">Observation Assistant</h1>
        </div>
        <div className="font-mono text-[10px] uppercase tracking-[0.22em] text-[var(--pq-bronze)]">
          {streaming ? "Streaming" : "Idle"}
        </div>
      </header>

      {/* Messages area */}
      <div className="flex-1 overflow-y-auto border-t border-[rgba(245,240,232,0.1)] pt-6">
        {hasMessages ? (
          <div className="space-y-6 pb-6">
            {messages.map((msg) => (
              <MessageBubble key={msg.id} message={msg} />
            ))}
            <div ref={messagesEndRef} />
          </div>
        ) : (
          <div className="flex h-full items-center justify-center py-12">
            <Welcome onPick={sendMessage} />
          </div>
        )}
      </div>

      {/* Input area */}
      <div className="shrink-0 border-t border-[rgba(245,240,232,0.1)] pt-4">
        <DisclaimerBanner type="coaching" className="mb-3" />

        <form
          onSubmit={handleSubmit}
          className="flex items-end gap-3"
        >
          <div className="relative flex-1">
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => {
                setInput(e.target.value);
                handleTextareaInput();
              }}
              onKeyDown={handleKeyDown}
              placeholder="Ask about your portfolio observation…"
              disabled={streaming}
              rows={1}
              className="pq-ink-input w-full resize-none"
              style={{ maxHeight: 140 }}
            />
          </div>

          {streaming ? (
            <button
              type="button"
              onClick={stopStreaming}
              className="pq-ink-btn-ghost"
              aria-label="Stop"
            >
              <StopCircle className="h-4 w-4" />
              <span>Stop</span>
            </button>
          ) : (
            <button
              type="submit"
              disabled={!input.trim()}
              className="pq-ink-btn-bronze disabled:opacity-40"
              aria-label="Send"
            >
              <Send className="h-4 w-4" />
              <span>Send</span>
            </button>
          )}
        </form>
      </div>
    </div>
  );
}

export default function AiChatPage() {
  return (
    <ErrorBoundary>
      <TierGate tier="pro">
        <ChatInner />
      </TierGate>
    </ErrorBoundary>
  );
}
