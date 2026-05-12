"use client";

/**
 * ChatPanel — Journal Companion Closed Beta conversation surface.
 *
 * Layout (mobile-first, 375px ground truth):
 *   ┌───────────────────────────────────────┐
 *   │ sticky header: label + bronze hairline│
 *   ├───────────────────────────────────────┤
 *   │ session-start disclosure (if !acked)  │
 *   │ scrollable message log (role=log)     │
 *   │   · user bubble (ivory, serif italic) │
 *   │   · agent bubble + bronze border-left │
 *   │     inline disclaimer band            │
 *   ├───────────────────────────────────────┤
 *   │ sticky composer: textarea + send      │
 *   │   hint · counter · rate-limit notice  │
 *   └───────────────────────────────────────┘
 *
 * Accessibility:
 *   - role="log" + aria-live="polite" on stream
 *   - Enter submits, Shift+Enter newlines
 *   - Send button keyboard-reachable, focus ring on all controls
 *   - Rate-limit surfaces as aria-live="assertive" so screen readers
 *     announce the countdown immediately.
 *
 * Legal:
 *   - Inline disclaimer band under every agent message.
 *   - Hint copy mirrors the "Remember · Mirror · Question" frame —
 *     no BUY/SELL/HOLD/추천/조언 language anywhere.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Send, AlertCircle, Loader2 } from "lucide-react";
import { motion, AnimatePresence } from "motion/react";
import {
  sendMessage,
  useCompanionHistory,
  useDisclaimerAck,
  type CompanionMessage,
  type GateVerdict,
} from "@/lib/cfo/useCompanion";
import { ApiError } from "@/lib/api";
import { DisclaimerBand } from "./disclaimer-band";

const CHAR_SOFT_CAP = 1000;
const CHAR_HARD_CAP = 2000;

function genId(): string {
  return `m_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
}

/** Soft reframe hint when the backend declines the prompt. */
function reframeHint(verdict: GateVerdict | undefined): string | null {
  switch (verdict) {
    case "refused_advice":
      return "Try asking from your record — what you already wrote, a pattern you've noticed. 자문은 제공할 수 없어요. 당신이 쓴 기록을 기반으로 물어봐 주세요.";
    case "refused_prediction":
      return "This companion won't predict — but it will remember. Ask 'what did I write when…'. 예측은 하지 않아요. 과거의 기록으로 돌아가 봐도 좋아요.";
    case "refused_guarantee":
      return "No outcome can be guaranteed. Rephrase as a reflection on what you've done before.";
    case "reframed":
      return "Reframed to stay within reflective bounds. 반영 범위에 맞게 다시 썼어요.";
    default:
      return null;
  }
}

interface ChatPanelProps {
  /**
   * Optional ticker to seed the composer with on first render. Bug #3 fix
   * (2026-05-09): /detail/[ticker] links to /companion?ticker=AAPL but the
   * param was silently dropped. Page reads the query param and passes it
   * here; we prefill the draft so the user's first message has stock
   * context without retyping.
   */
  initialContextTicker?: string | null;
}

