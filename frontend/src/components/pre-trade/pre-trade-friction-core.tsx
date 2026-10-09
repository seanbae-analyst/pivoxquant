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

import { parseUtcSafe } from "@/lib/relative-time";
import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  useSyncExternalStore,
} from "react";
import { toast } from "sonner";
import { Gavel, RotateCcw, Check, X, AlertCircle } from "lucide-react";
import { apiFetch, ApiError } from "@/lib/api";
import { API } from "@/lib/endpoints";
import { Caption } from "@/components/ui/editorial";
import {
  type Side,
  SIDE_LABEL_KO,
  sideFromWire,
  sideToWire,
} from "@/lib/pre-trade";
import { useT } from "@/lib/locale";
import {
  PRE_TRADE_QUESTIONS,
  PERSONA_QUESTION_HINTS,
} from "@/data/pre-trade-questions";
import { cachedPersonaId } from "@/lib/cfo/hooks";
import {
  type PagerDir,
  useSlideIn,
  useSwipePager,
} from "@/lib/use-swipe-pager";

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
  onProceeded?: (reflectionId: number) => Promise<void> | void;
  /** Called once /cancel succeeds (host clears its UI). */
  onCancelled?: () => void;
}

export interface PreTradeCycle {
  /** What happened to the host's record commit after proceed (drives finish copy). */
  commit: "none" | "recorded" | "failed";
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

