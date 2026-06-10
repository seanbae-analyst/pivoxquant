"use client";

/**
 * TodaysReviewCard — "오늘의 리뷰": the record looks back at you.
 *
 * record-as-spine Phase 3 (docs/strategy/record-as-spine_2026-06-09.md §4.3,
 * CEO GO 2026-06-10). The home screen's first content block after the desk
 * check-in is the user's own MOST RECENT pre-trade reflection — "이 진입,
 * 그때 무슨 생각이었나" — quoted back with the observation snapshot that was
 * on the desk at that moment (Phase 2 observed_context). The core loop is
 * 관측 → 성찰·기록 → **리뷰** → 복리; this card is the 리뷰 step surfacing
 * where every session starts.
 *
 * Additive by design: renders NOTHING while loading, on error, or when the
 * journal is empty — a brand-new user's home is byte-identical to before.
 *
 * Compliance (§17): the card replays the user's OWN words and the factual
 * observation labels they already saw (POSITIVE/NEGATIVE/NEUTRAL — the legal
 * surface). No directive, no 추천/조언.
 */

import Link from "next/link";
import { NotebookPen } from "lucide-react";
import { usePreTradeJournal } from "@/lib/hooks";
import { displayName } from "@/lib/format";
import { sideLabel } from "@/lib/pre-trade";
import { relativeTime } from "@/lib/relative-time";
import { useLocale } from "@/lib/locale";
import type { PreTradeReflection } from "@/lib/types";

function entryTs(r: PreTradeReflection): string | null {
  return r.proceeded_at ?? r.cancelled_at ?? r.cooldown_started_at ?? null;
}

export function TodaysReviewCard() {
  const { locale } = useLocale();
  const { reflections, isLoading, error } = usePreTradeJournal(3);

  // Quiet by default — never a skeleton, never an error block on home.
  if (isLoading || error || reflections.length === 0) return null;
  const r = reflections[0];
  if (!r || !r.rationale || r.rationale.trim().length === 0) return null;

  const name = displayName(r.intended_ticker, r.intended_name);
  const ts = entryTs(r);
  const side = r.intended_side ? sideLabel(r.intended_side) : null;
  const ctx = r.observed_context;
  const ctxParts: string[] = [];
  if (ctx?.signal) {
    ctxParts.push(
      typeof ctx.score === "number"
        ? `${ctx.signal} ${Math.round(ctx.score)}`
        : ctx.signal,
    );
  }
  if (typeof ctx?.vix === "number") ctxParts.push(`VIX ${ctx.vix}`);

  return (
    <Link
      href="/journal"
      aria-label="오늘의 리뷰 — open journal"
      className="group mb-8 block rounded-[2px] border p-5 transition-colors hover:border-[var(--pq-bronze)]"
      style={{
        borderColor: "var(--pq-ivory-line)",
        background: "var(--pq-card-veil)",
      }}
      data-testid="todays-review"
    >
      <div className="flex items-baseline justify-between gap-3">
        <span
          className="font-mono uppercase"
          style={{
            fontSize: "var(--pq-text-eyebrow)",
            letterSpacing: "0.22em",
            color: "var(--pq-bronze)",
          }}
        >
          오늘의 리뷰 · The Record
        </span>
        <span className="font-mono text-pq-caption uppercase tracking-[0.14em] text-[rgba(245,240,232,0.45)] transition-colors group-hover:text-[var(--pq-bronze)]">
          Journal →
        </span>
      </div>

      <p
        className="mt-3 font-serif text-pq-deck"
        style={{
          lineHeight: 1.55,
          color: "rgba(245,240,232,0.85)",
          wordBreak: "keep-all",
          display: "-webkit-box",
          WebkitLineClamp: 2,
          WebkitBoxOrient: "vertical",
          overflow: "hidden",
        }}
      >
        &ldquo;{r.rationale}&rdquo;
      </p>

      <div className="mt-2.5 flex flex-wrap items-center gap-x-3 gap-y-1 font-mono text-pq-caption text-[rgba(245,240,232,0.5)]">
        <span className="inline-flex items-center gap-1.5">
          <NotebookPen className="h-3 w-3" strokeWidth={1.5} aria-hidden />
          {name}
        </span>
        {side && <span className="text-[var(--pq-bronze-light)]">{side}</span>}
        {ts && <span>{relativeTime(ts, locale, { verbose: true })}</span>}
        {ctxParts.length > 0 && (
          <span className="opacity-80">관측 {ctxParts.join(" · ")}</span>
        )}
      </div>
    </Link>
  );
}