export function ChatPanel({ initialContextTicker }: ChatPanelProps = {}) {
  const { messages, append, update } = useCompanionHistory();
  const { acknowledged, acknowledge } = useDisclaimerAck();

  const [draft, setDraft] = useState(() =>
    initialContextTicker ? `${initialContextTicker} 에 대해 ` : "",
  );
  const [sending, setSending] = useState(false);
  const [rateLimitAt, setRateLimitAt] = useState<number | null>(null);
  const [rateRemaining, setRateRemaining] = useState<number>(0);
  const [inputError, setInputError] = useState<string | null>(null);

  const scrollerRef = useRef<HTMLDivElement | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);

  // Auto-scroll to bottom on new message.
  useEffect(() => {
    const el = scrollerRef.current;
    if (!el) return;
    el.scrollTop = el.scrollHeight;
  }, [messages.length]);

  // Rate-limit countdown tick.
  useEffect(() => {
    if (rateLimitAt === null) return;
    const tick = () => {
      const remaining = Math.max(0, Math.ceil((rateLimitAt - Date.now()) / 1000));
      setRateRemaining(remaining);
      if (remaining === 0) {
        setRateLimitAt(null);
      }
    };
    tick();
    const id = window.setInterval(tick, 1000);
    return () => window.clearInterval(id);
  }, [rateLimitAt]);

  // Autogrow textarea (bounded).
  useEffect(() => {
    const ta = textareaRef.current;
    if (!ta) return;
    ta.style.height = "auto";
    ta.style.height = `${Math.min(ta.scrollHeight, 180)}px`;
  }, [draft]);

  const charCount = draft.length;
  const overSoft = charCount > CHAR_SOFT_CAP;
  const overHard = charCount > CHAR_HARD_CAP;
  const canSend = !sending && rateLimitAt === null && draft.trim().length > 0 && !overHard;

  const submit = useCallback(async () => {
    const trimmed = draft.trim();
    if (!trimmed || sending || overHard) return;
    if (rateLimitAt !== null) return;

    setInputError(null);

    const userMsg: CompanionMessage = {
      id: genId(),
      role: "user",
      text: trimmed,
      ts: Date.now(),
    };
    append(userMsg);

    const placeholderId = genId();
    const placeholder: CompanionMessage = {
      id: placeholderId,
      role: "agent",
      text: "",
      ts: Date.now(),
      pending: true,
    };
    append(placeholder);

    setDraft("");
    setSending(true);

    try {
      const res = await sendMessage(trimmed);
      update(placeholderId, {
        text: res.text,
        gate_verdict: res.gate_verdict,
        request_id: res.request_id,
        pending: false,
      });
    } catch (err) {
      if (err instanceof ApiError && err.status === 429) {
        // 60s default if backend doesn't surface Retry-After through ApiError.
        setRateLimitAt(Date.now() + 60_000);
        update(placeholderId, {
          pending: false,
          error: "Rate limit — please wait a moment.",
          text: "",
        });
      } else if (err instanceof ApiError && err.status === 403) {
        update(placeholderId, {
          pending: false,
          error: "Closed Beta access required.",
          text: "",
        });
      } else {
        const msg = err instanceof Error ? err.message : "Something went wrong.";
        update(placeholderId, {
          pending: false,
          error: msg,
          text: "",
        });
      }
    } finally {
      setSending(false);
      // Return focus to textarea for continuous typing.
      textareaRef.current?.focus();
    }
  }, [draft, sending, overHard, rateLimitAt, append, update]);

  const onKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        if (canSend) void submit();
      }
    },
    [canSend, submit],
  );

  const onChange = useCallback((e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const v = e.target.value;
    if (v.length > CHAR_HARD_CAP) {
      setInputError(`Message is too long (limit ${CHAR_HARD_CAP}).`);
      setDraft(v.slice(0, CHAR_HARD_CAP));
      return;
    }
    setInputError(null);
    setDraft(v);
  }, []);

  const showSessionBanner = !acknowledged && messages.length === 0;

  return (
    <div
      className="flex h-full min-h-[100dvh] w-full flex-col"
      style={{
        background: "var(--pq-ink, #050505)",
        color: "var(--pq-ivory, #F5F0E8)",
        // Reserve space on mobile for the fixed <BottomNav/> (64px) plus
        // safe-area. Desktop has no bottom nav so the composer sits flush.
        paddingBottom: 0,
      }}
    >
      <StickyHeader />

      <div
        ref={scrollerRef}
        role="log"
        aria-live="polite"
        aria-label="Journal Companion conversation"
        className="flex-1 overflow-y-auto px-4 pb-6 pt-5 sm:px-8"
      >
        <div className="mx-auto flex w-full max-w-2xl flex-col gap-5">
          {showSessionBanner && (
            <DisclaimerBand variant="session-start" onAcknowledge={acknowledge} />
          )}

          {messages.length === 0 && acknowledged && <EmptyState />}

          {messages.map((m) => (
            <MessageBubble key={m.id} msg={m} />
          ))}
        </div>
      </div>

      <Composer
        textareaRef={textareaRef}
        draft={draft}
        onChange={onChange}
        onKeyDown={onKeyDown}
        onSubmit={submit}
        canSend={canSend}
        sending={sending}
        charCount={charCount}
        overSoft={overSoft}
        overHard={overHard}
        rateRemaining={rateLimitAt !== null ? rateRemaining : 0}
        inputError={inputError}
      />
    </div>
  );
}

