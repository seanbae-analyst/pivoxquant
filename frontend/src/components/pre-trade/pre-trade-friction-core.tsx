"use client";

/**
 * Pre-Trade Friction — reusable core (Feature 6).
 *
 * Single source of truth for the self-imposed cooldown + 7-question
 * reflection cycle. Consumed by:
 *   - /pre-trade route page (direct entry: full Setup → questions → cooldown)
 *   - <PreTradeFrictionModal /> (inline at the moment of action — Portfolio v2
 *     Add (ENTRY) / Trim·Close (EXIT) — ticker/shares/rationale prefilled,
 *     Setup skipped)
 *
 * Compliance posture (routes/pre_trade.py): "정보 제공용 UX 입니다. 거래
 * 권유가 아닙니다." We DO NOT place trades. `/proceed` only stamps "user
 * finished thinking" on a row; the caller's `onProceed()` then commits the
 * actual journal record (add / trim / close). Cooldown is the point — friction.
 *
 * v3 tone: Vantablack + Bronze + Playfair UPRIGHT (no italic headings — in
 * lock-step with the detail-page redesign). POSITIVE / NEGATIVE / NEUTRAL
 * only; no directional advice tokens.
 *
 * Side: internal Side enum ("ENTRY" / "EXIT") → legacy wire format via
 * `@/lib/pre-trade`. The DB schema / audit row stay untouched.
 */

import {
  useCallback,
  useEffect,
  useMemo,
  useState,
  useSyncExternalStore,
} from "react";
import { toast } from "sonner";
import { Gavel, RotateCcw, Check, X, AlertCircle } from "lucide-react";
import { apiFetch, ApiError } from "@/lib/api";
import { API } from "@/lib/endpoints";
import { Caption } from "@/components/ui/editorial";
import { type Side, sideLabel, sideToWire } from "@/lib/pre-trade";
import { useT } from "@/lib/locale";
import {
  PRE_TRADE_QUESTIONS,
  PERSONA_QUESTION_HINTS,
} from "@/data/pre-trade-questions";
import { cachedPersonaId } from "@/lib/cfo/hooks";

// useSyncExternalStore plumbing for the persona hint cache (QuestionsStep).
// Both must be module-scope constants: React resubscribes whenever the
// `subscribe` identity changes, so an inline arrow would resubscribe every
// render.
//
// The cache is written once per session by usePersona() and only read here
// on open, so there is no live-update channel worth subscribing to — the
// unsubscribe is a no-op. If a live persona swap ever needs to repaint an
// open deposition, wire this to a real storage/event listener.
const subscribePersonaCache = () => () => {};
// Server render has no localStorage — null keeps SSR and first paint on the
// neutral copy, which is what avoids the hydration mismatch.
const getServerPersonaId = () => null;

// 2026-05-22 (CEO "50자 너무 많아 10자"): lowered 50 → 10. Keep in lock-step
// with models/pre_trade_reflection.py MIN_RATIONALE_CHARS — the backend
// rejects a shorter rationale, so both constants must match.
export const MIN_RATIONALE_CHARS = 10;

// The seven reflective questions live in a single SoT shared with the landing
// teaser — see `@/data/pre-trade-questions`. Re-exported here under the
// historical name so existing imports (modal, route page) stay unchanged.
export const QUESTIONS = PRE_TRADE_QUESTIONS;

export interface Reflection {
  id: number;
  intended_ticker: string;
  /**
   * 회사명 (선택). Backend `models/pre_trade_reflection.to_dict()` 는 현재
   * intended_ticker 만 직렬화하므로 forward-compat 용. 폴백 intended_ticker.
   */
  intended_ticker_name?: string | null;
  intended_side: string | null;
  intended_shares: number | null;
  rationale: string;
  cooldown_started_at: string;
  cooldown_ends_at: string;
  proceeded_at: string | null;
  cancelled_at: string | null;
  auto_extended_reason: string | null;
  /** Phase-2 observation snapshot (server echo) — rendered in /journal only. */
  observed_context?: Record<string, unknown> | null;
  seconds_remaining: number;
  status: "pending" | "ready" | "proceeded" | "cancelled" | "expired";
}

