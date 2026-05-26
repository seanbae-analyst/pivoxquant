"use client";

/**
 * /journal — Decision Journal (Pre-Trade reflection feed).
 *
 * "User as CFO": a reverse-chronological feed of the user's OWN pre-trade
 * reflections — the rationale + 7-question devil's-advocate snapshot they
 * wrote before adding/trimming a position, plus whether they proceeded or
 * cancelled. The point is self-review: "look back at how I decided."
 *
 * Read-only. The backend never executed a trade — each row is a "user
 * finished thinking" record (services/pre_trade/friction.py). This page is
 * INFORMATIONAL, not a recommendation and not a trade-execution log.
 *
 * Compliance posture (KCMA §17 / 자본시장법):
 *   - intended_side BUY/SELL is NEVER surfaced raw. Rendered through
 *     `@/lib/pre-trade` sideLabel as "Long Entry · 진입" / "Position Exit · 정리".
 *   - No 추천/조언 language. DisclaimerBanner mounted at the page head.
 *
 * Tone: v3 — Vantablack + Bronze + Playfair UPRIGHT (no italic headings).
 * KR colour convention: proceeded = neutral ivory, cancelled = dimmed.
 * Carmine/indigo reserved for price direction, not used for status here.
 */

import { useState, useCallback } from "react";
import Link from "next/link";
import { Briefcase, NotebookPen, ChevronDown } from "lucide-react";
import { useLocale } from "@/lib/locale";
import { usePreTradeJournal } from "@/lib/hooks";
import { displayName, normalizeTicker } from "@/lib/format";
import { sideLabel } from "@/lib/pre-trade";
import { relativeTime } from "@/lib/relative-time";
import { ErrorBoundary } from "@/components/ui/error-boundary";
import {
  RuledKicker,
  Caption,
  EditorialHead,
  FootSignature,
} from "@/components/ui/editorial";
import type { PreTradeReflection } from "@/lib/types";

/* ────────────────────────────────────────────────────────────────────────
 * Helpers
 * ────────────────────────────────────────────────────────────────────── */

/** When the entry was created — proceeded/cancelled stamp else cooldown start. */
export function entryTimestamp(r: PreTradeReflection): string | null {
  return r.proceeded_at ?? r.cancelled_at ?? r.cooldown_started_at ?? null;
}

/** Absolute KST-rendered date for the inline metadata row. */
export function absoluteDate(iso: string | null): string {
  if (!iso) return "";
  const needsUtc = !iso.endsWith("Z") && !/[+-]\d{2}:?\d{2}$/.test(iso);
  const d = new Date(needsUtc ? iso + "Z" : iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleDateString("ko-KR", {
    year: "numeric",
    month: "long",
    day: "numeric",
    // Pin to KST so the date doesn't roll back/forward a day for viewers in
    // other timezones (2026-05-26 F#4 fix). The UTC-guard above ensures naive
    // backend timestamps are treated as UTC before zone conversion.
    timeZone: "Asia/Seoul",
  });
}

export type StatusKind = "proceeded" | "cancelled" | "pending";

export function statusKind(r: PreTradeReflection): StatusKind {
  if (r.status === "proceeded") return "proceeded";
  if (r.status === "cancelled") return "cancelled";
  return "pending"; // pending | ready
}

const STATUS_COPY: Record<StatusKind, { ko: string; en: string }> = {
  proceeded: { ko: "진행함", en: "Proceeded" },
  cancelled: { ko: "취소함", en: "Cancelled" },
  pending: { ko: "검토 중", en: "In review" },
};

/* ────────────────────────────────────────────────────────────────────────
 * Status chip — neutral tone (no carmine), cancelled dimmed.
 * ────────────────────────────────────────────────────────────────────── */

function StatusChip({ kind }: { kind: StatusKind }) {
  const dimmed = kind === "cancelled";
  return (
    <span
      className="font-mono text-pq-caption uppercase"
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 6,
        padding: "2px 8px",
        borderRadius: 2,
        letterSpacing: "0.16em",
        border: "0.5px solid var(--pq-ivory-line)",
        background: "var(--pq-ivory-line-faint)",
        color: dimmed
          ? "rgba(245,240,232,0.45)"
          : "rgba(245,240,232,0.82)",
      }}
    >
      <span
        aria-hidden="true"
        style={{
          width: 5,
          height: 5,
          borderRadius: "50%",
          background:
            kind === "proceeded"
              ? "var(--pq-bronze)"
              : kind === "cancelled"
              ? "rgba(245,240,232,0.3)"
              : "rgba(245,240,232,0.55)",
        }}
      />
      {STATUS_COPY[kind].ko}
      <span style={{ opacity: 0.5 }}>· {STATUS_COPY[kind].en}</span>
    </span>
  );
}

