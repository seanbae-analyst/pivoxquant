"use client";

import {
  useState,
  useRef,
  useCallback,
  useEffect,
  type FormEvent,
  type KeyboardEvent,
} from "react";
import { Send, Bot, User, Sparkles, StopCircle } from "lucide-react";
import { ErrorBoundary } from "@/components/ui/error-boundary";
import { TierGate } from "@/components/ui/tier-gate";
import { DisclaimerBanner } from "@/components/ui/disclaimer-banner";
import { API } from "@/lib/endpoints";
import { cn } from "@/lib/utils";

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

/* ── Suggested prompts ── */

const SUGGESTIONS = [
  "Why did my portfolio drop today?",
  "Analyze AAPL for me",
  "What's the market outlook this week?",
] as const;

/* ── Streaming Dots ── */

function StreamingDots() {
  return (
    <span className="inline-flex items-center gap-1" aria-label="AI is thinking">
      <span className="h-1.5 w-1.5 rounded-full bg-[var(--sp-accent)] animate-[pulse-dot_1.4s_ease-in-out_infinite]" />
      <span className="h-1.5 w-1.5 rounded-full bg-[var(--sp-accent)] animate-[pulse-dot_1.4s_ease-in-out_0.2s_infinite]" />
      <span className="h-1.5 w-1.5 rounded-full bg-[var(--sp-accent)] animate-[pulse-dot_1.4s_ease-in-out_0.4s_infinite]" />
    </span>
  );
}

/* ── Message Bubble ── */

function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === "user";

  return (
    <div
      className={cn(
        "flex gap-3 max-w-[85%] sm:max-w-[75%]",
        isUser ? "ml-auto flex-row-reverse" : "mr-auto",
      )}
    >
      {/* Avatar */}
      <div
        className={cn(
          "flex h-8 w-8 shrink-0 items-center justify-center rounded-full",
          isUser
            ? "bg-slate-900 text-white"
            : "bg-[var(--sp-accent-light)] text-[var(--sp-accent)]",
        )}
      >
        {isUser ? (
          <User className="h-4 w-4" />
        ) : (
          <Bot className="h-4 w-4" />
        )}
      </div>

      {/* Bubble */}
      <div
        className={cn(
          "rounded-2xl px-4 py-3 text-sm leading-relaxed",
          isUser
            ? "bg-slate-100 text-slate-900"
            : "bg-white border border-slate-200 text-slate-800 shadow-sm",
          !isUser && "border-l-[3px] border-l-[var(--sp-accent)]",
        )}
      >
        {message.content ? (
          <div className="whitespace-pre-wrap break-words">{message.content}</div>
        ) : (
          <StreamingDots />
        )}
      </div>
    </div>
  );
}

/* ── Welcome Card ── */