export interface StartResponse {
  ok: true;
  disclaimer: string;
  reflection: Reflection;
}

export type Phase = "setup" | "questions" | "cooldown" | "terminal";

/* ─── Shared cycle hook ──────────────────────────────────────────────────
 * Owns the server lifecycle: POST /start (after questions) → poll /status
 * (cooldown) → /proceed | /cancel. Setup-step state (ticker/side/shares/
 * rationale) is owned by the caller so a host that prefills can skip Setup.
 */

export interface PreTradeCycleArgs {
  /** Internal Side ("ENTRY" | "EXIT"). */
  side: Side;
  ticker: string;
  /** Optional shares — null/empty skips the field server-side. */
  sharesText?: string;
  rationale: string;
  /** Question acknowledgements + optional one-line answers. */
  acks: Record<number, boolean>;
  answers: Record<number, string>;
  /**
   * Called once /proceed succeeds. The host commits the real journal record
   * here (e.g. POST /api/portfolio/positions). Errors thrown here surface a
   * toast but DO NOT roll back the reflection (it is already stamped).
   */
  onProceeded?: () => Promise<void> | void;
  /** Called once /cancel succeeds (host clears its UI). */
  onCancelled?: () => void;
}

export interface PreTradeCycle {
  phase: Phase;
  reflection: Reflection | null;
  submitting: boolean;
  /** POST /start — call when all 7 questions are acknowledged. */
  startCooldown: () => Promise<void>;
  proceed: () => Promise<void>;
  cancel: () => Promise<void>;
  /** Reset to setup (route page only). */
  reset: () => void;
  /** Force-set phase (route page Setup→questions, Back, etc.). */
  setPhase: (p: Phase) => void;
}

