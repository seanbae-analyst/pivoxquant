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
 *   1. Setup — ticker / side / shares / rationale (≥ MIN_RATIONALE_CHARS = 10 chars)
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
 *
 * 2026-10-05 — Setup ticker picking:
 *   - The ticker field is the shared <TickerSearch /> (`/api/search`, names
 *     only — live while MARKET_DATA_DISPLAY_ENABLED is off). Free text still
 *     works; a pick just writes the canonical exchange ticker back.
 *   - EXIT lists the holdings recorded on Portfolio as one-tap chips, and a
 *     typed ticker that is not among them gets a non-blocking note (the user
 *     may hold it without having recorded it). Shares/avg cost only — no
 *     price is read or rendered here.
 *   - After a proceeded pause, a one-line pointer to /journal/import: this
 *     route records nothing to the book, so the fill is journaled there and
 *     a buy can be linked back to this pause on approval
 *     (services/pre_trade/link.py).
 */

import { useCallback, useMemo, useState } from "react";
import Link from "next/link";
import useSWR from "swr";
import { ChevronRight } from "lucide-react";
import { ErrorBoundary } from "@/components/ui/error-boundary";
import { useT } from "@/lib/locale";
import { Caption, FootSignature, RuledKicker } from "@/components/ui/editorial";
import {
  type Side,
  SIDE_LABEL_EN,
  SIDE_LABEL_KO,
  sideLabel,
  isHeldTicker,
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
import { RelatedObservationNotes } from "@/components/pre-trade/related-observation-notes";
import { TickerSearch } from "@/components/shared/ticker-search";
import type { BackendPositionRow } from "@/components/portfolio/types";
import { PORTFOLIO_POSITIONS } from "@/lib/endpoints";
import { fetcher } from "@/lib/hooks";
import { displayTicker, normalizeTicker } from "@/lib/format";

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
          {/* Phone: the app bar already says 멈춤 — keep only the caption. */}
          <div className="hidden md:block">
            <RuledKicker>Signature &middot; Pre-Trade Checklist</RuledKicker>
          </div>
          <h1
            className="mt-3 hidden font-display text-[var(--pq-ivory)] md:block"
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

        {/* The user's own past observations on this symbol — read-only, and
            placed before the questions so it is context for the answers
            (docs/design/observation-notes_2026-09-22.md §4-1). Renders
            nothing when there are none. */}
        {cycle.phase === "questions" && (
          <RelatedObservationNotes ticker={ticker} />
        )}

        {cycle.phase === "questions" && (
          <QuestionsStep
            acks={acks} setAcks={setAcks}
            answers={answers} setAnswers={setAnswers}
            allAcked={allAcked}
            submitting={cycle.submitting}
            onBack={() => cycle.setPhase("setup")}
            onStart={cycle.startCooldown}
            pagedOnPhone
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
            commit={cycle.commit}
            reflection={cycle.reflection}
            onReset={reset}
          />
        )}

        {cycle.phase === "terminal" && cycle.reflection?.status === "proceeded" && (
          <ImportHint />
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
  const t = useT();

  return (
    <section className="space-y-6">
      <SectionLabel n={1} title="The Trade · 거래 개요" />
      <div className="grid grid-cols-1 md:grid-cols-[1fr_auto_1fr] gap-4">
        <Field label="Ticker" htmlFor="pre-trade-ticker">
          <TickerSearch
            id="pre-trade-ticker"
            value={ticker}
            onChange={setTicker}
            onPick={(r) => setTicker(r.ticker)}
            ariaLabel="Ticker"
            autoFocus
            inputClassName="w-full bg-transparent border-b border-[rgba(245,240,232,0.15)] py-2 font-mono text-pq-lead uppercase outline-none focus:border-[var(--pq-bronze)] text-[var(--pq-ivory)]"
            inputStyle={{ letterSpacing: "0.04em" }}
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
                    : "border border-[rgba(245,240,232,0.15)] text-[var(--pq-ivory-mid)] hover:border-[rgba(245,240,232,0.45)]"
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

      {side === "EXIT" && <HeldPicker ticker={ticker} setTicker={setTicker} />}

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
        <div className="mt-1 text-pq-mono-sm text-[var(--pq-ivory-faint)] tracking-[0.06em]">
          {rationaleOk
            ? (
              <span className="text-[var(--pq-bronze)]">
                {t("preTrade.charsOk", { n: String(rationale.trim().length) })}
              </span>
            )
            : (
              <span>
                {t("preTrade.charsMore", {
                  remaining: String(remaining),
                  n: String(rationale.trim().length),
                  min: String(MIN_RATIONALE_CHARS),
                })}
              </span>
            )}
        </div>
      </Field>

      <div className="flex flex-col items-end gap-2 pt-2">
        {!canAdvance && (
          <p
            aria-live="polite"
            role="status"
            className="text-pq-mono-sm text-[var(--pq-ivory-faint)] tracking-[0.06em]"
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

/* ─── EXIT — pick from the holdings recorded on Portfolio ─────────────────── */

function HeldPicker({ ticker, setTicker }: { ticker: string; setTicker: (s: string) => void }) {
  const t = useT();
  // One-shot read (no polling): only shares/name are used, never a price.
  const { data, error } = useSWR<{ positions?: BackendPositionRow[] }>(
    PORTFOLIO_POSITIONS,
    fetcher,
    { revalidateOnFocus: false, revalidateIfStale: false },
  );
  const rows = useMemo(
    () => (data?.positions ?? []).filter((r) => (r.shares ?? 0) > 0),
    [data],
  );
  // Loading or failed: say nothing — the free-text field still works.
  if (!data || error) return null;

  const typed = ticker.trim().length > 0;
  return (
    <div className="space-y-2">
      <div className="text-pq-eyebrow uppercase tracking-[0.2em] text-[var(--pq-ivory-faint)]">
        {t("preTrade.setup.heldLabel")}
      </div>
      {rows.length === 0 ? (
        <p className="text-pq-mono-sm text-[var(--pq-ivory-faint)] tracking-[0.06em]">
          {t("preTrade.setup.heldEmpty")}
        </p>
      ) : (
        <div className="flex flex-wrap gap-2">
          {rows.map((r) => {
            const sym = r.symbol ?? r.ticker;
            const active = normalizeTicker(sym) === normalizeTicker(ticker);
            return (
              <button
                key={String(r.id)}
                type="button"
                onClick={() => setTicker(sym)}
                aria-pressed={active}
                className={`px-3 py-1.5 text-pq-mono-sm tracking-[0.06em] transition-colors ${
                  active
                    ? "bg-[rgba(245,240,232,0.10)] border border-[var(--pq-ivory)] text-[var(--pq-ivory)]"
                    : "border border-[rgba(245,240,232,0.15)] text-[var(--pq-ivory-mid)] hover:border-[rgba(245,240,232,0.45)]"
                }`}
              >
                {displayTicker(sym, r.name)}
                <span className="ml-2 text-[var(--pq-ivory-faint)]">
                  {t("preTrade.setup.heldShares", { n: String(r.shares) })}
                </span>
              </button>
            );
          })}
        </div>
      )}
      {typed && rows.length > 0 && !isHeldTicker(ticker, rows) && (
        <p
          role="status"
          aria-live="polite"
          className="text-pq-mono-sm text-[var(--pq-ivory-faint)] tracking-[0.06em]"
        >
          {t("preTrade.setup.notHeld")}
        </p>
      )}
    </div>
  );
}

/* ─── After a proceeded pause — where the fill gets journaled ─────────────── */

function ImportHint() {
  const t = useT();
  return (
    <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3 border-t border-[var(--pq-ivory-line-soft)] pt-4">
      <p className="font-serif text-pq-body leading-relaxed text-[var(--pq-ivory-mid)] max-w-[560px]">
        {t("preTrade.done.importHint")}
      </p>
      <Link
        href="/journal/import?tab=image"
        className="inline-flex items-center gap-2 self-start md:self-auto px-5 py-2 text-pq-mono-sm uppercase tracking-[0.22em] text-[var(--pq-ivory-mid)] border border-[rgba(245,240,232,0.15)] hover:border-[var(--pq-bronze)] hover:text-[var(--pq-bronze)]"
      >
        {t("preTrade.done.importCta")}
        <ChevronRight className="h-3.5 w-3.5" />
      </Link>
    </div>
  );
}