  // 2026-09-19: the four failure toasts below were hardcoded English — the
  // moment a Korean reader most needs to be told what happened. Only the
  // LOCAL fallbacks moved to i18n: an ApiError's `message` is already the
  // server's `error_kr` under the ko locale (lib/api.ts pickErrorMessage ←
  // services/error_responses.api_error), so overriding it would replace a
  // specific Korean reason with a generic one.
  const t = useT();
  const [phase, setPhase] = useState<Phase>("setup");
  const [reflection, setReflection] = useState<Reflection | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [commit, setCommit] = useState<"none" | "recorded" | "failed">("none");

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
        // Commit the host's real journal record AFTER the reflection is
        // stamped, and BEFORE the finish screen, so its copy can say what
        // actually happened. 2026-09-10: the screen always said "recorded the
        // entry to your book", including on /pre-trade (no host commit at all)
        // and after a failed commit.
        if (onProceeded) {
          try {
            await onProceeded(target.id);
            setCommit("recorded");
          } catch (commitErr) {
            const cmsg =
              commitErr instanceof Error && commitErr.message
                ? commitErr.message
                : t("preTrade.errors.recordFailed");
            toast.error(cmsg);
            setCommit("failed");
          }
        } else {
          setCommit("none");
        }
        setPhase("terminal");
      } catch (err) {
        const fallback = t("preTrade.errors.proceedFailed");
        const msg = err instanceof ApiError ? err.message : fallback;
        toast.error(msg || fallback);
      }
    },
    [onProceeded, t],
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
      const fallback = t("preTrade.errors.cooldownFailed");
      const msg =
        err instanceof ApiError ? err.message || fallback : fallback;
      toast.error(msg);
    } finally {
      setSubmitting(false);
    }
  }, [submitting, ticker, side, sharesText, rationale, answers, proceedWith, t]);

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
      toast.success(t("preTrade.errors.cancelled"));
      onCancelled?.();
    } catch (err) {
      const fallback = t("preTrade.errors.cancelFailed");
      const msg = err instanceof ApiError ? err.message : fallback;
      toast.error(msg || fallback);
    } finally {
      setSubmitting(false);
    }
  }, [reflection, onCancelled, submitting, t]);

  const reset = useCallback(() => {
    setPhase("setup");
    setReflection(null);
    setSubmitting(false);
  }, []);

  return {
    commit,
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

/**
 * Phone pager screens inside QuestionsStep: 0..6 are the seven questions,
 * REVIEW_IDX is the last look before the start button.
 */
const REVIEW_IDX = QUESTIONS.length;

type QuestionsPager = {
  cur: number;
  swipeBlocked: boolean;
  swipe: ReturnType<typeof useSwipePager<HTMLDivElement>>;
  ackAndNext: () => void;
  prev: () => void;
  jump: (i: number) => void;
};

/**
 * Phone paging for QuestionsStep (2026-10-07 one-per-screen; 2026-10-09
 * swipe + slide, CEO "화면 넘기는 식으로 앱처럼").
 *
 * The "검토했음 · 다음" button ticks the current question and moves on, as
 * before. A swipe NEVER ticks anything: it pages forward only from a question
 * that is already ticked (going back and forth over answered screens), and
 * otherwise springs back with a hint. A tick is what the audit row records as
 * "(acknowledged)"; an accidental gesture must not sign it. Swiping back from
 * the first question returns to setup, like the "이전" button.
 */
function useQuestionsPager(args: {
  /** The screen element that slides and takes the swipe. */
  screenRef: React.RefObject<HTMLDivElement | null>;
  enabled: boolean;
  acks: Record<number, boolean>;
  setAcks: (f: (prev: Record<number, boolean>) => Record<number, boolean>) => void;
  submitting: boolean;
  onBack?: () => void;
}): QuestionsPager {
  const { screenRef, enabled, acks, setAcks, submitting, onBack } = args;
  const [nav, setNav] = useState<{ cur: number; dir: PagerDir }>({ cur: 0, dir: 1 });
  const [blockedAt, setBlockedAt] = useState<number | null>(null);
  const cur = nav.cur;
  const curAcked = cur < REVIEW_IDX && !!acks[QUESTIONS[cur].n];

  const go = (to: number, dir: PagerDir) => {
    setBlockedAt(null);
    setNav({ cur: to, dir });
  };
  const ackAndNext = () => {
    const n = QUESTIONS[cur].n;
    setAcks((p) => ({ ...p, [n]: true }));
    go(cur + 1, 1);
  };
  const prev = () => (cur === 0 ? onBack?.() : go(cur - 1, -1));

  const swipe = useSwipePager(screenRef, {
    enabled: enabled && !submitting,
    onNext: () => {
      if (curAcked) {
        go(cur + 1, 1);
        return "moved";
      }
      if (cur < REVIEW_IDX) setBlockedAt(cur);
      return "blocked"; // the review screen starts only from its button
    },
    onPrev: () => {
      if (cur === 0 && !onBack) return "blocked";
      prev();
      return "moved";
    },
  });
  useSlideIn(screenRef, cur, nav.dir, { enabled, animateOnMount: true });

  return {
    cur,
    swipeBlocked: blockedAt === cur && !curAcked,
    swipe,
    ackAndNext,
    prev,
    jump: (i) => go(i, -1),
  };
}

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
  /**
   * Phone only (2026-10-07, CEO "너무 웹사이트야"; 2026-10-09 swipe): one
   * question per screen, sliding horizontally, with a segmented progress
   * bar, a last review screen and a sticky action bar ("검토했음 · 다음" →
   * "진입 시계 시작"). At md and up the list renders as before. The route
   * page opts in; the modals keep the list.
   */
  pagedOnPhone?: boolean;
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
    pagedOnPhone = false,
  } = props;
  const screenRef = useRef<HTMLDivElement>(null);
  const pager = useQuestionsPager({
    screenRef,
    enabled: pagedOnPhone,
    acks,
    setAcks,
    submitting,
    onBack,
  });
  const { cur } = pager;
  const onReview = pagedOnPhone && cur === REVIEW_IDX;
  const ackCount = QUESTIONS.filter((q) => acks[q.n]).length;

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
      {!bare && <SectionLabel n={2} title="질문 7개" />}
      {pagedOnPhone && <PhoneProgress cur={cur} acks={acks} ackCount={ackCount} />}
      <div
        ref={screenRef}
        {...pager.swipe}
        className={pagedOnPhone ? PAGER_SCREEN_CLASS : undefined}
        data-testid="questions-screen"
      >
        <ol className="space-y-5">
          {QUESTIONS.map((q, i) => (
            <QuestionItem
              key={q.n}
              q={q}
              hint={hints?.[q.n]}
              hiddenOnPhone={pagedOnPhone && i !== cur}
              acked={!!acks[q.n]}
              answer={answers[q.n] ?? ""}
              setAcks={setAcks}
              setAnswers={setAnswers}
            />
          ))}
        </ol>
        {onReview && (
          <ReviewScreen acks={acks} answers={answers} onJump={pager.jump} />
        )}
        {/* Under the question it refers to, not below the screen's height. */}
        {pager.swipeBlocked && (
          <p
            role="status"
            aria-live="polite"
            className="mt-4 ml-[34px] pl-5 text-pq-mono-sm text-[var(--pq-bronze)] tracking-[0.06em] md:hidden"
            data-testid="questions-swipe-hint"
          >
            검토했음을 눌러야 다음 질문으로 넘어갑니다.
          </p>
        )}
      </div>

      <div
        className={`flex-wrap gap-3 justify-between pt-3 border-t border-[var(--pq-ivory-line-soft)] ${
          pagedOnPhone ? "hidden md:flex" : "flex"
        }`}
      >
        {/* Paged on a phone, the action bar's "이전" is the only back
            control; this one (→ setup) and the start button below are the
            md+ footer. */}
        {onBack ? (
          <button
            type="button"
            onClick={onBack}
            disabled={submitting}
            className={`px-4 py-2 text-pq-mono-sm text-[var(--pq-ivory-dim)] hover:text-[var(--pq-bronze)] ${
              pagedOnPhone ? "hidden md:inline-block" : ""
            }`}
            data-testid="questions-footer-back"
          >
            ← 이전
          </button>
        ) : (
          <span />
        )}
        <button
          type="button"
          onClick={onStart}
          disabled={!allAcked || submitting}
          aria-disabled={!allAcked || submitting}
          className={`pq-ink-btn-bronze inline-flex items-center gap-2 px-5 py-2 text-pq-mono-sm disabled:opacity-30 disabled:cursor-not-allowed ${
            pagedOnPhone && onBack ? "ml-auto" : ""
          }`}
          data-testid="questions-start"
        >
          {submitting ? "시작하는 중…" : "진입 시계 시작"}
          <Gavel className="h-3.5 w-3.5" />
        </button>
      </div>
      {!allAcked && (
        <p
          aria-live="polite"
          role="status"
          className={`text-pq-mono-sm text-[var(--pq-ivory-faint)] text-right tracking-[0.06em] ${
            pagedOnPhone && !onReview ? "hidden md:block" : ""
          }`}
        >
          {`모든 질문에 ✓ 표시해야 진입 시계가 시작됩니다 (${ackCount}/${QUESTIONS.length}).`}
        </p>
      )}

      {pagedOnPhone && (
        <PhoneActionBar testId="questions-pager">
          <button
            type="button"
            onClick={pager.prev}
            disabled={submitting || (cur === 0 && !onBack)}
            className="min-h-[48px] px-4 text-[15px] text-[var(--pq-ivory-dim)] disabled:opacity-30"
            data-testid="questions-prev"
          >
            이전
          </button>
          {onReview ? (
            <button
              type="button"
              onClick={onStart}
              disabled={!allAcked || submitting}
              aria-disabled={!allAcked || submitting}
              className="pq-ink-btn-bronze flex min-h-[48px] flex-1 items-center justify-center gap-2 text-[15px] disabled:opacity-30 disabled:cursor-not-allowed"
              data-testid="questions-start-phone"
            >
              {submitting ? "시작하는 중…" : "진입 시계 시작"}
              <Gavel className="h-4 w-4" />
            </button>
          ) : (
            <button
              type="button"
              onClick={pager.ackAndNext}
              disabled={submitting}
              className="pq-ink-btn-bronze flex min-h-[48px] flex-1 items-center justify-center text-[15px]"
              data-testid="questions-next"
            >
              검토했음 · 다음
            </button>
          )}
        </PhoneActionBar>
      )}
    </section>
  );
}

