"use client";

/**
 * AI Chat — Vantablack ink observation assistant.
 *
 * Claude-powered conversational observation assistant. Streams SSE
 * from /api/ai/chat. No advice/recommendation language — the model
 * is constrained to neutral observation.
 *
 * Layout: full-height flex column. Header → Main (flex-1) → Input (footer)
 * → DisclaimerBanner at page bottom with generous whitespace gap.
 */

import {
  useState,
  useRef,
  useCallback,
  useEffect,
  type FormEvent,
  type KeyboardEvent,
} from "react";
import { Send, StopCircle } from "lucide-react";
import { ErrorBoundary } from "@/components/ui/error-boundary";
import { TierGate } from "@/components/ui/tier-gate";
import { AiContentBadge } from "@/components/ui/ai-content-badge";
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

function formatTime(d: Date): string {
  const hh = String(d.getHours()).padStart(2, "0");
  const mm = String(d.getMinutes()).padStart(2, "0");
  return `${hh}:${mm}`;
}

/* ── Suggested prompts ── */

const SUGGESTIONS = [
  "Summarize my portfolio observations this week.",
  "Which of my holdings has the highest concentration?",
  "What historical risk patterns apply to my sector exposure?",
  "Observe the macro calendar ahead of next week.",
] as const;

/* ── Streaming indicator ── */

function StreamingDots() {
  return (
    <div className="flex items-center gap-1.5 pl-1" aria-label="Thinking">
      <span className="w-1.5 h-1.5 rounded-full bg-[var(--pq-bronze)] animate-pulse" />
      <span
        className="w-1.5 h-1.5 rounded-full bg-[var(--pq-bronze)] animate-pulse"
        style={{ animationDelay: "150ms" }}
      />
      <span
        className="w-1.5 h-1.5 rounded-full bg-[var(--pq-bronze)] animate-pulse"
        style={{ animationDelay: "300ms" }}
      />
    </div>
  );
}

/* ── Assistant avatar ── */

function AssistantAvatar() {
  return (
    <div className="w-7 h-7 rounded-full bg-[rgba(139,111,71,0.15)] border border-[rgba(139,111,71,0.3)] flex items-center justify-center shrink-0">
      <span className="text-pq-eyebrow text-[var(--pq-bronze)] font-serif">
        PQ
      </span>
    </div>
  );
}

/* ── Message bubble ── */

function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === "user";
  const isEmpty = !message.content;

  return (
    <div
      className={`flex gap-4 ${isUser ? "justify-end" : "justify-start"}`}
    >
      {!isUser && <AssistantAvatar />}
      <div
        className={
          isUser
            ? "max-w-[75%] bg-[rgba(139,111,71,0.08)] border border-[rgba(139,111,71,0.15)] rounded-[2px] px-4 py-3"
            : "max-w-[75%] text-[rgba(245,240,232,0.85)] border-l-2 border-[rgba(139,111,71,0.3)] pl-4"
        }
      >
        {isEmpty ? (
          <StreamingDots />
        ) : (
          <p className="text-pq-body-sm leading-relaxed whitespace-pre-wrap break-words">
            {message.content}
          </p>
        )}
        {message.timestamp && !isEmpty && (
          <div className="text-pq-kicker tracking-[0.2em] uppercase text-[rgba(245,240,232,0.55)] mt-2 font-mono">
            {formatTime(message.timestamp)}
          </div>
        )}
      </div>
    </div>
  );
}

/* ── Welcome block ── */