/* ─── Header ──────────────────────────────────────────────────────── */

function StickyHeader() {
  return (
    <header
      className="sticky top-0 z-10 px-4 py-3 sm:px-8"
      style={{
        background: "rgba(5, 5, 5, 0.88)",
        backdropFilter: "blur(8px)",
        WebkitBackdropFilter: "blur(8px)",
        borderBottom: "0.5px solid var(--pq-ivory-line)",
      }}
    >
      <div className="mx-auto flex w-full max-w-2xl items-center justify-between">
        <div className="flex items-center gap-2.5">
          <span
            aria-hidden
            className="h-px w-6"
            style={{ background: "rgba(184, 149, 106, 0.7)" }}
          />
          <span
            className="font-serif uppercase"
            style={{
              fontSize: "var(--pq-text-eyebrow)",
              letterSpacing: "0.22em",
              color: "var(--pq-bronze, #B8956A)",
            }}
          >
            Personal Journal Companion
          </span>
        </div>
        <span
          className="font-mono uppercase"
          style={{
            fontSize: "var(--pq-text-eyebrow)",
            letterSpacing: "0.18em",
            color: "rgba(245, 240, 232, 0.55)",
          }}
        >
          Closed Beta
        </span>
      </div>
    </header>
  );
}

/* ─── Empty state ─────────────────────────────────────────────────── */

function EmptyState() {
  return (
    <div
      className="rounded-sm p-6"
      style={{
        background: "rgba(247, 245, 239, 0.02)",
        border: "0.5px solid var(--pq-ivory-line)",
      }}
      role="note"
    >
      <p
        className="font-serif italic"
        style={{
          fontSize: "var(--pq-text-body)",
          lineHeight: 1.65,
          color: "rgba(245, 240, 232, 0.72)",
        }}
      >
        Your journal, remembered. Ask what you once wrote — or how a pattern of yours recurred.
      </p>
      <p
        className="mt-2 font-serif italic"
        style={{
          fontSize: "var(--pq-text-body)",
          lineHeight: 1.65,
          color: "rgba(184, 149, 106, 0.8)",
        }}
      >
        기록을 기반으로 묻고, 반영하고, 스스로 질문해 보세요.
      </p>
    </div>
  );
}

/* ─── Message bubble ──────────────────────────────────────────────── */