function QuestionItem(props: {
  q: (typeof QUESTIONS)[number];
  hint: string | undefined;
  hiddenOnPhone: boolean;
  acked: boolean;
  answer: string;
  setAcks: (f: (prev: Record<number, boolean>) => Record<number, boolean>) => void;
  setAnswers: (f: (prev: Record<number, string>) => Record<number, string>) => void;
}) {
  const { q, hint, hiddenOnPhone, acked, answer, setAcks, setAnswers } = props;
  return (
    <li
      className={`border-l-2 border-[var(--pq-ivory-line)] pl-5 hover:border-[var(--pq-bronze)] transition-colors ${
        hiddenOnPhone ? "hidden md:block" : ""
      }`}
      data-testid={`question-${q.n}`}
    >
      <div className="flex items-baseline gap-3">
        <span
          className="font-mono text-pq-eyebrow uppercase tracking-[0.22em] text-[var(--pq-bronze)] mt-0.5"
          style={{ minWidth: 18 }}
        >
          {String(q.n).padStart(2, "0")}
        </span>
        <div className="flex-1 space-y-1">
          {/* 2026-10-07 (CEO "영문 라벨도 한글로"): only the Korean line
              is shown. q.en stays in the data — it still labels each
              answer in the devil_advocate audit blob sent to /start. */}
          <p className="font-serif text-pq-deck leading-snug text-[var(--pq-ivory)]">
            {q.ko}
          </p>
          {hint && (
            <p
              className="font-serif text-pq-caption leading-snug"
              // 0.85 alpha — 12px text must clear the project's WCAG
              // ladder (globals.css: alpha 0.45 ≈ 3.99:1 is large-text
              // only; bronze 0.66 ≈ 3.65:1 failed AA for small text).
              style={{ color: "rgba(184,149,106,0.85)" }}
              data-testid={`persona-hint-${q.n}`}
            >
              {hint}
            </p>
          )}
        </div>
      </div>
      <div className="mt-3 ml-[34px] flex flex-col gap-2">
        <input
          value={answer}
          onChange={(e) =>
            setAnswers((prev) => ({ ...prev, [q.n]: e.target.value }))
          }
          placeholder="(선택) 한 줄로 답해보라"
          aria-label={`질문 ${q.n} 답: ${q.ko}`}
          className="w-full bg-transparent border-b border-[rgba(245,240,232,0.1)] py-1.5 text-pq-body-sm font-serif outline-none focus:border-[var(--pq-bronze)] text-[var(--pq-ivory)]"
        />
        <label className="inline-flex items-center gap-2 cursor-pointer text-pq-mono-sm text-[var(--pq-ivory-dim)] hover:text-[var(--pq-bronze)]">
          <input
            type="checkbox"
            checked={acked}
            onChange={(e) =>
              setAcks((prev) => ({ ...prev, [q.n]: e.target.checked }))
            }
            className="accent-[var(--pq-bronze)]"
          />
          검토했음
        </label>
      </div>
    </li>
  );
}