function WelcomeBlock({ onPick }: { onPick: (text: string) => void }) {
  return (
    <div className="flex-1 flex flex-col items-center justify-center py-16 px-6 text-center">
      <div className="max-w-md mb-12">
        <div
          className="font-mono text-pq-caption uppercase mb-4"
          style={{ letterSpacing: "0.22em", color: "var(--pq-bronze)" }}
        >
          Observation Assistant
        </div>
        <h2
          className="mb-4 font-display"
          style={{
            fontWeight: 500,
            fontSize: "var(--pq-text-h3)",
            lineHeight: 1.15,
            letterSpacing: "-0.02em",
            color: "var(--pq-ivory)",
          }}
        >
          Ask the{" "}
          <span style={{ fontStyle: "italic", color: "var(--pq-bronze)" }}>
            desk.
          </span>
        </h2>
        <p
          className="font-serif italic"
          style={{
            fontSize: "var(--pq-text-body)",
            lineHeight: 1.55,
            color: "rgba(245,240,232,0.6)",
          }}
        >
          Claude-augmented synthesis of your portfolio, market observations,
          and historical patterns. Every response is informational only —
          never a directive.
        </p>
      </div>

      {/* Editorial prompt list — was a 4-card boxy grid (`border ... rounded
          hover:border-bronze`) which read as a generic onboarding tile row.
          Now hairline-divided rows with bronze "→" guide, matching the
          ledger rhythm used by /risk v2 layer ladder + /discover overview. */}
      <div
        className="w-full max-w-2xl border-t"
        style={{
          borderTopColor: "rgba(184,149,106,0.32)",
          borderTopWidth: 0.5,
        }}
      >
        {SUGGESTIONS.map((q) => (
          <button
            key={q}
            type="button"
            onClick={() => onPick(q)}
            className="group flex w-full items-baseline gap-4 border-b py-4 px-1 text-left transition-colors"
            style={{
              borderBottomColor: "var(--pq-ivory-line-soft)",
              borderBottomWidth: 0.5,
              color: "rgba(245,240,232,0.75)",
            }}
          >
            <span
              className="font-mono shrink-0"
              style={{
                fontSize: "var(--pq-text-eyebrow)",
                color: "var(--pq-bronze)",
                letterSpacing: "0.05em",
              }}
            >
              →
            </span>
            <span
              className="font-serif"
              style={{
                fontSize: "var(--pq-text-body)",
                lineHeight: 1.45,
              }}
            >
              {q}
            </span>
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

  // Auto-resize textarea
  useEffect(() => {
    const el = inputRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 180)}px`;
  }, [input]);

  // P1 (wave1-critical): abort any in-flight stream when the component
  // unmounts so background fetches don't continue writing to a stale
  // setMessages closure (and silently leak network/CPU).
  useEffect(() => {
    return () => {
      abortRef.current?.abort();
      abortRef.current = null;
    };
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
    /* Mobile fix (2026-05-05): subtract both the 56px TopBar AND the 64px
       BottomNav so the chat input area does not get clipped behind the
       bottom navigation on small viewports. md+ keeps -64px since the
       desktop layout has no bottom nav. */
    <div className="flex flex-col min-h-[calc(100vh-120px)] md:min-h-[calc(100vh-64px)] gap-0">
      {/* Header — promoted to v3 lock-in (Wave 2, 2026-05-01). Was a flat
          sans-style header that broke from /portfolio v2, /risk v2, /signals,
          /discover, /alerts, /watchlist. */}
      <header
        className="pb-6 flex items-start justify-between border-b"
        style={{
          borderBottomColor: "var(--pq-ivory-line)",
          borderBottomWidth: 0.5,
        }}
      >
        <div>
          <div
            className="font-mono text-pq-caption uppercase mb-3"
            style={{ letterSpacing: "0.22em", color: "var(--pq-bronze)" }}
          >
            AI &middot; Observation Assistant
          </div>
          <h1
            className="font-display"
            style={{
              fontWeight: 500,
              fontSize: "clamp(28px, 3.6vw, 42px)",
              lineHeight: 1.1,
              letterSpacing: "-0.02em",
              color: "var(--pq-ivory)",
            }}
          >
            What are you{" "}
            <span style={{ fontStyle: "italic", color: "var(--pq-bronze)" }}>
              observing
            </span>{" "}
            today?
          </h1>
        </div>
        <div
          className="font-mono text-pq-eyebrow uppercase mt-2"
          style={{ letterSpacing: "0.22em", color: "var(--pq-bronze)" }}
        >
          {streaming ? "Streaming" : "Idle"}
        </div>
      </header>

      {/* AI content disclosure (regulatory ③ 2026-01) — chat output is AI-generated */}
      <div className="pt-4">
        <AiContentBadge variant="inline" />
      </div>

      {/* Main chat area — flex-1 grows */}
      <section className="flex-1 min-h-[480px] flex flex-col">
        {hasMessages ? (
          <div className="flex-1 overflow-y-auto py-6 space-y-6 pr-2">
            {messages.map((msg) => (
              <MessageBubble key={msg.id} message={msg} />
            ))}
            <div ref={messagesEndRef} />
          </div>
        ) : (
          <WelcomeBlock onPick={sendMessage} />
        )}
      </section>

      {/* Input — above disclaimer with breathing room */}
      <footer className="pt-6 mt-6 border-t border-[var(--pq-ivory-line)]">
        <form onSubmit={handleSubmit} className="relative">
          <label htmlFor="ai-chat-input" className="sr-only">
            AI 분석 질문 입력 · Ask the AI assistant about your portfolio
          </label>
          <textarea
            id="ai-chat-input"
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask about your portfolio observation…"
            disabled={streaming}
            rows={1}
            className="pq-ink-input w-full resize-none pr-14 py-3.5 leading-relaxed text-pq-body-sm"
            style={{ maxHeight: 180 }}
          />
          {streaming ? (
            <button
              type="button"
              onClick={stopStreaming}
              className="absolute right-3 bottom-3 w-11 h-11 flex items-center justify-center rounded-[2px] bg-[var(--pq-ivory-line-soft)] hover:bg-[rgba(245,240,232,0.1)] border border-[rgba(245,240,232,0.15)] transition-colors"
              aria-label="Stop streaming"
            >
              <StopCircle className="w-4 h-4 text-[rgba(245,240,232,0.75)]" />
            </button>
          ) : (
            <button
              type="submit"
              disabled={!input.trim()}
              className="absolute right-3 bottom-3 w-11 h-11 flex items-center justify-center rounded-[2px] bg-[var(--pq-bronze)] hover:bg-[var(--pq-bronze-light)] disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
              aria-label="Send message"
            >
              <Send className="w-4 h-4 text-[var(--pq-ink)]" />
            </button>
          )}
        </form>

        <p className="mt-3 text-pq-mono-sm text-[rgba(245,240,232,0.45)] font-serif">
          Press{" "}
          <kbd className="inline-block px-1.5 py-[1px] bg-[rgba(245,240,232,0.05)] border border-[rgba(245,240,232,0.15)] rounded-[2px] font-mono text-pq-eyebrow not- text-[rgba(245,240,232,0.7)]">Enter</kbd> to send ·{" "}
          <kbd className="inline-block px-1.5 py-[1px] bg-[rgba(245,240,232,0.05)] border border-[rgba(245,240,232,0.15)] rounded-[2px] font-mono text-pq-eyebrow not- text-[rgba(245,240,232,0.7)]">Shift+Enter</kbd> for new line
        </p>
      </footer>

      {/* Legal disclaimer mounted by (dashboard)/layout.tsx — do not re-mount. */}
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
