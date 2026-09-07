"use client";

/**
 * /pre-trade — Pre-Trade Friction (Feature 6), direct-entry route.
 *
 * Self-imposed cooldown + 7-question reflection before the user fires the
 * broker order in their existing app. We DO NOT place the trade here — the
 * backend `/proceed` endpoint just stamps "user finished thinking" on a row.
 * Compliance posture from routes/pre_trade.py:
 * "정보 제공용 UX 입니다. 거래 권유가 아닙니다."
 *
 * The reflection cycle (questions / cooldown / proceed / cancel / terminal)
 * lives in `@/components/pre-trade/pre-trade-friction-core` and is SHARED
 * with <PreTradeFrictionModal /> (inline at the moment of action in Portfolio
 * v2 Add/Trim). This page owns ONLY the Setup step — the modal prefills it.
 * Single source of truth; no duplicated step logic.
 *
 * Flow (route):
 *   1. Setup — ticker / side / shares / rationale (≥50 chars)
 *   2. Devil's Advocate — 7 reflective questions (shared)
 *   3. Cooldown — REMOVED 2026-05-22 (CEO "2분 없애"): backend cooldown is 0,
 *      so the cycle goes straight from the 7 questions to Ready/Proceed (shared)
 *   4. Ready  — Proceed (open) | Cancel (abort) (shared)
 *   5. Terminal — Proceeded or Cancelled (shared)
 *
 * Tone: v3 — Vantablack + Bronze + Playfair UPRIGHT (no italic headings, in
 * lock-step with the detail-page redesign). POSITIVE / NEGATIVE / NEUTRAL only.
 *
 * Side labels: internal Side enum ("ENTRY"/"EXIT") → legacy wire format via
 * `@/lib/pre-trade`. The DB schema / audit row stay untouched.
 */

import { useCallback, useState } from "react";
import { ChevronRight } from "lucide-react";
import { ErrorBoundary } from "@/components/ui/error-boundary";
import { Caption, FootSignature, RuledKicker } from "@/components/ui/editorial";
import {
  type Side,
  SIDE_LABEL_EN,
  SIDE_LABEL_KO,
  sideLabel,
} from "@/lib/pre-trade";
import {
  MIN_RATIONALE_CHARS,
  QUESTIONS,
  Field,
  SectionLabel,
  QuestionsStep,
  CooldownStep,
  TerminalStep,
  usePreTradeCycle,
} from "@/components/pre-trade/pre-trade-friction-core";

