"use client";

/**
 * <ResearchForm /> — the same five fields for every stock.
 *
 * docs/design/research-notes_2026-10-15.md §2. Most people buy on someone
 * else's conclusion (a report, a video, a friend); the form names the few
 * things worth checking yourself, in plain words, and nothing more:
 *
 *   1. 내가 보는 이유 1~3개 (필수)    2. 이게 보이면 틀린 것
 *   + 어디서 알게 됐나 · 다시 볼 날 (1·3·6개월)
 *   더 적기(접힘): 이 회사는 뭘로 돈을 버나 · 가장 큰 위험 하나 ·
 *                 직접 확인한 숫자 (비우면 "안 봄")
 *
 * 2026-10-25 (CEO "적어야 할게 너무 많다"): the form opens on two fields —
 * the reason (scored on the review day) and what would prove it wrong. The
 * other three stay, folded; "뭘로 돈을 버나" is no longer required.
 *
 * We fill in nothing about the stock — no figures, no news, no per-stock
 * guidance (자본시장법 §6 투자자문 경계 · FMP §2.2.2). Placeholders are
 * generic shapes of an answer, not hints about any company. The form has no
 * edit path after saving (a record you can rewrite later stops being a
 * mirror); it can be deleted.
 */
import * as React from "react";
import { ApiError } from "@/lib/api";
import { createResearchNote } from "@/lib/hooks";
import { displayName } from "@/lib/format";
import {
  INFO_SOURCE_LABEL,
  INFO_SOURCE_ORDER,
  RESEARCH_MAX_BUSINESS,
  RESEARCH_MAX_INVALIDATION,
  RESEARCH_MAX_NUMBERS,
  RESEARCH_MAX_RISK,
  RESEARCH_MAX_THESES,
  RESEARCH_MAX_THESIS,
  REVIEW_MONTH_OPTIONS,
  type ReviewMonths,
} from "@/lib/research";
import { Caption, FieldLabel } from "@/components/ui/editorial";
import { TickerSearch, type TickerSearchResult } from "@/components/shared/ticker-search";
import type { ResearchInfoSource, ResearchNote } from "@/lib/types";

const INPUT =
  "w-full rounded-[var(--pq-radius-card)] border border-[var(--pq-ivory-line)] bg-transparent px-3 py-2 text-pq-body-sm text-[var(--pq-ivory)] outline-none placeholder:text-[var(--pq-ivory-faint)] focus:border-[var(--pq-bronze)]";

export interface ResearchFormProps {
  /** Pre-picked symbol (e.g. from a /portfolio row). */
  defaultTicker?: { ticker: string; name?: string } | null;
  surface?: "journal" | "portfolio" | "pre_trade";
  onSaved: (note: ResearchNote) => void;
  onCancel?: () => void;
}

function Chip({
  on,
  onClick,
  children,
}: {
  on: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      aria-pressed={on}
      onClick={onClick}
      className="min-h-[36px] rounded-full border px-3 text-pq-body-sm transition-colors"
      style={{
        borderColor: on ? "var(--pq-bronze)" : "var(--pq-ivory-line)",
        background: on ? "rgba(var(--pq-bronze-rgb), 0.14)" : "transparent",
        color: on ? "var(--pq-bronze-light)" : "var(--pq-ivory-dim)",
      }}
    >
      {children}
    </button>
  );
}

function Step({ n, label, optional, children }: { n: number; label: string; optional?: boolean; children: React.ReactNode }) {
  return (
    <div className="mt-6">
      <div className="flex items-baseline gap-2">
        <span className="tabular-nums text-pq-body-sm font-semibold text-[var(--pq-bronze)]">{n}</span>
        <span className="text-pq-body font-semibold text-[var(--pq-ivory)]">{label}</span>
        {optional && <span className="text-pq-caption text-[var(--pq-ivory-faint)]">선택</span>}
      </div>
      <div className="mt-2">{children}</div>
    </div>
  );
}