/**
 * Phone screen height: the viewport between the app bar and the bottom nav,
 * less the step chrome above the screen (section label + progress, ~9rem)
 * and the sticky action bar (~5rem), so each step reads as one screen and
 * the bar sits at the bottom edge. Below md only; md+ is untouched.
 */
export const PAGER_SCREEN_CLASS =
  "max-md:min-h-[calc(100dvh_-_var(--pq-topbar-height)_-_var(--pq-bottomnav-clearance)_-_14rem)]";

function PhoneProgress({
  cur,
  acks,
  ackCount,
}: {
  cur: number;
  acks: Record<number, boolean>;
  ackCount: number;
}) {
  return (
    <div className="md:hidden" data-testid="questions-progress">
      <div className="flex items-center justify-between text-[13px] text-[var(--pq-ivory-dim)]">
        <span>
          {cur === REVIEW_IDX ? "마지막 확인" : `질문 ${cur + 1} / ${QUESTIONS.length}`}
        </span>
        <span>
          검토 {ackCount} / {QUESTIONS.length}
        </span>
      </div>
      <div
        className="mt-2 flex gap-1"
        role="progressbar"
        aria-label="검토한 질문"
        aria-valuemin={0}
        aria-valuemax={QUESTIONS.length}
        aria-valuenow={ackCount}
      >
        {QUESTIONS.map((q, i) => (
          <span
            key={q.n}
            data-testid={`progress-seg-${q.n}`}
            data-state={acks[q.n] ? "acked" : i === cur ? "current" : "todo"}
            className={`h-[3px] flex-1 transition-colors ${
              acks[q.n]
                ? "bg-[var(--pq-bronze)]"
                : i === cur
                  ? "bg-[var(--pq-ivory-mid)]"
                  : "bg-[var(--pq-ivory-line)]"
            }`}
          />
        ))}
      </div>
    </div>
  );
}

/** Last phone screen: every question with what the user wrote, tap to revisit. */
function ReviewScreen({
  acks,
  answers,
  onJump,
}: {
  acks: Record<number, boolean>;
  answers: Record<number, string>;
  onJump: (i: number) => void;
}) {
  return (
    <div className="space-y-4 md:hidden" data-testid="questions-review">
      <p className="font-serif text-pq-deck leading-snug text-[var(--pq-ivory)]">
        일곱 개의 질문을 지나왔습니다.
      </p>
      <Caption>
        고칠 답이 있으면 질문을 누르세요. 시작하면 아래 답이 이 멈춤의 기록에
        그대로 남습니다.
      </Caption>
      <ol className="space-y-2">
        {QUESTIONS.map((q, i) => {
          const ans = (answers[q.n] ?? "").trim();
          return (
            <li key={q.n}>
              <button
                type="button"
                onClick={() => onJump(i)}
                className="w-full border-l-2 border-[var(--pq-ivory-line)] py-1.5 pl-4 text-left"
                data-testid={`review-jump-${q.n}`}
              >
                <span className="block font-serif text-pq-body-sm leading-snug text-[var(--pq-ivory-mid)]">
                  <span className="mr-2 font-mono text-pq-eyebrow tracking-[0.22em] text-[var(--pq-bronze)]">
                    {String(q.n).padStart(2, "0")}
                  </span>
                  {q.ko}
                </span>
                <span
                  className={`mt-1 block line-clamp-2 text-pq-mono-sm ${
                    acks[q.n] ? "text-[var(--pq-ivory)]" : "text-[var(--pq-ivory-faint)]"
                  }`}
                >
                  {acks[q.n] ? ans || "답 없이 검토함" : "검토 전"}
                </span>
              </button>
            </li>
          );
        })}
      </ol>
    </div>
  );
}

