"use client";

/**
 * /pre-trade — Pre-Trade Friction (Feature 6).
 *
 * Self-imposed cooldown + 7-question reflection before the user fires
 * the broker order in their existing app. We DO NOT place the trade
 * here — the backend `/proceed` endpoint just stamps "user finished
 * thinking" on a row. Compliance posture from routes/pre_trade.py:
 * "정보 제공용 UX 입니다. 거래 권유가 아닙니다."
 *
 * Flow:
 *   1. Setup — ticker / side / shares / rationale (≥50 chars)
 *   2. Devil's Advocate — 7 reflective questions (DepositionTeaser parity)
 *   3. Cooldown — 2 min default, 5 min when FOMC ±30m / VIX>30 / >5%/h move
 *   4. Ready  — Proceed (open) | Cancel (abort)
 *   5. Terminal — Proceeded or Cancelled
 *
 * Tone: v3 — Vantablack + Bronze + Playfair italic. POSITIVE / NEGATIVE /
 * NEUTRAL only. No directional advice tokens anywhere in the surfaced copy.
 *
 * Side labels: the legacy wire format on the backend stays untouched for
 * data compat. The UI uses an internal Side enum ("ENTRY" / "EXIT") and
 * renders "Long Entry · 진입" / "Position Exit · 정리" via sideLabel().
 * See `@/lib/pre-trade` for the translation boundary.
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { Gavel, ChevronRight, RotateCcw, Check, X, AlertCircle } from "lucide-react";
import { apiFetch, ApiError } from "@/lib/api";
import { API } from "@/lib/endpoints";
import { ErrorBoundary } from "@/components/ui/error-boundary";
import { Caption, FootSignature, RuledKicker } from "@/components/ui/editorial";
import {
  type Side,
  SIDE_LABEL_EN,
  SIDE_LABEL_KO,
  sideLabel,
  sideToWire,
} from "@/lib/pre-trade";

const MIN_RATIONALE_CHARS = 50;

// 7 reflective questions — verbatim parity with the landing
// DepositionTeaser. Listed once here so future copy edits stay
// in lock-step with the marketing surface.
const QUESTIONS: readonly { n: number; en: string; ko: string }[] = [
  { n: 1, en: "What is your thesis in one sentence?", ko: "한 문장으로 진입 논리를 말해보라." },
  { n: 2, en: "What would prove you wrong?", ko: "어떤 사실이 확인되면 당신이 틀린 것인가?" },
  { n: 3, en: "How does this fit your persona allocation?", ko: "현재 페르소나 배분에 부합하는가?" },
  { n: 4, en: "Is this inside your drift band?", ko: "당신의 Drift 허용 범위 안에 있는가?" },
  { n: 5, en: "Size: is this a normal position for you?", ko: "평소 크기인가? 이례적이라면 왜인가?" },
  { n: 6, en: "Have you seen a similar setup before — and what happened?", ko: "비슷한 국면에서 결과는?" },
  { n: 7, en: "If it drops 20% tomorrow — are you adding or cutting?", ko: "내일 -20% 라면 더 담는가, 잘라내는가?" },
] as const;

interface Reflection {
  id: number;
  intended_ticker: string;
  /**
   * 회사명 (선택). Backend `models/pre_trade_reflection.to_dict()` 는 현재
   * intended_ticker 만 직렬화하므로 이 필드는 forward-compat 용. 백엔드가
   * 추후 `intended_ticker_name` 을 추가하면 자동 노출되고, 그 전까지는
   * `intended_ticker` 로 폴백한다 — 회귀 위험 0.
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
  seconds_remaining: number;
  status: "pending" | "ready" | "proceeded" | "cancelled" | "expired";
}

interface StartResponse {
  ok: true;
  disclaimer: string;
  reflection: Reflection;
}

type Phase = "setup" | "questions" | "cooldown" | "terminal";

export default function PreTradePage() {
  const [phase, setPhase] = useState<Phase>("setup");

  // Step 1 — setup
  const [ticker, setTicker] = useState("");
  const [side, setSide] = useState<Side>("ENTRY");
  const [sharesText, setSharesText] = useState("");
  const [rationale, setRationale] = useState("");

  // Step 2 — questions (each tracks acknowledged + optional one-line answer)
  const [acks, setAcks] = useState<Record<number, boolean>>({});
  const [answers, setAnswers] = useState<Record<number, string>>({});

  // Step 3+ — server state
  const [reflection, setReflection] = useState<Reflection | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const allAcked = QUESTIONS.every((q) => acks[q.n]);
  const rationaleOk = rationale.trim().length >= MIN_RATIONALE_CHARS;
  const setupOk = ticker.trim().length > 0 && rationaleOk;

  /* ── Step 1 → 2 ── */
  const advanceToQuestions = useCallback(() => {
    if (!setupOk) return;
    setPhase("questions");
  }, [setupOk]);

  /* ── Step 2 → 3 (POST /start) ── */
  const startCooldown = useCallback(async () => {
    if (submitting) return;
    setSubmitting(true);
    try {
      // Stitch the seven question acknowledgements into the
      // devil_advocate field so the audit row carries exactly what the
      // user signed off on. Rationale gets the user's primary thesis
      // text alone (matches MIN_RATIONALE_CHARS server validation).
      const ackBlob = QUESTIONS.map((q) => {
        const ans = (answers[q.n] || "").trim();
        return ans
          ? `Q${q.n} ${q.en}\n→ ${ans}`
          : `Q${q.n} ${q.en}\n→ (acknowledged)`;
      }).join("\n\n");

      const sharesNum = sharesText.trim() === "" ? null : Number(sharesText);
      const body: Record<string, unknown> = {
        ticker: ticker.trim().toUpperCase(),
        // Serialize internal Side ("ENTRY"/"EXIT") to the legacy wire
        // format that routes/pre_trade.py expects. Keeps DB schema and
        // audit row stable while removing the literal from the UI.
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
      setReflection(res.reflection);
      setPhase(res.reflection.status === "proceeded" || res.reflection.status === "cancelled"
        ? "terminal" : "cooldown");
    } catch (err) {
      const msg = err instanceof ApiError
        ? (err.message || "Could not start cooldown")
        : "Could not start cooldown";
      toast.error(msg);
    } finally {
      setSubmitting(false);
    }
  }, [submitting, ticker, side, sharesText, rationale, answers]);

  /* ── Step 3 polling — refresh seconds_remaining every second ── */
  const reflectionId = reflection?.id;
  useEffect(() => {
    if (phase !== "cooldown" || !reflectionId) return;

    // Local clock decrement is cheap and matches what the user sees.
    // We re-fetch from the server every 5s as a belt-and-suspenders
    // sync so a clock drift can't unlock /proceed prematurely.
    const localTick = window.setInterval(() => {
      setReflection((r) => {
        if (!r) return r;
        const next = Math.max(0, r.seconds_remaining - 1);
        return { ...r, seconds_remaining: next, status: next > 0 ? "pending" : "ready" };
      });
    }, 1000);

    const serverSync = window.setInterval(async () => {
      try {
        const r = await apiFetch<StartResponse>(API.preTrade.status(reflectionId));
        setReflection(r.reflection);
        if (r.reflection.status === "proceeded" || r.reflection.status === "cancelled") {
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

  /* ── Proceed / Cancel ── */
  const proceed = useCallback(async () => {
    if (!reflection) return;
    if (reflection.status !== "ready") return;
    setSubmitting(true);
    try {
      const r = await apiFetch<StartResponse>(API.preTrade.proceed(reflection.id), { method: "POST" });
      setReflection(r.reflection);
      setPhase("terminal");
      toast.success("Reflection marked complete. Now place the order in your broker.");
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : "Could not proceed";
      toast.error(msg || "Could not proceed");
    } finally {
      setSubmitting(false);
    }
  }, [reflection]);

  const cancel = useCallback(async () => {
    if (!reflection) return;
    setSubmitting(true);
    try {
      const r = await apiFetch<StartResponse>(API.preTrade.cancel(reflection.id), { method: "POST" });
      setReflection(r.reflection);
      setPhase("terminal");
      toast.success("Cancelled.");
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : "Could not cancel";
      toast.error(msg || "Could not cancel");
    } finally {
      setSubmitting(false);
    }
  }, [reflection]);

  const reset = useCallback(() => {
    setPhase("setup");
    setTicker("");
    setSide("ENTRY");
    setSharesText("");
    setRationale("");
    setAcks({});
    setAnswers({});
    setReflection(null);
  }, []);

  return (
    <ErrorBoundary>
      <div className="space-y-10 pb-12">
        {/* ── Editorial header (v3 lock-in: Playfair + italic accent,
              matches /alerts "When the desk *spoke.*", /portfolio
              "Your *book.*", /risk "Risk *board.*"). Layout already
              mounts a single DisclaimerBanner — pages MUST NOT mount
              their own.  */}
        <header className="space-y-3">
          <RuledKicker>Signature &middot; Pre-Trade Checklist</RuledKicker>
          <h1
            className="mt-3 font-display text-[var(--pq-ivory)]"
            style={{
              fontWeight: 500,
              fontSize: "clamp(34px, 4.6vw, 52px)",
              lineHeight: 1.06,
              letterSpacing: "-0.022em",
            }}
          >
            Seven questions{" "}
            <span style={{ fontStyle: "italic", color: "var(--pq-bronze)" }}>
              before every trade.
            </span>
          </h1>
          <Caption className="mt-3 max-w-[560px]">
            진입 결정 앞에 서는 7개의 관문. 당신의 논리를 스스로 검증할
            기회다 — 조언이 아니라 규율이다.
          </Caption>
        </header>

        {phase === "setup" && (
          <SetupStep
            ticker={ticker} setTicker={setTicker}
            side={side} setSide={setSide}
            sharesText={sharesText} setSharesText={setSharesText}
            rationale={rationale} setRationale={setRationale}
            rationaleOk={rationaleOk}
            canAdvance={setupOk}
            onNext={advanceToQuestions}
          />
        )}

        {phase === "questions" && (
          <QuestionsStep
            acks={acks} setAcks={setAcks}
            answers={answers} setAnswers={setAnswers}
            allAcked={allAcked}
            submitting={submitting}
            onBack={() => setPhase("setup")}
            onStart={startCooldown}
          />
        )}

        {phase === "cooldown" && reflection && (
          <CooldownStep
            reflection={reflection}
            submitting={submitting}
            onProceed={proceed}
            onCancel={cancel}
          />
        )}

        {phase === "terminal" && reflection && (
          <TerminalStep
            reflection={reflection}
            onReset={reset}
          />
        )}

        {/* ── Single foot signature (v3 convention). Layout owns the
              global disclaimer above; this footer is the editorial
              sign-off — fleuron + italic byline, no separate caveats
              repeated per phase. */}
        <FootSignature />
      </div>
    </ErrorBoundary>
  );
}

/* ─── Step 1 ─────────────────────────────────────────────────────────── */

function SetupStep(props: {
  ticker: string; setTicker: (s: string) => void;
  side: Side; setSide: (s: Side) => void;
  sharesText: string; setSharesText: (s: string) => void;
  rationale: string; setRationale: (s: string) => void;
  rationaleOk: boolean;
  canAdvance: boolean;
  onNext: () => void;
}) {
  const { ticker, setTicker, side, setSide, sharesText, setSharesText, rationale, setRationale, rationaleOk, canAdvance, onNext } = props;
  const remaining = Math.max(0, MIN_RATIONALE_CHARS - rationale.trim().length);

  return (
    <section className="space-y-6">
      <SectionLabel n={1} title="The Trade · 거래 개요" />
      <div className="grid grid-cols-1 md:grid-cols-[1fr_auto_1fr] gap-4">
        <Field label="Ticker" htmlFor="pre-trade-ticker">
          <input
            id="pre-trade-ticker"
            value={ticker}
            onChange={(e) => setTicker(e.target.value)}
            placeholder="AAPL · 005930.KS"
            autoFocus
            className="w-full bg-transparent border-b border-[rgba(245,240,232,0.15)] py-2 font-mono text-[15px] uppercase outline-none focus:border-[var(--pq-bronze)] text-[var(--pq-ivory)]"
            style={{ letterSpacing: "0.04em" }}
          />
        </Field>
        <Field label="Side">
          <div className="flex gap-2 mt-1">
            {(["ENTRY", "EXIT"] as const).map((s) => (
              <button
                key={s}
                type="button"
                onClick={() => setSide(s)}
                aria-label={sideLabel(s)}
                className={`px-4 py-2 text-[10px] uppercase tracking-[0.2em] transition-colors ${
                  side === s
                    ? "bg-[var(--pq-bronze)] text-[var(--pq-ink)]"
                    : "border border-[rgba(245,240,232,0.15)] text-[rgba(245,240,232,0.65)] hover:border-[var(--pq-bronze)]"
                }`}
              >
                {SIDE_LABEL_EN[s]} · {SIDE_LABEL_KO[s]}
              </button>
            ))}
          </div>
        </Field>
        <Field label="Shares (optional)" htmlFor="pre-trade-shares">
          {/* Bug #7 fix (2026-05-09 deep bug hunt): no min attr meant
              users could submit -5 shares; backend rejected with a toast
              error (services/pre_trade/friction.py:81), no inline hint.
              `min="0"` + `step` give native browser validation. */}
          <input
            id="pre-trade-shares"
            type="number"
            inputMode="decimal"
            min="0"
            step="any"
            value={sharesText}
            onChange={(e) => setSharesText(e.target.value)}
            placeholder="0"
            className="w-full bg-transparent border-b border-[rgba(245,240,232,0.15)] py-2 font-mono text-[15px] outline-none focus:border-[var(--pq-bronze)] text-[var(--pq-ivory)]"
          />
        </Field>
      </div>

      <Field label={`Thesis · 한 문단 (${MIN_RATIONALE_CHARS}자 이상)`} htmlFor="pre-trade-thesis">
        <textarea
          id="pre-trade-thesis"
          value={rationale}
          onChange={(e) => setRationale(e.target.value)}
          rows={5}
          placeholder="왜 지금 이 종목을 이 방향으로 들어가는가? 한 문단으로 정직하게."
          className="w-full bg-transparent border border-[rgba(245,240,232,0.15)] rounded-[2px] p-3 text-sm leading-relaxed outline-none focus:border-[var(--pq-bronze)] text-[var(--pq-ivory)] font-serif"
          style={{ resize: "vertical" }}
        />
        <div className="mt-1 text-[11px] text-[rgba(245,240,232,0.45)] tracking-[0.06em]">
          {rationaleOk
            ? <span className="text-[var(--pq-bronze)]">✓ {rationale.trim().length} chars</span>
            : <span>{remaining} chars more required ({rationale.trim().length}/{MIN_RATIONALE_CHARS})</span>}
        </div>
      </Field>

      {/* Bug #6 (P2): button stays `disabled` until both ticker + thesis
          are filled, but earlier UI gave no hint *why* the CTA wouldn't
          fire. Inline aria-live hint surfaces the exact missing piece(s)
          so the user does not click into silence. */}
      <div className="flex flex-col items-end gap-2 pt-2">
        {!canAdvance && (
          <p
            aria-live="polite"
            role="status"
            className="text-[11px] text-[rgba(245,240,232,0.5)] tracking-[0.06em]"
          >
            {ticker.trim().length === 0 && !rationaleOk
              ? "Ticker와 Thesis를 채워야 진행합니다."
              : ticker.trim().length === 0
                ? "Ticker를 입력해야 진행합니다."
                : `Thesis ${MIN_RATIONALE_CHARS}자 이상 필요합니다.`}
          </p>
        )}
        <button
          type="button"
          onClick={onNext}
          disabled={!canAdvance}
          aria-disabled={!canAdvance}
          className="pq-ink-btn-bronze inline-flex items-center gap-2 px-5 py-2 text-[11px] uppercase tracking-[0.22em] disabled:opacity-30 disabled:cursor-not-allowed"
        >
          Continue · 7 questions
          <ChevronRight className="h-3.5 w-3.5" />
        </button>
      </div>
    </section>
  );
}

/* ─── Step 2 ─────────────────────────────────────────────────────────── */

function QuestionsStep(props: {
  acks: Record<number, boolean>;
  setAcks: (f: (prev: Record<number, boolean>) => Record<number, boolean>) => void;
  answers: Record<number, string>;
  setAnswers: (f: (prev: Record<number, string>) => Record<number, string>) => void;
  allAcked: boolean;
  submitting: boolean;
  onBack: () => void;
  onStart: () => void;
}) {
  const { acks, setAcks, answers, setAnswers, allAcked, submitting, onBack, onStart } = props;
  return (
    <section className="space-y-6">
      <SectionLabel n={2} title="The Deposition · 7개 질문" />
      <ol className="space-y-5">
        {QUESTIONS.map((q) => (
          <li
            key={q.n}
            className="border-l-2 border-[var(--pq-ivory-line)] pl-5 hover:border-[var(--pq-bronze)] transition-colors"
          >
            <div className="flex items-baseline gap-3">
              <span
                className="font-mono text-[10px] uppercase tracking-[0.22em] text-[var(--pq-bronze)] mt-0.5"
                style={{ minWidth: 18 }}
              >
                {String(q.n).padStart(2, "0")}
              </span>
              <div className="flex-1 space-y-1">
                <p className="font-serif text-[17px] leading-snug text-[var(--pq-ivory)]" style={{ fontStyle: "italic" }}>
                  {q.en}
                </p>
                <p className="font-serif text-[13px] text-[rgba(245,240,232,0.55)]">
                  {q.ko}
                </p>
              </div>
            </div>
            <div className="mt-3 ml-[34px] flex flex-col gap-2">
              <input
                value={answers[q.n] ?? ""}
                onChange={(e) => setAnswers((prev) => ({ ...prev, [q.n]: e.target.value }))}
                placeholder="(optional) 한 줄로 답해보라"
                className="w-full bg-transparent border-b border-[rgba(245,240,232,0.1)] py-1.5 text-[13px] font-serif outline-none focus:border-[var(--pq-bronze)] text-[var(--pq-ivory)]"
              />
              <label className="inline-flex items-center gap-2 cursor-pointer text-[11px] tracking-[0.18em] uppercase text-[rgba(245,240,232,0.55)] hover:text-[var(--pq-bronze)]">
                <input
                  type="checkbox"
                  checked={!!acks[q.n]}
                  onChange={(e) => setAcks((prev) => ({ ...prev, [q.n]: e.target.checked }))}
                  className="accent-[var(--pq-bronze)]"
                />
                I considered this · 검토했음
              </label>
            </div>
          </li>
        ))}
      </ol>

      <div className="flex flex-wrap gap-3 justify-between pt-3 border-t border-[var(--pq-ivory-line-soft)]">
        <button
          type="button"
          onClick={onBack}
          disabled={submitting}
          className="px-4 py-2 text-[11px] uppercase tracking-[0.18em] text-[rgba(245,240,232,0.55)] hover:text-[var(--pq-bronze)]"
        >
          ← Back
        </button>
        <button
          type="button"
          onClick={onStart}
          disabled={!allAcked || submitting}
          aria-disabled={!allAcked || submitting}
          className="pq-ink-btn-bronze inline-flex items-center gap-2 px-5 py-2 text-[11px] uppercase tracking-[0.22em] disabled:opacity-30 disabled:cursor-not-allowed"
        >
          {submitting ? "Starting…" : "Start cooldown · 진입 시계"}
          <Gavel className="h-3.5 w-3.5" />
        </button>
      </div>
      {!allAcked && (
        <p
          aria-live="polite"
          role="status"
          className="text-[11px] text-[rgba(245,240,232,0.5)] text-right tracking-[0.06em]"
        >
          {`모든 질문에 ✓ 표시해야 진입 시계가 시작됩니다 (${QUESTIONS.filter((q) => acks[q.n]).length}/${QUESTIONS.length}).`}
        </p>
      )}
    </section>
  );
}

/* ─── Step 3 ─────────────────────────────────────────────────────────── */

function CooldownStep({
  reflection, submitting, onProceed, onCancel,
}: {
  reflection: Reflection;
  submitting: boolean;
  onProceed: () => void;
  onCancel: () => void;
}) {
  const isReady = reflection.status === "ready" || reflection.seconds_remaining === 0;
  const totalSec = useMemo(() => {
    if (!reflection.cooldown_started_at || !reflection.cooldown_ends_at) return 120;
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
      <SectionLabel n={3} title={isReady ? "Ready · 결정의 시간" : "Cooldown · 진입 시계"} />

      <div className="rounded-[2px] border border-[var(--pq-ivory-line)] bg-[rgba(255,255,255,0.02)] p-6 md:p-8 space-y-6">
        {/* Trade summary */}
        <div className="flex flex-wrap items-baseline gap-x-6 gap-y-2">
          <span className="font-mono text-[11px] uppercase tracking-[0.22em] text-[var(--pq-bronze)]">
            {sideLabel(reflection.intended_side)}
          </span>
          <span
            className="font-serif text-[28px] text-[var(--pq-ivory)]"
            style={{ letterSpacing: "-0.01em" }}
          >
            {reflection.intended_ticker_name || reflection.intended_ticker}
          </span>
          {reflection.intended_shares !== null && (
            <span className="font-mono text-[13px] text-[rgba(245,240,232,0.6)]">
              {reflection.intended_shares} shares
            </span>
          )}
        </div>

        {/* Big timer */}
        <div className="text-center py-4">
          <div
            className="font-mono tabular-nums text-[var(--pq-ivory)]"
            style={{ fontSize: "clamp(48px, 9vw, 96px)", lineHeight: 1, letterSpacing: "-0.02em" }}
          >
            {String(mm).padStart(2, "0")}:{String(ss).padStart(2, "0")}
          </div>
          <div className="mt-3 text-[10px] tracking-[0.22em] uppercase text-[rgba(245,240,232,0.45)]">
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
            <p className="text-[12px] leading-relaxed text-[rgba(245,240,232,0.75)]">
              <span className="font-mono text-[10px] tracking-[0.18em] uppercase text-[var(--pq-bronze)] mr-2">
                Extended
              </span>
              {extendReasonLabel(reflection.auto_extended_reason)}
            </p>
          </div>
        )}

        {/* Rationale recap */}
        <div className="border-t border-[var(--pq-ivory-line-soft)] pt-4">
          <Caption>Your thesis</Caption>
          <p className="mt-2 font-serif text-[14px] leading-relaxed italic text-[rgba(245,240,232,0.78)]">
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
          className="inline-flex items-center gap-2 px-4 py-2 text-[11px] uppercase tracking-[0.18em] text-[rgba(245,240,232,0.55)] hover:text-red-400"
        >
          <X className="h-3.5 w-3.5" />
          Cancel · 취소
        </button>
        <button
          type="button"
          onClick={onProceed}
          disabled={!isReady || submitting}
          className="pq-ink-btn-bronze inline-flex items-center gap-2 px-5 py-2 text-[11px] uppercase tracking-[0.22em] disabled:opacity-30 disabled:cursor-not-allowed"
        >
          <Check className="h-3.5 w-3.5" />
          {isReady ? "I am ready · 진행" : "Wait…"}
        </button>
      </div>
    </section>
  );
}

/* ─── Step 4 ─────────────────────────────────────────────────────────── */

function TerminalStep({
  reflection, onReset,
}: {
  reflection: Reflection;
  onReset: () => void;
}) {
  const proceeded = reflection.status === "proceeded";
  return (
    <section className="space-y-6">
      <SectionLabel
        n={4}
        title={proceeded ? "Proceeded · 기록 완료" : "Cancelled · 취소"}
      />
      <div className="rounded-[2px] border border-[var(--pq-ivory-line)] bg-[rgba(255,255,255,0.02)] p-6 md:p-8 space-y-4">
        <div
          className="font-serif text-[28px] text-[var(--pq-ivory)]"
          style={{ letterSpacing: "-0.01em" }}
        >
          {proceeded ? (
            <>You did the work. <em style={{ color: "var(--pq-bronze)" }}>Now place the order.</em></>
          ) : (
            <>Step away. <em style={{ color: "var(--pq-bronze)" }}>The desk waits.</em></>
          )}
        </div>
        <p className="font-serif text-[14px] leading-relaxed text-[rgba(245,240,232,0.65)]">
          {proceeded
            ? "We stamped your reflection. PivoxQuant does not place trades — open your broker (Alpaca, KIS, etc.) and submit the order yourself."
            : "취소되었습니다. 다음 진입 결정 때 다시 7개 질문을 거치세요."}
        </p>
        <div className="border-t border-[var(--pq-ivory-line-soft)] pt-3 flex flex-wrap gap-x-6 gap-y-1 text-[12px] font-mono text-[rgba(245,240,232,0.55)]">
          <span>{sideLabel(reflection.intended_side)} · {reflection.intended_ticker_name || reflection.intended_ticker}</span>
          {reflection.intended_shares !== null && <span>{reflection.intended_shares} shares</span>}
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
          className="inline-flex items-center gap-2 px-5 py-2 text-[11px] uppercase tracking-[0.22em] text-[rgba(245,240,232,0.65)] border border-[rgba(245,240,232,0.15)] hover:border-[var(--pq-bronze)] hover:text-[var(--pq-bronze)]"
        >
          <RotateCcw className="h-3.5 w-3.5" />
          New checklist · 새로 시작
        </button>
      </div>
    </section>
  );
}

/* ─── Helpers ────────────────────────────────────────────────────────── */

function SectionLabel({ n, title }: { n: number; title: string }) {
  // Hairline divider above + bronze 2-digit eyebrow + Playfair section
  // title — same convention as /alerts ledger rows ("Total / Unread /
  // Today / This week" hairline strip).
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

function Field({
  label,
  htmlFor,
  children,
}: {
  label: string;
  htmlFor?: string;
  children: React.ReactNode;
}) {
  // a11y P2 2026-05-03: support explicit htmlFor + id pattern for SR
  // compatibility. Falls back to implicit-wrap when no id supplied
  // (e.g. Side field that wraps a button group, not an input).
  if (htmlFor) {
    return (
      <div className="block">
        <label
          htmlFor={htmlFor}
          className="block text-[10px] uppercase tracking-[0.22em] text-[rgba(245,240,232,0.5)] mb-1"
        >
          {label}
        </label>
        {children}
      </div>
    );
  }
  return (
    <label className="block">
      <span className="block text-[10px] uppercase tracking-[0.22em] text-[rgba(245,240,232,0.5)] mb-1">
        {label}
      </span>
      {children}
    </label>
  );
}

function extendReasonLabel(reason: string): string {
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

function formatTime(iso: string | null): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" });
  } catch {
    return "—";
  }
}