/* ────────────────────────────────────────────────────────────────────────
 * Journal entry card
 * ────────────────────────────────────────────────────────────────────── */

function JournalEntry({ r }: { r: PreTradeReflection }) {
  const { locale } = useLocale();
  const [open, setOpen] = useState(false);

  const ts = entryTimestamp(r);
  const name = displayName(r.intended_ticker, r.intended_name);
  const bareTicker = normalizeTicker(r.intended_ticker);
  // Only show the ticker sub when the resolved name is NOT just the bare code.
  const showTickerSub =
    bareTicker.length > 0 && name.toUpperCase() !== bareTicker.toUpperCase();

  const sideText = r.intended_side ? sideLabel(r.intended_side) : null;
  const kind = statusKind(r);
  const hasDevilsAdvocate =
    typeof r.devil_advocate_seen === "string" &&
    r.devil_advocate_seen.trim().length > 0;

  const dimmed = kind === "cancelled";

  return (
    <article
      className="rounded-[2px] border p-4 sm:p-5 transition-colors"
      style={{
        borderColor: "var(--pq-ivory-line)",
        background: "var(--pq-card-veil)",
        opacity: dimmed ? 0.72 : 1,
      }}
    >
      {/* Header: name + ticker sub + status */}
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <EditorialHead as="h3" size={26} style={{ wordBreak: "keep-all" }}>
            {name}
          </EditorialHead>
          {showTickerSub && (
            <span className="font-mono text-pq-caption uppercase tracking-[0.14em] text-[rgba(245,240,232,0.45)]">
              {bareTicker}
            </span>
          )}
        </div>
        <StatusChip kind={kind} />
      </div>

      {/* Meta row: intent + shares + time */}
      <div className="mt-2.5 flex flex-wrap items-center gap-x-4 gap-y-1.5">
        {sideText && (
          <span className="font-mono text-pq-caption uppercase tracking-[0.14em] text-[var(--pq-bronze-light)]">
            {sideText}
          </span>
        )}
        {typeof r.intended_shares === "number" && r.intended_shares > 0 && (
          <span className="font-mono text-pq-caption text-[rgba(245,240,232,0.55)]">
            {r.intended_shares.toLocaleString()}
            <span className="ml-1 opacity-60">주</span>
          </span>
        )}
        {ts && (
          <span className="font-mono text-pq-caption text-[rgba(245,240,232,0.45)]">
            {relativeTime(ts, locale, { verbose: true })}
            <span className="mx-1.5 opacity-40">·</span>
            <span className="opacity-70">{absoluteDate(ts)}</span>
          </span>
        )}
      </div>

      {/* Rationale */}
      {r.rationale.trim().length > 0 && (
        <p
          className="mt-3 font-serif text-pq-deck"
          style={{
            lineHeight: 1.6,
            color: "rgba(245,240,232,0.82)",
            wordBreak: "keep-all",
          }}
        >
          {r.rationale}
        </p>
      )}

      {/* Auto-extended cooldown note (volatility context) */}
      {r.auto_extended_reason && (
        <p className="mt-2 font-mono text-pq-caption text-[rgba(245,240,232,0.45)]">
          {r.auto_extended_reason}
        </p>
      )}

      {/* 7-question reflection — collapsible */}
      {hasDevilsAdvocate && (
        <div className="mt-3 border-t pt-3" style={{ borderColor: "var(--pq-ivory-line-soft)" }}>
          <button
            type="button"
            onClick={() => setOpen((v) => !v)}
            className="flex w-full items-center gap-2 text-left"
            aria-expanded={open}
          >
            <span className="font-mono text-pq-caption uppercase tracking-[0.18em] text-[var(--pq-bronze-light)]">
              7문항 자기검증
            </span>
            <ChevronDown
              className="h-3.5 w-3.5 shrink-0 text-[rgba(245,240,232,0.5)] transition-transform duration-200"
              style={{ transform: open ? "rotate(180deg)" : undefined }}
            />
          </button>
          {open && (
            <p
              className="mt-2 font-serif text-pq-lead"
              style={{
                lineHeight: 1.6,
                whiteSpace: "pre-wrap",
                color: "rgba(245,240,232,0.7)",
                wordBreak: "keep-all",
              }}
            >
              {r.devil_advocate_seen}
            </p>
          )}
        </div>
      )}
    </article>
  );
}