export function usePreTradeCycle(args: PreTradeCycleArgs): PreTradeCycle {
  const {
    side,
    ticker,
    sharesText,
    rationale,
    answers,
    onProceeded,
    onCancelled,
  } = args;

  const [phase, setPhase] = useState<Phase>("setup");
  const [reflection, setReflection] = useState<Reflection | null>(null);
  const [submitting, setSubmitting] = useState(false);

  /* ── Proceed against a *specific* reflection ──
   * Shared by the user-driven `proceed()` and the auto-proceed path in
   * `startCooldown`. Takes the reflection explicitly so the auto path can act
   * on the freshly-returned row without waiting for the `reflection` state to
   * commit (closure would still hold the previous value). */
  const proceedWith = useCallback(
    async (target: Reflection) => {
      try {
        const r = await apiFetch<StartResponse>(
          API.preTrade.proceed(target.id),
          {
            method: "POST",
          },
        );
        setReflection(r.reflection);
        setPhase("terminal");
        // Commit the host's real journal record AFTER the reflection is
        // stamped. A failure here is surfaced but the reflection stands.
        try {
          await onProceeded?.();
        } catch (commitErr) {
          const cmsg =
            commitErr instanceof Error
              ? commitErr.message
              : "Failed to record entry.";
          toast.error(cmsg);
        }
      } catch (err) {
        const msg = err instanceof ApiError ? err.message : "Could not proceed";
        toast.error(msg || "Could not proceed");
      }
    },
    [onProceeded],
  );

  /* ── POST /start ── */
  const startCooldown = useCallback(async () => {
    if (submitting) return;
    setSubmitting(true);
    try {
      // Stitch the seven acknowledgements into devil_advocate so the audit
      // row carries exactly what the user signed off on.
      const ackBlob = QUESTIONS.map((q) => {
        const ans = (answers[q.n] || "").trim();
        return ans
          ? `Q${q.n} ${q.en}\n→ ${ans}`
          : `Q${q.n} ${q.en}\n→ (acknowledged)`;
      }).join("\n\n");

      const sharesNum =
        !sharesText || sharesText.trim() === "" ? null : Number(sharesText);
      const body: Record<string, unknown> = {
        ticker: ticker.trim().toUpperCase(),
        side: sideToWire(side),
        rationale: rationale.trim(),
        devil_advocate: ackBlob,
      };
      if (sharesNum !== null && Number.isFinite(sharesNum)) {
        body.shares = sharesNum;
      }

      const res = await apiFetch<StartResponse>(API.preTrade.start, {
        method: "POST",
        body: JSON.stringify(body),
      });
      const ref = res.reflection;
      setReflection(ref);

      if (ref.status === "proceeded" || ref.status === "cancelled") {
        // Server already resolved it — show the terminal recap.
        setPhase("terminal");
        return;
      }

      // Cooldown is 0 on the backend (2026-05-22), so a fresh reflection comes
      // back already `ready` (seconds_remaining <= 0). Skip the 00:00 counter
      // screen entirely and auto-proceed — 7 questions → recorded, no extra
      // click. The legacy cooldown > 0 path still falls through to the
      // countdown UI. (FIX 3.)
      if (ref.status === "ready" || ref.seconds_remaining <= 0) {
        await proceedWith(ref);
        return;
      }

      setPhase("cooldown");
    } catch (err) {
      const msg =
        err instanceof ApiError
          ? err.message || "Could not start cooldown"
          : "Could not start cooldown";
      toast.error(msg);
    } finally {
      setSubmitting(false);
    }
  }, [submitting, ticker, side, sharesText, rationale, answers, proceedWith]);

  /* ── Cooldown polling — local clock + 5s server sync ── */
  const reflectionId = reflection?.id;
  useEffect(() => {
    if (phase !== "cooldown" || !reflectionId) return;

    const localTick = window.setInterval(() => {
      setReflection((r) => {
        if (!r) return r;
        const next = Math.max(0, r.seconds_remaining - 1);
        return {
          ...r,
          seconds_remaining: next,
          status: next > 0 ? "pending" : "ready",
        };
      });
    }, 1000);

    const serverSync = window.setInterval(async () => {
      try {
        const r = await apiFetch<StartResponse>(
          API.preTrade.status(reflectionId),
        );
        setReflection(r.reflection);
        if (
          r.reflection.status === "proceeded" ||
          r.reflection.status === "cancelled"
        ) {
          setPhase("terminal");
        }
      } catch {
        /* swallow — keep ticking on local clock */
      }
    }, 5000);

    return () => {
      window.clearInterval(localTick);
      window.clearInterval(serverSync);
    };
  }, [phase, reflectionId]);

  /* ── Proceed (user-driven, from the cooldown CTA) ── */
  const proceed = useCallback(async () => {
    if (submitting) return;
    if (!reflection) return;
    if (reflection.status !== "ready") return;
    setSubmitting(true);
    try {
      await proceedWith(reflection);
    } finally {
      setSubmitting(false);
    }
  }, [reflection, proceedWith, submitting]);

  /* ── Cancel ── */
  const cancel = useCallback(async () => {
    if (submitting) return;
    if (!reflection) return;
    setSubmitting(true);
    try {
      const r = await apiFetch<StartResponse>(
        API.preTrade.cancel(reflection.id),
        {
          method: "POST",
        },
      );
      setReflection(r.reflection);
      setPhase("terminal");
      toast.success("Cancelled.");
      onCancelled?.();
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : "Could not cancel";
      toast.error(msg || "Could not cancel");
    } finally {
      setSubmitting(false);
    }
  }, [reflection, onCancelled, submitting]);

  const reset = useCallback(() => {
    setPhase("setup");
    setReflection(null);
    setSubmitting(false);
  }, []);

  return {
    phase,
    reflection,
    submitting,
    startCooldown,
    proceed,
    cancel,
    reset,
    setPhase,
  };
}

/* ─── Questions step ─────────────────────────────────────────────────────── */