export default function PreTradePage() {
  // Step 1 — setup (owned by this route page)
  const [ticker, setTicker] = useState("");
  const [side, setSide] = useState<Side>("ENTRY");
  const [sharesText, setSharesText] = useState("");
  const [rationale, setRationale] = useState("");

  // Step 2 — questions
  const [acks, setAcks] = useState<Record<number, boolean>>({});
  const [answers, setAnswers] = useState<Record<number, string>>({});

  const allAcked = QUESTIONS.every((q) => acks[q.n]);
  const rationaleOk = rationale.trim().length >= MIN_RATIONALE_CHARS;
  const setupOk = ticker.trim().length > 0 && rationaleOk;

  const cycle = usePreTradeCycle({
    side,
    ticker,
    sharesText,
    rationale,
    acks,
    answers,
  });

  const advanceToQuestions = useCallback(() => {
    if (!setupOk) return;
    cycle.setPhase("questions");
  }, [setupOk, cycle]);

  const reset = useCallback(() => {
    setTicker("");
    setSide("ENTRY");
    setSharesText("");
    setRationale("");
    setAcks({});
    setAnswers({});
    cycle.reset();
  }, [cycle]);

  return (
    <ErrorBoundary>
      <div className="space-y-10 pb-12">
        {/* ── Editorial header (v3 lock-in: Playfair UPRIGHT). Layout mounts
              a single DisclaimerBanner — pages MUST NOT mount their own. */}
        <header className="space-y-3">
          <RuledKicker>Signature &middot; Pre-Trade Checklist</RuledKicker>
          <h1
            className="mt-3 font-display text-[var(--pq-ivory)]"
            style={{
              fontWeight: 500,
              fontSize: "var(--pq-text-h1-dash)",
              lineHeight: 1.06,
              letterSpacing: "-0.022em",
            }}
          >
            매수 앞에 놓인{" "}
            <span style={{ color: "var(--pq-bronze)" }}>일곱 번의 멈춤.</span>
          </h1>
          {/* This caption DENIES the very thing FORBIDDEN_DIRECTIVE_TERMS
              bans, which means it has to quote that word in the negative.
              The marker is the documented escape (.githooks/pre-commit:136);
              the guard scans added lines, it cannot read the negation. */}
          <Caption className="mt-3 max-w-[560px]">
            진입 결정 앞에 놓인 7개의 관문. 당신의 논리를 스스로 검증하는
            자리입니다 — 조언이 아니라 규율입니다.{/* // legal-ok */}
          </Caption>
        </header>

        {cycle.phase === "setup" && (
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

        {cycle.phase === "questions" && (
          <QuestionsStep
            acks={acks} setAcks={setAcks}
            answers={answers} setAnswers={setAnswers}
            allAcked={allAcked}
            submitting={cycle.submitting}
            onBack={() => cycle.setPhase("setup")}
            onStart={cycle.startCooldown}
          />
        )}

        {cycle.phase === "cooldown" && cycle.reflection && (
          <CooldownStep
            reflection={cycle.reflection}
            submitting={cycle.submitting}
            onProceed={cycle.proceed}
            onCancel={cycle.cancel}
          />
        )}

        {cycle.phase === "terminal" && cycle.reflection && (
          <TerminalStep
            reflection={cycle.reflection}
            onReset={reset}
          />
        )}

        {/* Single foot signature (v3 convention). Layout owns the global
            disclaimer above; this footer is the editorial sign-off. */}
        <FootSignature />
      </div>
    </ErrorBoundary>
  );
}

/* ─── Step 1 — Setup (route-only; modal prefills instead) ─────────────────── */

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
            className="w-full bg-transparent border-b border-[rgba(245,240,232,0.15)] py-2 font-mono text-pq-lead uppercase outline-none focus:border-[var(--pq-bronze)] text-[var(--pq-ivory)]"
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
                className={`px-4 py-2 text-pq-eyebrow uppercase tracking-[0.2em] transition-colors ${
                  side === s
                    ? "bg-[rgba(245,240,232,0.10)] border border-[var(--pq-ivory)] text-[var(--pq-ivory)]"
                    : "border border-[rgba(245,240,232,0.15)] text-[rgba(245,240,232,0.65)] hover:border-[rgba(245,240,232,0.45)]"
                }`}
              >
                {SIDE_LABEL_EN[s]} · {SIDE_LABEL_KO[s]}
              </button>
            ))}
          </div>
        </Field>
        <Field label="Shares (optional)" htmlFor="pre-trade-shares">
          <input
            id="pre-trade-shares"
            type="number"
            inputMode="decimal"
            min="0"
            step="any"
            value={sharesText}
            onChange={(e) => setSharesText(e.target.value)}
            placeholder="0"
            className="w-full bg-transparent border-b border-[rgba(245,240,232,0.15)] py-2 font-mono text-pq-lead outline-none focus:border-[var(--pq-bronze)] text-[var(--pq-ivory)]"
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
        <div className="mt-1 text-pq-mono-sm text-[rgba(245,240,232,0.45)] tracking-[0.06em]">
          {rationaleOk
            ? <span className="text-[var(--pq-bronze)]">✓ {rationale.trim().length} chars</span>
            : <span>{remaining} chars more required ({rationale.trim().length}/{MIN_RATIONALE_CHARS})</span>}
        </div>
      </Field>

      <div className="flex flex-col items-end gap-2 pt-2">
        {!canAdvance && (
          <p
            aria-live="polite"
            role="status"
            className="text-pq-mono-sm text-[rgba(245,240,232,0.5)] tracking-[0.06em]"
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
          className="pq-ink-btn-bronze inline-flex items-center gap-2 px-5 py-2 text-pq-mono-sm uppercase tracking-[0.22em] disabled:opacity-30 disabled:cursor-not-allowed"
        >
          Continue · 7 questions
          <ChevronRight className="h-3.5 w-3.5" />
        </button>
      </div>
    </section>
  );
}