/* ────────────────────────────────────────────────────────────────────────
 * States
 * ────────────────────────────────────────────────────────────────────── */

function LoadingState() {
  return (
    <div className="space-y-4" aria-hidden="true">
      {[0, 1, 2].map((i) => (
        <div
          key={i}
          className="h-32 animate-pulse rounded-[2px] border"
          style={{
            borderColor: "var(--pq-ivory-line)",
            background: "var(--pq-card-veil)",
          }}
        />
      ))}
    </div>
  );
}

function LoadFailure({ onRetry }: { onRetry: () => void }) {
  return (
    <div
      className="rounded-[2px] border p-6 text-center"
      style={{
        borderColor: "var(--pq-ivory-line)",
        background: "var(--pq-card-veil)",
      }}
    >
      <p className="font-serif text-pq-mono-sm text-[rgba(245,240,232,0.7)]">
        기록을 불러오지 못했습니다.
      </p>
      <button
        type="button"
        onClick={onRetry}
        className="mt-3 rounded-[2px] border px-4 py-2 font-mono text-pq-caption uppercase tracking-[0.16em] text-[var(--pq-bronze-light)] transition-colors hover:bg-[var(--pq-card-veil-strong)]"
        style={{ borderColor: "var(--pq-ivory-line)" }}
      >
        다시 시도
      </button>
    </div>
  );
}

function EmptyState() {
  return (
    <div
      className="rounded-[2px] border px-6 py-12 text-center"
      style={{
        borderColor: "var(--pq-ivory-line)",
        background: "var(--pq-card-veil)",
      }}
    >
      <NotebookPen
        className="mx-auto h-7 w-7 text-[var(--pq-bronze-light)]"
        aria-hidden="true"
      />
      <p
        className="mx-auto mt-4 max-w-md font-serif text-pq-h6"
        style={{
          lineHeight: 1.6,
          color: "rgba(245,240,232,0.78)",
          wordBreak: "keep-all",
        }}
      >
        아직 기록된 의사결정이 없습니다.
      </p>
      <Caption className="mx-auto mt-2 max-w-md">
        종목을 추가하거나 정리할 때 작성한 reflection이 여기 시간순으로 쌓입니다.
      </Caption>
      <Link
        href="/portfolio"
        className="mt-6 inline-flex items-center gap-2 rounded-[2px] border px-5 py-2.5 font-mono text-pq-caption uppercase tracking-[0.16em] text-[var(--pq-bronze-light)] transition-colors hover:bg-[var(--pq-card-veil-strong)]"
        style={{ borderColor: "var(--pq-ivory-line)" }}
      >
        <Briefcase className="h-3.5 w-3.5" aria-hidden="true" />
        포트폴리오로 이동
      </Link>
    </div>
  );
}

/* ────────────────────────────────────────────────────────────────────────
 * Page
 * ────────────────────────────────────────────────────────────────────── */

function JournalContent() {
  const { reflections, isLoading, error, mutate } = usePreTradeJournal();
  const retry = useCallback(() => {
    void mutate();
  }, [mutate]);

  return (
    <div className="mx-auto w-full max-w-2xl px-4 py-8 sm:px-6">
      {/* Header */}
      <header className="mb-6">
        <RuledKicker>Decision Journal</RuledKicker>
        <EditorialHead as="h1" size={32} className="mt-3">
          기록
        </EditorialHead>
        <Caption className="mt-2 max-w-lg">
          종목을 더하거나 줄이기 전, 당신이 스스로 남긴 근거와 자기검증입니다.
          지난 결정을 돌아보세요.
        </Caption>
      </header>

      {/* Legal disclaimer mounted once at the bottom by (dashboard)/layout.tsx
          — no page-level banner here (CEO 2026-05-24: disclaimer only at the
          bottom, every page). */}

      {/* Feed */}
      {isLoading ? (
        <LoadingState />
      ) : error ? (
        <LoadFailure onRetry={retry} />
      ) : reflections.length === 0 ? (
        <EmptyState />
      ) : (
        <div className="space-y-4">
          {reflections.map((r) => (
            <JournalEntry key={r.id} r={r} />
          ))}
        </div>
      )}

      <FootSignature />
    </div>
  );
}

export default function JournalPage() {
  return (
    <ErrorBoundary>
      <JournalContent />
    </ErrorBoundary>
  );
}