export function ResearchForm({ defaultTicker, surface = "journal", onSaved, onCancel }: ResearchFormProps) {
  const [picked, setPicked] = React.useState<{ ticker: string; name: string } | null>(
    defaultTicker ? { ticker: defaultTicker.ticker, name: defaultTicker.name ?? "" } : null,
  );
  const [query, setQuery] = React.useState("");
  const [business, setBusiness] = React.useState("");
  const [theses, setTheses] = React.useState<string[]>([""]);
  const [invalidation, setInvalidation] = React.useState("");
  const [risk, setRisk] = React.useState("");
  const [numbers, setNumbers] = React.useState("");
  const [source, setSource] = React.useState<ResearchInfoSource | null>(null);
  const [months, setMonths] = React.useState<ReviewMonths>(3);
  const [submitting, setSubmitting] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  const filledTheses = theses.map((t) => t.trim()).filter(Boolean);
  const canSubmit = Boolean(picked) && filledTheses.length > 0 && !submitting;

  const onPick = (r: TickerSearchResult) => {
    setPicked({ ticker: r.ticker, name: r.name });
    setQuery("");
  };

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!canSubmit || !picked) return;
    setSubmitting(true);
    setError(null);
    try {
      const res = await createResearchNote({
        ticker: picked.ticker,
        business: business.trim() || undefined,
        theses: filledTheses,
        invalidation: invalidation.trim() || undefined,
        risk: risk.trim() || undefined,
        numbers: numbers.trim() || undefined,
        info_source: source,
        review_months: months,
        surface,
      });
      onSaved(res.note);
    } catch (err) {
      setError(err instanceof ApiError && err.message ? err.message : "저장하지 못했어요. 다시 시도해 주세요.");
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={submit} data-testid="research-form" aria-label="리서치 양식">
      {/* 종목 */}
      <div>
        <FieldLabel tone="muted">종목</FieldLabel>
        {picked ? (
          <div className="mt-2 flex items-center gap-3">
            <span className="text-pq-body font-semibold text-[var(--pq-ivory)]">
              {displayName(picked.ticker, picked.name)}
            </span>
            <button
              type="button"
              onClick={() => setPicked(null)}
              className="text-pq-caption text-[var(--pq-bronze-light)] underline-offset-4 hover:underline"
            >
              바꾸기
            </button>
          </div>
        ) : (
          <div className="mt-2">
            <TickerSearch
              value={query}
              onChange={setQuery}
              onPick={onPick}
              ariaLabel="종목 검색"
              placeholder="종목명 또는 티커"
              showPickedName={false}
              inputClassName={INPUT}
            />
          </div>
        )}
      </div>

      <Step n={1} label="내가 보는 이유">
        <ul className="list-none space-y-2 p-0">
          {theses.map((t, i) => (
            <li key={i} className="flex items-center gap-2">
              <input
                aria-label={`이유 ${i + 1}`}
                value={t}
                maxLength={RESEARCH_MAX_THESIS}
                onChange={(e) => setTheses((cur) => cur.map((x, j) => (j === i ? e.target.value : x)))}
                placeholder={i === 0 ? "예: 다음 분기에 마진이 회복된다" : "또 하나 (선택)"}
                className={INPUT}
              />
              {theses.length > 1 && (
                <button
                  type="button"
                  aria-label={`이유 ${i + 1} 빼기`}
                  onClick={() => setTheses((cur) => cur.filter((_, j) => j !== i))}
                  className="shrink-0 px-2 text-[var(--pq-ivory-faint)] hover:text-[var(--pq-ivory)]"
                >
                  ×
                </button>
              )}
            </li>
          ))}
        </ul>
        {theses.length < RESEARCH_MAX_THESES && (
          <button
            type="button"
            onClick={() => setTheses((cur) => [...cur, ""])}
            className="mt-2 text-pq-caption text-[var(--pq-bronze-light)] underline-offset-4 hover:underline"
          >
            + 이유 하나 더 ({theses.length}/{RESEARCH_MAX_THESES})
          </button>
        )}
        <Caption className="mt-1">다시 볼 날, 이 줄마다 맞았는지 스스로 채점해요.</Caption>
      </Step>

      <Step n={2} label="이게 보이면 틀린 것" optional>
        <input
          aria-label="이게 보이면 틀린 것"
          value={invalidation}
          maxLength={RESEARCH_MAX_INVALIDATION}
          onChange={(e) => setInvalidation(e.target.value)}
          placeholder="예: 두 분기 연속 마진이 줄어든다"
          className={INPUT}
        />
      </Step>

      {/* Folded (2026-10-25): worth writing, not worth blocking on. */}
      <details className="mt-6" data-testid="research-more">
        <summary className="pq-hit cursor-pointer select-none text-pq-body-sm text-[var(--pq-bronze-light)]">
          더 적기 (선택) · 뭘로 돈을 버나 · 가장 큰 위험 · 확인한 숫자
        </summary>
        <Step n={3} label="이 회사는 뭘로 돈을 버나" optional>
          <input
            aria-label="이 회사는 뭘로 돈을 버나"
            value={business}
            maxLength={RESEARCH_MAX_BUSINESS}
            onChange={(e) => setBusiness(e.target.value)}
            placeholder="예: 구독료로 번다"
            className={INPUT}
          />
        </Step>

        <Step n={4} label="가장 큰 위험 하나" optional>
          <input
            aria-label="가장 큰 위험 하나"
            value={risk}
            maxLength={RESEARCH_MAX_RISK}
            onChange={(e) => setRisk(e.target.value)}
            placeholder="예: 매출이 한 고객에 몰려 있다"
            className={INPUT}
          />
        </Step>

        <Step n={5} label="직접 확인한 숫자" optional>
          <textarea
            aria-label="직접 확인한 숫자"
            value={numbers}
            maxLength={RESEARCH_MAX_NUMBERS}
            onChange={(e) => setNumbers(e.target.value)}
            rows={2}
            placeholder="예: 최근 3년 매출 추이를 사업보고서에서 봄"
            className={INPUT}
          />
          <Caption className="mt-1">본 만큼만 적어요. 안 봤으면 비워 두면 「안 봄」으로 남아요.</Caption>
        </Step>
      </details>

      <div className="mt-6">
        <FieldLabel tone="muted">어디서 알게 됐나</FieldLabel>
        <div className="mt-2 flex flex-wrap gap-2" role="group" aria-label="어디서 알게 됐나">
          {INFO_SOURCE_ORDER.map((s) => (
            <Chip key={s} on={source === s} onClick={() => setSource((cur) => (cur === s ? null : s))}>
              {INFO_SOURCE_LABEL[s]}
            </Chip>
          ))}
        </div>
      </div>

      <div className="mt-5">
        <FieldLabel tone="muted">다시 볼 날</FieldLabel>
        <div className="mt-2 flex flex-wrap gap-2" role="group" aria-label="다시 볼 날">
          {REVIEW_MONTH_OPTIONS.map((m) => (
            <Chip key={m} on={months === m} onClick={() => setMonths(m)}>
              {m}개월 뒤
            </Chip>
          ))}
        </div>
      </div>

      {error && (
        <p role="alert" className="mt-4 text-pq-caption" style={{ color: "var(--pq-negative)" }}>
          {error}
        </p>
      )}

      <div className="mt-6 flex flex-wrap items-center gap-3">
        <button
          type="submit"
          disabled={!canSubmit}
          aria-disabled={!canSubmit}
          className="pq-ink-btn-bronze inline-flex items-center px-5 py-2 text-pq-mono-sm disabled:cursor-not-allowed disabled:opacity-30"
        >
          {submitting ? "저장하는 중" : "저장"}
        </button>
        {onCancel && (
          <button type="button" onClick={onCancel} className="pq-hit text-pq-caption text-[var(--pq-ivory-dim)] hover:text-[var(--pq-ivory)]">
            취소
          </button>
        )}
      </div>
      <Caption className="mt-2">
        저장한 뒤에는 고칠 수 없어요 — 그때의 생각 그대로 남겨 두고, 다시 볼 날 채점해요. 지울 수는 있어요.
      </Caption>
    </form>
  );
}

export default ResearchForm;