export function QuestionsStep(props: {
  acks: Record<number, boolean>;
  setAcks: (
    f: (prev: Record<number, boolean>) => Record<number, boolean>,
  ) => void;
  answers: Record<number, string>;
  setAnswers: (
    f: (prev: Record<number, string>) => Record<number, string>,
  ) => void;
  allAcked: boolean;
  submitting: boolean;
  /** Optional Back affordance (route page: → setup). Hidden when omitted. */
  onBack?: () => void;
  onStart: () => void;
  /** When true, render without the leading numbered SectionLabel (modal). */
  bare?: boolean;
}) {
  const {
    acks,
    setAcks,
    answers,
    setAnswers,
    allAcked,
    submitting,
    onBack,
    onStart,
    bare,
  } = props;

  // Persona-aware hint lines (record-as-spine §7, 2026-06-10). Resolved
  // client-side from the usePersona() localStorage cache — no fetch from
  // the deposition flow (would break the host modals' strict apiFetch
  // call-count tests), no SSR/hydration mismatch (first paint is always
  // the neutral copy). Cold cache / offline-mock → null → questions
  // render exactly as before.
  //
  // 2026-08-30: was useState + a mount useEffect that called setHints.
  // That is render → effect → setState → re-render on every mount, which
  // `react-hooks/set-state-in-effect` flags as a cascading render. Reading
  // a client-only external store is what useSyncExternalStore is for:
  // getServerSnapshot returns null so SSR and first paint keep the neutral
  // copy, and the client snapshot is a primitive PersonaId, so it stays
  // referentially stable across renders (no resubscribe/render loop).
  const personaId = useSyncExternalStore(
    subscribePersonaCache,
    cachedPersonaId,
    getServerPersonaId,
  );
  const hints: Readonly<Record<number, string>> | null =
    (personaId && PERSONA_QUESTION_HINTS[personaId]) || null;

  return (
    <section className="space-y-6">
      {!bare && <SectionLabel n={2} title="The Deposition · 7개 질문" />}
      <ol className="space-y-5">
        {QUESTIONS.map((q) => (
          <li
            key={q.n}
            className="border-l-2 border-[var(--pq-ivory-line)] pl-5 hover:border-[var(--pq-bronze)] transition-colors"
          >
            <div className="flex items-baseline gap-3">
              <span
                className="font-mono text-pq-eyebrow uppercase tracking-[0.22em] text-[var(--pq-bronze)] mt-0.5"
                style={{ minWidth: 18 }}
              >
                {String(q.n).padStart(2, "0")}
              </span>
              <div className="flex-1 space-y-1">
                <p className="font-serif text-pq-deck leading-snug text-[var(--pq-ivory)]">
                  {q.en}
                </p>
                <p className="font-serif text-pq-body-sm text-[var(--pq-ivory-dim)]">
                  {q.ko}
                </p>
                {hints?.[q.n] && (
                  <p
                    className="font-serif text-pq-caption leading-snug"
                    // 0.85 alpha — 12px text must clear the project's WCAG
                    // ladder (globals.css: alpha 0.45 ≈ 3.99:1 is large-text
                    // only; bronze 0.66 ≈ 3.65:1 failed AA for small text).
                    style={{ color: "rgba(184,149,106,0.85)" }}
                    data-testid={`persona-hint-${q.n}`}
                  >
                    {hints[q.n]}
                  </p>
                )}
              </div>
            </div>
            <div className="mt-3 ml-[34px] flex flex-col gap-2">
              <input
                value={answers[q.n] ?? ""}
                onChange={(e) =>
                  setAnswers((prev) => ({ ...prev, [q.n]: e.target.value }))
                }
                placeholder="(optional) 한 줄로 답해보라"
                aria-label={`Answer to question ${q.n}: ${q.en}`}
                className="w-full bg-transparent border-b border-[rgba(245,240,232,0.1)] py-1.5 text-pq-body-sm font-serif outline-none focus:border-[var(--pq-bronze)] text-[var(--pq-ivory)]"
              />
              <label className="inline-flex items-center gap-2 cursor-pointer text-pq-mono-sm tracking-[0.18em] uppercase text-[var(--pq-ivory-dim)] hover:text-[var(--pq-bronze)]">
                <input
                  type="checkbox"
                  checked={!!acks[q.n]}
                  onChange={(e) =>
                    setAcks((prev) => ({ ...prev, [q.n]: e.target.checked }))
                  }
                  className="accent-[var(--pq-bronze)]"
                />
                I considered this · 검토했음
              </label>
            </div>
          </li>
        ))}
      </ol>

      <div className="flex flex-wrap gap-3 justify-between pt-3 border-t border-[var(--pq-ivory-line-soft)]">
        {onBack ? (
          <button
            type="button"
            onClick={onBack}
            disabled={submitting}
            className="px-4 py-2 text-pq-mono-sm uppercase tracking-[0.18em] text-[var(--pq-ivory-dim)] hover:text-[var(--pq-bronze)]"
          >
            ← Back
          </button>
        ) : (
          <span />
        )}
        <button
          type="button"
          onClick={onStart}
          disabled={!allAcked || submitting}
          aria-disabled={!allAcked || submitting}
          className="pq-ink-btn-bronze inline-flex items-center gap-2 px-5 py-2 text-pq-mono-sm uppercase tracking-[0.22em] disabled:opacity-30 disabled:cursor-not-allowed"
        >
          {submitting ? "Starting…" : "Start cooldown · 진입 시계"}
          <Gavel className="h-3.5 w-3.5" />
        </button>
      </div>
      {!allAcked && (
        <p
          aria-live="polite"
          role="status"
          className="text-pq-mono-sm text-[var(--pq-ivory-faint)] text-right tracking-[0.06em]"
        >
          {`모든 질문에 ✓ 표시해야 진입 시계가 시작됩니다 (${QUESTIONS.filter((q) => acks[q.n]).length}/${QUESTIONS.length}).`}
        </p>
      )}
    </section>
  );
}