/**
 * Phone-only action bar, sticky above the bottom nav (whose own padding
 * already carries the home-indicator inset, so the offset adds the same
 * env() term). Sticky, not fixed: it rides at the bottom edge while its
 * step is on screen and settles at the end of the step otherwise, and no
 * transformed ancestor can detach it. Hidden at md and up.
 */
export function PhoneActionBar({
  children,
  testId,
}: {
  children: React.ReactNode;
  testId?: string;
}) {
  return (
    <div
      className="sticky z-30 -mx-4 flex gap-3 border-t border-[var(--pq-ivory-line)] bg-[var(--pq-ink)] px-4 py-3 md:hidden"
      style={{
        bottom: "calc(var(--pq-bottomnav-height) + env(safe-area-inset-bottom, 0px))",
      }}
      data-testid={testId}
    >
      {children}
    </div>
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
          title={isReady ? "결정의 시간" : "진입 시계"}
        />
      )}

      <div className="rounded-[2px] border border-[var(--pq-ivory-line)] bg-[rgba(255,255,255,0.02)] p-6 md:p-8 space-y-6">
        {/* Trade summary */}
        <div className="flex flex-wrap items-baseline gap-x-6 gap-y-2">
          <span className="font-mono text-pq-mono-sm text-[var(--pq-bronze)]">
            {sideLabelKo(reflection.intended_side)}
          </span>
          <span
            className="font-serif text-pq-avatar text-[var(--pq-ivory)]"
            style={{ letterSpacing: "-0.01em" }}
          >
            {reflection.intended_ticker_name || reflection.intended_ticker}
          </span>
          {reflection.intended_shares !== null && (
            <span className="font-mono text-pq-body-sm text-[rgba(245,240,232,0.6)]">
              {reflection.intended_shares}주
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
          <div className="mt-3 text-pq-eyebrow text-[var(--pq-ivory-faint)]">
            {isReady ? "기다림 끝" : "남은 시간"}
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
              <span className="font-mono text-pq-eyebrow text-[var(--pq-bronze)] mr-2">
                연장됨
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
          className="inline-flex items-center gap-2 px-4 py-2 text-pq-mono-sm text-[var(--pq-ivory-dim)] hover:text-[var(--pq-error)]"
        >
          <X className="h-3.5 w-3.5" />
          취소
        </button>
        <button
          type="button"
          onClick={onProceed}
          disabled={!isReady || submitting}
          className="pq-ink-btn-bronze inline-flex items-center gap-2 px-5 py-2 text-pq-mono-sm disabled:opacity-30 disabled:cursor-not-allowed"
        >
          <Check className="h-3.5 w-3.5" />
          {isReady ? "진행" : "기다리는 중…"}
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
  commit = "none",
}: {
  reflection: Reflection;
  /** Outcome of the host's record commit; "none" when the host has no commit. */
  commit?: "none" | "recorded" | "failed";
  onReset: () => void;
  /** Override the reset CTA label (modal: "닫기"; page: "새로 시작"). */
  resetLabel?: string;
  bare?: boolean;
}) {
  const t = useT();
  const proceeded = reflection.status === "proceeded";
  const d = (k: string, params?: Record<string, string>) =>
    t(`preTrade.done.${k}`, params);
  return (
    <section className="space-y-6">
      {!bare && (
        <SectionLabel
          n={4}
          title={proceeded ? "기록 완료" : "취소"}
        />
      )}
      <div className="rounded-[2px] border border-[var(--pq-ivory-line)] bg-[rgba(255,255,255,0.02)] p-6 md:p-8 space-y-4">
        {/* 2026-09-19: this screen — the product's single most important
            confirmation moment — rendered entirely in English under the ko
            locale, while the cancelled branch beside it was already Korean.
            Both branches now go through useT (house rule: EN mono eyebrow,
            localised heading + body). The bronze accent was an <em>, which
            renders italic — banned product-wide (CEO 2026-06-15) — so it is
            a <span> now. */}
        <div
          className="font-serif text-pq-avatar text-[var(--pq-ivory)]"
          style={{ letterSpacing: "-0.01em" }}
        >
          {proceeded ? (
            <>
              {d("proceededHead")}{" "}
              <span style={{ color: "var(--pq-bronze)" }}>
                {d("proceededHeadAccent")}
              </span>
            </>
          ) : (
            <>
              {d("cancelledHead")}{" "}
              <span style={{ color: "var(--pq-bronze)" }}>
                {d("cancelledHeadAccent")}
              </span>
            </>
          )}
        </div>
        <p className="font-serif text-pq-body leading-relaxed text-[var(--pq-ivory-mid)]">
          {proceeded
            ? `${
                commit === "recorded"
                  ? d("recorded")
                  : commit === "failed"
                    ? d("recordFailed")
                    : d("stampedOnly")
              } ${d("noOrderTail")}`
            : d("cancelledBody")}
        </p>
        <div className="border-t border-[var(--pq-ivory-line-soft)] pt-3 flex flex-wrap gap-x-6 gap-y-1 text-pq-caption font-mono text-[var(--pq-ivory-dim)]">
          <span>
            {sideLabelKo(reflection.intended_side)} ·{" "}
            {reflection.intended_ticker_name || reflection.intended_ticker}
          </span>
          {reflection.intended_shares !== null && (
            <span>{d("shares", { n: String(reflection.intended_shares) })}</span>
          )}
          <span>
            {proceeded
              ? `진행 ${formatTime(reflection.proceeded_at)}`
              : `취소 ${formatTime(reflection.cancelled_at)}`}
          </span>
        </div>
      </div>

      <div className="flex justify-end">
        <button
          type="button"
          onClick={onReset}
          className="inline-flex items-center gap-2 px-5 py-2 text-pq-mono-sm text-[var(--pq-ivory-mid)] border border-[rgba(245,240,232,0.15)] hover:border-[var(--pq-bronze)] hover:text-[var(--pq-bronze)]"
        >
          <RotateCcw className="h-3.5 w-3.5" />
          {resetLabel ?? "새로 시작"}
        </button>
      </div>
    </section>
  );
}