function MessageBubble({ msg }: { msg: CompanionMessage }) {
  if (msg.role === "user") {
    return (
      <motion.div
        initial={{ opacity: 0, y: 6 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.28, ease: [0.16, 1, 0.3, 1] }}
        className="flex justify-end"
      >
        <div
          className="max-w-[86%] rounded-sm px-4 py-3"
          style={{
            background: "rgba(245, 240, 232, 0.92)",
            color: "var(--pq-ink, #050505)",
          }}
        >
          <p
            className="font-serif italic"
            style={{
              fontSize: "var(--pq-text-lead)",
              lineHeight: 1.55,
              margin: 0,
              whiteSpace: "pre-wrap",
              wordBreak: "break-word",
            }}
          >
            {msg.text}
          </p>
        </div>
      </motion.div>
    );
  }

  // Agent — pending / error / content
  const hint = reframeHint(msg.gate_verdict);
  const refused =
    msg.gate_verdict === "refused_advice" ||
    msg.gate_verdict === "refused_prediction" ||
    msg.gate_verdict === "refused_guarantee" ||
    msg.gate_verdict === "refused_other";

  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: refused ? 0.5 : 0.32, ease: [0.16, 1, 0.3, 1] }}
      className="flex justify-start"
    >
      <div
        className="w-full max-w-[92%] rounded-sm"
        style={{
          background: "rgba(10, 10, 10, 0.72)",
          border: "0.5px solid var(--pq-ivory-line)",
          borderLeft: "2px solid var(--pq-bronze, #B8956A)",
          padding: "14px 16px",
        }}
      >
        {msg.request_id && (
          <div className="mb-2 flex items-center gap-2">
            <span
              className="font-mono tabular-nums uppercase"
              style={{
                fontSize: "var(--pq-text-kicker)",
                letterSpacing: "0.2em",
                color: "rgba(184, 149, 106, 0.7)",
              }}
            >
              {msg.request_id}
            </span>
          </div>
        )}

        {msg.pending ? (
          <div className="flex items-center gap-2">
            <Loader2
              className="h-3.5 w-3.5 animate-spin"
              strokeWidth={1.5}
              style={{ color: "var(--pq-bronze, #B8956A)" }}
              aria-hidden
            />
            <span
              className="font-serif italic"
              style={{
                fontSize: "var(--pq-text-body)",
                color: "rgba(245, 240, 232, 0.55)",
              }}
            >
              Remembering…
            </span>
          </div>
        ) : msg.error ? (
          <div className="flex items-start gap-2">
            <AlertCircle
              className="mt-[3px] h-3.5 w-3.5 shrink-0"
              strokeWidth={1.5}
              style={{ color: "rgba(239, 184, 143, 0.8)" }}
              aria-hidden
            />
            <p
              className="font-serif"
              style={{
                fontSize: "var(--pq-text-body)",
                lineHeight: 1.55,
                color: "rgba(245, 240, 232, 0.78)",
                margin: 0,
              }}
            >
              {msg.error}
            </p>
          </div>
        ) : (
          <>
            <p
              className="font-serif"
              style={{
                fontSize: "var(--pq-text-lead)",
                lineHeight: 1.7,
                color: "var(--pq-ivory, #F5F0E8)",
                margin: 0,
                whiteSpace: "pre-wrap",
                wordBreak: "break-word",
              }}
            >
              {msg.text}
            </p>
            {hint && (
              <p
                className="mt-3 font-serif italic"
                style={{
                  fontSize: "var(--pq-text-eyebrow)",
                  lineHeight: 1.55,
                  color: "rgba(184, 149, 106, 0.85)",
                  margin: 0,
                }}
              >
                {hint}
              </p>
            )}
            <DisclaimerBand variant="inline" />
          </>
        )}
      </div>
    </motion.div>
  );
}

/* ─── Composer ────────────────────────────────────────────────────── */

interface ComposerProps {
  textareaRef: React.RefObject<HTMLTextAreaElement | null>;
  draft: string;
  onChange: (e: React.ChangeEvent<HTMLTextAreaElement>) => void;
  onKeyDown: (e: React.KeyboardEvent<HTMLTextAreaElement>) => void;
  onSubmit: () => void;
  canSend: boolean;
  sending: boolean;
  charCount: number;
  overSoft: boolean;
  overHard: boolean;
  rateRemaining: number;
  inputError: string | null;
}