/* ─── Cooldown step ──────────────────────────────────────────────────────── */

export function CooldownStep({
  reflection,
  submitting,
  onProceed,
  onCancel,
  bare,
}: {
  reflection: Reflection;
  submitting: boolean;
  onProceed: () => void;
  onCancel: () => void;
  bare?: boolean;
}) {
  const t = useT();
  const isReady =
    reflection.status === "ready" || reflection.seconds_remaining === 0;
  const totalSec = useMemo(() => {
    if (!reflection.cooldown_started_at || !reflection.cooldown_ends_at)
      return 120;
    const start = new Date(reflection.cooldown_started_at).getTime();
    const end = new Date(reflection.cooldown_ends_at).getTime();
    return Math.max(1, Math.round((end - start) / 1000));
  }, [reflection.cooldown_started_at, reflection.cooldown_ends_at]);
  const elapsed = Math.max(0, totalSec - reflection.seconds_remaining);
  const pct = Math.min(100, Math.round((elapsed / totalSec) * 100));
  const mm = Math.floor(reflection.seconds_remaining / 60);
  const ss = reflection.seconds_remaining % 60;

  return (
    <section className="space-y-6">
      {!bare && (
        <SectionLabel
          n={3}
          title={isReady ? "Ready · 결정의 시간" : "Cooldown · 진입 시계"}
        />
      )}

      <div className="rounded-[2px] border border-[var(--pq-ivory-line)] bg-[rgba(255,255,255,0.02)] p-6 md:p-8 space-y-6">
        {/* Trade summary */}
        <div className="flex flex-wrap items-baseline gap-x-6 gap-y-2">
          <span className="font-mono text-pq-mono-sm uppercase tracking-[0.22em] text-[var(--pq-bronze)]">
            {sideLabel(reflection.intended_side)}
          </span>
          <span
            className="font-serif text-pq-avatar text-[var(--pq-ivory)]"
            style={{ letterSpacing: "-0.01em" }}
          >
            {reflection.intended_ticker_name || reflection.intended_ticker}
          </span>
          {reflection.intended_shares !== null && (
            <span className="font-mono text-pq-body-sm text-[rgba(245,240,232,0.6)]">
              {reflection.intended_shares} shares
            </span>
          )}
        </div>

        {/* Big timer */}
        <div className="text-center py-4">
          <div
            className="font-mono tabular-nums text-[var(--pq-ivory)]"
            style={{
              fontSize: "clamp(48px, 9vw, 96px)",
              lineHeight: 1,
              letterSpacing: "-0.02em",
            }}
          >
            {String(mm).padStart(2, "0")}:{String(ss).padStart(2, "0")}
          </div>
          <div className="mt-3 text-pq-eyebrow tracking-[0.22em] uppercase text-[var(--pq-ivory-faint)]">
            {isReady ? "Cooldown complete" : "Time remaining · 남은 시간"}
          </div>
        </div>

        {/* Progress bar */}
        <div className="h-[2px] bg-[var(--pq-ivory-line)] relative overflow-hidden">
          <div
            className="absolute left-0 top-0 h-full bg-[var(--pq-bronze)] transition-all"
            style={{ width: `${pct}%` }}
          />
        </div>

        {/* Auto-extend reason */}
        {reflection.auto_extended_reason && (
          <div className="flex items-start gap-2 rounded-[2px] border border-[rgba(184,149,106,0.3)] bg-[rgba(184,149,106,0.05)] p-3">
            <AlertCircle className="h-3.5 w-3.5 mt-0.5 text-[var(--pq-bronze)] shrink-0" />
            <p className="text-pq-caption leading-relaxed text-[rgba(245,240,232,0.75)]">
              <span className="font-mono text-pq-eyebrow tracking-[0.18em] uppercase text-[var(--pq-bronze)] mr-2">
                Extended
              </span>
              {extendReasonLabel(reflection.auto_extended_reason)}
            </p>
          </div>
        )}

        {/* Rationale recap */}
        <div className="border-t border-[var(--pq-ivory-line-soft)] pt-4">
          <Caption>{t("preTrade.thesis")}</Caption>
          <p className="mt-2 font-serif text-pq-body leading-relaxed text-[var(--pq-ivory-soft)]">
            &ldquo;{reflection.rationale}&rdquo;
          </p>
        </div>
      </div>

      {/* Action row */}
      <div className="flex flex-wrap gap-3 justify-end">
        <button
          type="button"
          onClick={onCancel}
          disabled={submitting}
          className="inline-flex items-center gap-2 px-4 py-2 text-pq-mono-sm uppercase tracking-[0.18em] text-[var(--pq-ivory-dim)] hover:text-[var(--pq-error)]"
        >
          <X className="h-3.5 w-3.5" />
          Cancel · 취소
        </button>
        <button
          type="button"
          onClick={onProceed}
          disabled={!isReady || submitting}
          className="pq-ink-btn-bronze inline-flex items-center gap-2 px-5 py-2 text-pq-mono-sm uppercase tracking-[0.22em] disabled:opacity-30 disabled:cursor-not-allowed"
        >
          <Check className="h-3.5 w-3.5" />
          {isReady ? "I am ready · 진행" : "Wait…"}
        </button>
      </div>
    </section>
  );
}