/* ─── Shared helpers ─────────────────────────────────────────────────────── */

/**
 * Korean-only side label ("진입" / "정리") for an internal Side or a wire
 * value. `@/lib/pre-trade` sideLabel still renders the bilingual
 * "Long Entry · 진입" form other surfaces use; the pre-trade and journal
 * screens show Korean only (CEO 2026-10-07 "영문 라벨도 한글로").
 */
export function sideLabelKo(wireOrSide: string | null | undefined): string {
  const s: Side | null =
    wireOrSide === "ENTRY" || wireOrSide === "EXIT"
      ? wireOrSide
      : sideFromWire(wireOrSide);
  return s ? SIDE_LABEL_KO[s] : "—";
}

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
          className="block text-pq-eyebrow text-[var(--pq-ivory-faint)] mb-1"
        >
          {label}
        </label>
        {children}
      </div>
    );
  }
  return (
    <label className="block">
      <span className="block text-pq-eyebrow text-[var(--pq-ivory-faint)] mb-1">
        {label}
      </span>
      {children}
    </label>
  );
}

export function extendReasonLabel(reason: string): string {
  switch (reason) {
    case "fomc_30min":
      return "FOMC 발표가 ±30분 안에 있어 진입 시계가 5분으로 연장되었습니다.";
    case "high_vix":
      return "VIX > 30 고변동성 구간이라 진입 시계가 5분으로 연장되었습니다.";
    case "big_move_1h":
      return "이 종목이 최근 1시간 동안 ±5% 이상 움직여 진입 시계가 5분으로 연장되었습니다.";
    default:
      return `진입 시계가 연장되었습니다 (${reason}).`;
  }
}

export function formatTime(iso: string | null): string {
  if (!iso) return "—";
  try {
    // Backend timestamps are naive UTC (no "Z"); parse them as UTC, not local.
    return new Date(parseUtcSafe(iso)).toLocaleTimeString("en-GB", {
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return "—";
  }
}
