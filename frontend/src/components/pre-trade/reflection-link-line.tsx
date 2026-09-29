"use client";

/**
 * <ReflectionLinkLine /> + useReflectionLink() — link a recorded buy to the
 * pause (/pre-trade reflection) that preceded it. 2026-09-29, CEO approved.
 *
 * The user pauses on /pre-trade, places the order at their own broker, and
 * later records the fill here. Until now the two were joined only by a time
 * window guess (friction_outcome, 7 days). When a recent unlinked buy-side
 * pause exists for this ticker, one factual line offers the link — checkbox
 * default ON — and the host sends `reflection_id` with the buy. The pause's
 * rationale then *is* the buy's reason; the seven questions are not asked
 * again. Backend: services/pre_trade/link.py.
 *
 * Renders nothing while loading, on error, or when there is no candidate.
 * Factual wording only — no nudge to pause more, no verdict on the pause.
 */

import * as React from "react";
import { useLinkableReflections } from "@/lib/hooks";
import { useT } from "@/lib/locale";
import { parseUtcSafe } from "@/lib/relative-time";
import type { PreTradeReflection } from "@/lib/types";

const DAY_MS = 86_400_000;
/** Rationale excerpt budget (first line only), before the ellipsis. */
export const LINK_EXCERPT_CHARS = 80;

export interface ReflectionLinkState {
  /** Most recent linkable pause for the ticker, or null. */
  candidate: PreTradeReflection | null;
  /** Whether the checkbox is on (default ON whenever a candidate exists). */
  linked: boolean;
  setLinked: (on: boolean) => void;
  /** What to send as `reflection_id` — null when unlinked / no candidate. */
  reflectionId: number | null;
}

/** Null ticker disables the fetch (e.g. sell, edit, review mode). */
export function useReflectionLink(ticker: string | null | undefined): ReflectionLinkState {
  const symbol = (ticker ?? "").trim().toUpperCase();
  const { reflections } = useLinkableReflections(symbol || null);
  const candidate = reflections[0] ?? null;
  // Remember which candidate the user unchecked, so the default stays ON for
  // any other candidate (no effect needed to seed the default).
  const [optedOutId, setOptedOutId] = React.useState<number | null>(null);
  const linked = candidate != null && optedOutId !== candidate.id;
  const setLinked = React.useCallback(
    (on: boolean) => setOptedOutId(on ? null : (candidate?.id ?? null)),
    [candidate],
  );
  return { candidate, linked, setLinked, reflectionId: linked && candidate ? candidate.id : null };
}

/** First line of the user's rationale, cut to the excerpt budget. Pure. */
export function rationaleFirstLine(text: string, max: number = LINK_EXCERPT_CHARS): string {
  const first = (text ?? "").split(/\r?\n/).find((l) => l.trim()) ?? "";
  const flat = first.replace(/\s+/g, " ").trim();
  return flat.length <= max ? flat : `${flat.slice(0, max)}…`;
}

/** Whole days between the pause and `now` (0 = today). Pure. */
export function daysSince(iso: string | null | undefined, now: number = Date.now()): number | null {
  const at = parseUtcSafe(iso ?? null);
  if (Number.isNaN(at)) return null;
  return Math.max(0, Math.floor((now - at) / DAY_MS));
}

function ymd(iso: string | null | undefined): string {
  const at = parseUtcSafe(iso ?? null);
  if (Number.isNaN(at)) return "";
  // Calendar day in KST — the day the user wrote it (product is KR-first).
  const d = new Date(at + 9 * 3_600_000);
  const p = (n: number) => String(n).padStart(2, "0");
  return `${d.getUTCFullYear()}.${p(d.getUTCMonth() + 1)}.${p(d.getUTCDate())}`;
}

export function ReflectionLinkLine({ link }: { link: ReflectionLinkState }) {
  const t = useT();
  const { candidate, linked, setLinked } = link;
  if (!candidate) return null;

  const days = daysSince(candidate.cooldown_started_at);
  const head =
    days == null || days === 0
      ? t("preTrade.link.today")
      : t("preTrade.link.daysAgo", { n: String(days) });
  const excerpt = rationaleFirstLine(candidate.rationale);

  return (
    <label
      data-testid="reflection-link-line"
      className="flex cursor-pointer items-start gap-3 rounded-[2px] border px-4 py-3"
      style={{
        borderColor: "var(--pq-ivory-line)",
        background: "var(--pq-card-veil)",
      }}
    >
      <input
        type="checkbox"
        checked={linked}
        onChange={(e) => setLinked(e.target.checked)}
        style={{ marginTop: 3, accentColor: "var(--pq-bronze)" }}
      />
      <span className="flex min-w-0 flex-col gap-1">
        <span
          style={{
            fontSize: "var(--pq-text-body-sm)",
            color: "var(--pq-ivory-strong)",
            wordBreak: "keep-all",
          }}
        >
          {head}
        </span>
        <span
          className="font-mono"
          style={{ fontSize: "var(--pq-text-eyebrow)", color: "var(--pq-ivory-faint)" }}
        >
          {ymd(candidate.cooldown_started_at)}
          {candidate.status === "cancelled" ? ` · ${t("preTrade.link.wasCancelled")}` : ""}
        </span>
        {excerpt && (
          <span
            className="font-serif"
            style={{
              fontSize: "var(--pq-text-body-sm)",
              lineHeight: 1.55,
              color: "var(--pq-ivory-dim)",
              wordBreak: "keep-all",
            }}
          >
            “{excerpt}”
          </span>
        )}
      </span>
    </label>
  );
}

export default ReflectionLinkLine;