/* ─── Terminal step ──────────────────────────────────────────────────────── */

export function TerminalStep({
  reflection,
  onReset,
  resetLabel,
  bare,
}: {
  reflection: Reflection;
  onReset: () => void;
  /** Override the reset CTA label (modal: "Close"; page: "New checklist"). */
  resetLabel?: string;
  bare?: boolean;
}) {
  const proceeded = reflection.status === "proceeded";
  return (
    <section className="space-y-6">
      {!bare && (
        <SectionLabel
          n={4}
          title={proceeded ? "Proceeded · 기록 완료" : "Cancelled · 취소"}
        />
      )}
      <div className="rounded-[2px] border border-[var(--pq-ivory-line)] bg-[rgba(255,255,255,0.02)] p-6 md:p-8 space-y-4">
        <div
          className="font-serif text-pq-avatar text-[var(--pq-ivory)]"
          style={{ letterSpacing: "-0.01em" }}
        >
          {proceeded ? (
            <>
              You did the work.{" "}
              <em style={{ color: "var(--pq-bronze)" }}>The record stands.</em>
            </>
          ) : (
            <>
              Step away.{" "}
              <em style={{ color: "var(--pq-bronze)" }}>The desk waits.</em>
            </>
          )}
        </div>
        <p className="font-serif text-pq-body leading-relaxed text-[var(--pq-ivory-mid)]">
          {proceeded
            ? "We stamped your reflection and recorded the entry to your book. PivoxQuant does not place trades — open your broker (KIS, etc.) and submit the order yourself."
            : "취소되었습니다. 기록되지 않았습니다. 다음 결정 때 다시 7개 질문을 거치세요."}
        </p>
        <div className="border-t border-[var(--pq-ivory-line-soft)] pt-3 flex flex-wrap gap-x-6 gap-y-1 text-pq-caption font-mono text-[var(--pq-ivory-dim)]">
          <span>
            {sideLabel(reflection.intended_side)} ·{" "}
            {reflection.intended_ticker_name || reflection.intended_ticker}
          </span>
          {reflection.intended_shares !== null && (
            <span>{reflection.intended_shares} shares</span>
          )}
          <span>
            {proceeded
              ? `Proceeded ${formatTime(reflection.proceeded_at)}`
              : `Cancelled ${formatTime(reflection.cancelled_at)}`}
          </span>
        </div>
      </div>

      <div className="flex justify-end">
        <button
          type="button"
          onClick={onReset}
          className="inline-flex items-center gap-2 px-5 py-2 text-pq-mono-sm uppercase tracking-[0.22em] text-[var(--pq-ivory-mid)] border border-[rgba(245,240,232,0.15)] hover:border-[var(--pq-bronze)] hover:text-[var(--pq-bronze)]"
        >
          <RotateCcw className="h-3.5 w-3.5" />
          {resetLabel ?? "New checklist · 새로 시작"}
        </button>
      </div>
    </section>
  );
}