function WelcomeCard({
  onSuggestionClick,
}: {
  onSuggestionClick: (text: string) => void;
}) {
  return (
    <div className="mx-auto max-w-lg">
      <div className="sp-card p-6 text-center">
        <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-[var(--sp-accent-light)]">
          <Sparkles className="h-7 w-7 text-[var(--sp-accent)]" />
        </div>
        <h2 className="mb-2 text-lg font-bold text-slate-900">
          AI Investment Assistant
        </h2>
        <p className="mb-5 text-sm text-slate-500 leading-relaxed">
          I can help you understand market data, analyze stocks, and review your portfolio metrics.
          Ask me a question to get started.
        </p>
        <div className="space-y-2">
          <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
            Try asking
          </p>
          {SUGGESTIONS.map((text) => (
            <button
              key={text}
              type="button"
              onClick={() => onSuggestionClick(text)}
              className="block w-full rounded-xl border border-slate-200 bg-slate-50 px-4 py-2.5 text-left text-sm text-slate-700 transition-all duration-200 hover:border-[var(--sp-accent)] hover:bg-[var(--sp-accent-light)] hover:text-[var(--sp-accent-hover)] active:scale-[0.99]"
              style={{
                transitionTimingFunction: "cubic-bezier(0.16, 1, 0.3, 1)",
              }}
            >
              &ldquo;{text}&rdquo;
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

/* ── Main Page ── */

export default function AiChatPage() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  /* Auto-scroll to bottom when new messages arrive */
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  /* Auto-resize textarea */
  const handleTextareaInput = useCallback(() => {
    const el = inputRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 120)}px`;
  }, []);

  /* Send message with SSE streaming */
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

      // Reset textarea height
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
        if (csrfToken) {
          headers["X-CSRF-Token"] = csrfToken;
        }

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
        if (!reader) {
          throw new Error("No response body");
        }

        const decoder = new TextDecoder();
        let accumulated = "";
        let buffer = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n");
          // Keep the last potentially incomplete line in the buffer
          buffer = lines.pop() ?? "";

          for (const line of lines) {
            if (line.startsWith("data: ")) {
              const data = line.slice(6);
              if (data === "[DONE]") break;
              accumulated += data;
              setMessages((prev) => {
                const updated = [...prev];
                const lastMsg = updated[updated.length - 1];
                updated[updated.length - 1] = {
                  ...lastMsg,
                  content: accumulated,
                };
                return updated;
              });
            }
          }
        }

        // Process any remaining buffer
        if (buffer.startsWith("data: ")) {
          const data = buffer.slice(6);
          if (data !== "[DONE]") {
            accumulated += data;
            setMessages((prev) => {
              const updated = [...prev];
              const lastMsg = updated[updated.length - 1];
              updated[updated.length - 1] = {
                ...lastMsg,
                content: accumulated,
              };
              return updated;
            });
          }
        }
      } catch (err: unknown) {
        if (err instanceof DOMException && err.name === "AbortError") {
          // User cancelled — do nothing
        } else {
          const errorMessage =
            err instanceof Error ? err.message : "Something went wrong";
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

  /* Stop streaming */
  const stopStreaming = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    setStreaming(false);
  }, []);

  /* Form submit */
  const handleSubmit = useCallback(
    (e: FormEvent) => {
      e.preventDefault();
      sendMessage(input);
    },
    [input, sendMessage],
  );

  /* Enter to send, Shift+Enter for newline */
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
    <ErrorBoundary>
      <TierGate tier="pro">
      <div className="flex h-[calc(100dvh-9rem)] flex-col md:h-[calc(100dvh-5rem)]">
        {/* Header */}
        <div className="shrink-0 border-b border-slate-200 bg-white px-4 py-3 sm:px-6">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-[var(--sp-accent-light)]">
              <Bot className="h-5 w-5 text-[var(--sp-accent)]" />
            </div>
            <div>
              <h1 className="text-base font-bold text-slate-900">
                AI Assistant
              </h1>
              <p className="text-xs text-slate-500">
                Powered by Claude AI
              </p>
            </div>
            {streaming && (
              <span className="ml-auto text-xs text-[var(--sp-accent)] font-medium">
                Thinking...
              </span>
            )}
          </div>
        </div>

        {/* Messages area */}
        <div className="flex-1 overflow-y-auto px-4 py-4 sm:px-6 scrollbar-thin">
          {hasMessages ? (
            <div className="space-y-4 max-w-3xl mx-auto">
              {messages.map((msg) => (
                <MessageBubble key={msg.id} message={msg} />
              ))}
              <div ref={messagesEndRef} />
            </div>
          ) : (
            <div className="flex h-full items-center justify-center py-8">
              <WelcomeCard onSuggestionClick={sendMessage} />
            </div>
          )}
        </div>

        {/* Input area */}
        <div className="shrink-0 border-t border-slate-200 bg-white px-4 pb-3 pt-3 sm:px-6">
          {/* Disclaimer */}
          <DisclaimerBanner type="coaching" className="mb-3" />

          <form
            onSubmit={handleSubmit}
            className="mx-auto flex max-w-3xl items-end gap-2"
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
                placeholder="Ask about your portfolio..."
                disabled={streaming}
                rows={1}
                className={cn(
                  "w-full resize-none rounded-xl border border-slate-200 bg-slate-50 px-4 py-2.5 pr-12 text-sm text-slate-900 placeholder:text-slate-400",
                  "outline-none transition-all duration-200",
                  "focus:border-[var(--sp-accent)] focus:ring-2 focus:ring-[var(--sp-accent)]/20 focus:bg-white",
                  "disabled:opacity-50 disabled:cursor-not-allowed",
                )}
                style={{
                  transitionTimingFunction: "cubic-bezier(0.16, 1, 0.3, 1)",
                  maxHeight: 120,
                }}
              />
            </div>

            {streaming ? (
              <button
                type="button"
                onClick={stopStreaming}
                className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-red-500 text-white transition-all duration-200 hover:bg-red-600 active:scale-95"
                aria-label="Stop generating"
              >
                <StopCircle className="h-5 w-5" />
              </button>
            ) : (
              <button
                type="submit"
                disabled={!input.trim()}
                className={cn(
                  "flex h-10 w-10 shrink-0 items-center justify-center rounded-xl transition-all duration-200 active:scale-95",
                  input.trim()
                    ? "bg-[var(--sp-accent)] text-white hover:bg-[var(--sp-accent-hover)]"
                    : "bg-slate-100 text-slate-400 cursor-not-allowed",
                )}
                style={{
                  transitionTimingFunction: "cubic-bezier(0.16, 1, 0.3, 1)",
                }}
                aria-label="Send message"
              >
                <Send className="h-4 w-4" />
              </button>
            )}
          </form>
        </div>
      </div>
      </TierGate>
    </ErrorBoundary>
  );
}