function Composer({
  textareaRef,
  draft,
  onChange,
  onKeyDown,
  onSubmit,
  canSend,
  sending,
  charCount,
  overSoft,
  overHard,
  rateRemaining,
  inputError,
}: ComposerProps) {
  const counterColor = useMemo(() => {
    if (overHard) return "rgba(239, 184, 143, 0.95)";
    if (overSoft) return "rgba(184, 149, 106, 0.9)";
    return "rgba(245, 240, 232, 0.45)";
  }, [overSoft, overHard]);

  const rateLimited = rateRemaining > 0;

  return (
    <div
      className="sticky bottom-0 z-10 px-4 pb-[max(16px,env(safe-area-inset-bottom))] pt-3 sm:px-8 md:mb-0 mb-16"
      style={{
        background: "rgba(5, 5, 5, 0.92)",
        backdropFilter: "blur(8px)",
        WebkitBackdropFilter: "blur(8px)",
        borderTop: "0.5px solid var(--pq-ivory-line)",
      }}
    >
      <div className="mx-auto w-full max-w-2xl">
        <AnimatePresence>
          {rateLimited && (
            <motion.div
              key="rate"
              initial={{ opacity: 0, y: 4 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              role="status"
              aria-live="assertive"
              className="mb-2 rounded-sm px-3 py-2"
              style={{
                background: "rgba(239, 184, 143, 0.08)",
                border: "0.5px solid rgba(239, 184, 143, 0.3)",
                color: "rgba(239, 184, 143, 0.95)",
                fontSize: "var(--pq-text-eyebrow)",
              }}
            >
              Rate limit reached · {rateRemaining}s until you can send again.
            </motion.div>
          )}
        </AnimatePresence>

        <div
          className="rounded-sm"
          style={{
            background: "rgba(247, 245, 239, 0.04)",
            border: "0.5px solid rgba(245, 240, 232, 0.12)",
          }}
        >
          <label htmlFor="companion-input" className="sr-only">
            Write to your Journal Companion
          </label>
          <textarea
            id="companion-input"
            ref={textareaRef}
            value={draft}
            onChange={onChange}
            onKeyDown={onKeyDown}
            disabled={sending || rateLimited}
            placeholder="Ask 'what did I write when…' or 'show my pattern around…'"
            rows={1}
            aria-describedby="companion-hint companion-counter"
            aria-invalid={overHard || !!inputError}
            className="w-full resize-none bg-transparent px-4 py-3 font-serif outline-none placeholder:italic"
            style={{
              color: "var(--pq-ivory, #F5F0E8)",
              fontSize: "var(--pq-text-lead)",
              lineHeight: 1.55,
              minHeight: 48,
              maxHeight: 180,
              caretColor: "var(--pq-bronze, #B8956A)",
            }}
          />
          <div
            className="flex items-center justify-between px-3 pb-2 pt-1"
            style={{ borderTop: "0.5px solid var(--pq-ivory-line-soft)" }}
          >
            <p
              id="companion-hint"
              className="font-serif italic"
              style={{
                fontSize: "var(--pq-text-eyebrow)",
                lineHeight: 1.4,
                color: "rgba(245, 240, 232, 0.5)",
                margin: 0,
              }}
            >
              Remember · Mirror · Question — this AI does not advise.
            </p>
            <div className="flex items-center gap-3">
              <span
                id="companion-counter"
                className="font-mono tabular-nums"
                style={{
                  fontSize: "var(--pq-text-eyebrow)",
                  color: counterColor,
                }}
                aria-live="off"
              >
                {charCount}/{CHAR_SOFT_CAP}
              </span>
              <button
                type="button"
                onClick={onSubmit}
                disabled={!canSend}
                aria-label="Send message"
                className="inline-flex h-8 items-center gap-1.5 rounded-sm px-3 font-serif uppercase transition-opacity"
                style={{
                  background: canSend ? "var(--pq-bronze, #B8956A)" : "rgba(184, 149, 106, 0.3)",
                  color: canSend ? "var(--pq-ink, #050505)" : "rgba(245, 240, 232, 0.55)",
                  fontSize: "var(--pq-text-eyebrow)",
                  letterSpacing: "0.2em",
                  cursor: canSend ? "pointer" : "not-allowed",
                }}
              >
                {sending ? (
                  <Loader2 className="h-3 w-3 animate-spin" strokeWidth={1.8} aria-hidden />
                ) : (
                  <Send className="h-3 w-3" strokeWidth={1.8} aria-hidden />
                )}
                Send
              </button>
            </div>
          </div>
        </div>

        {inputError && (
          <p
            role="alert"
            className="mt-2 font-serif"
            style={{
              fontSize: "var(--pq-text-eyebrow)",
              color: "rgba(239, 184, 143, 0.9)",
              margin: 0,
            }}
          >
            {inputError}
          </p>
        )}
      </div>
    </div>
  );
}

export default ChatPanel;