/* ─── Shared helpers ─────────────────────────────────────────────────────── */

export function SectionLabel({ n, title }: { n: number; title: string }) {
  return (
    <div
      className="flex items-baseline gap-4 border-t pt-5"
      style={{ borderTopColor: "rgba(184,149,106,0.32)", borderTopWidth: 0.5 }}
    >
      <span
        className="font-mono uppercase"
        style={{
          fontSize: "var(--pq-text-eyebrow)",
          letterSpacing: "0.22em",
          color: "var(--pq-bronze)",
        }}
      >
        {String(n).padStart(2, "0")}
      </span>
      <h2
        className="font-display"
        style={{
          fontWeight: 500,
          fontSize: "clamp(20px, 2.4vw, 26px)",
          lineHeight: 1.15,
          letterSpacing: "-0.012em",
          color: "var(--pq-ivory)",
        }}
      >
        {title}
      </h2>
    </div>
  );
}

export function Field({
  label,
  htmlFor,
  children,
}: {
  label: string;
  htmlFor?: string;
  children: React.ReactNode;
}) {
  if (htmlFor) {
    return (
      <div className="block">
        <label
          htmlFor={htmlFor}
          className="block text-pq-eyebrow uppercase tracking-[0.22em] text-[var(--pq-ivory-faint)] mb-1"
        >
          {label}
        </label>
        {children}
      </div>
    );
  }
  return (
    <label className="block">
      <span className="block text-pq-eyebrow uppercase tracking-[0.22em] text-[var(--pq-ivory-faint)] mb-1">
        {label}
      </span>
      {children}
    </label>
  );
}

export function extendReasonLabel(reason: string): string {
  switch (reason) {
    case "fomc_30min":
      return "FOMC 발표가 ±30분 안에 있어 cooldown이 5분으로 연장되었습니다.";
    case "high_vix":
      return "VIX > 30 고변동성 구간이라 cooldown이 5분으로 연장되었습니다.";
    case "big_move_1h":
      return "이 종목이 최근 1시간 동안 ±5% 이상 움직여 cooldown이 5분으로 연장되었습니다.";
    default:
      return `Cooldown extended (${reason}).`;
  }
}

export function formatTime(iso: string | null): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleTimeString("en-GB", {
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return "—";
  }
}
