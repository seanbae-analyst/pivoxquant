"use client";

/**
 * <SellMoment /> — 매도 순간의 거울 (2026-10-15).
 *
 * At a 매도 — a waiting fill in the import inbox, or one being typed in the
 * portfolio sell modal — show what the user themselves wrote about this
 * stock before it (멈춤 · 체결 이유 · 리서치 · 관찰 노트), then how long the
 * FIFO lots this sell closes were held and where the price sits against
 * their own cost. Backend: routes/sell_moment.py → services/sell_moment.py.
 *
 * STRICTLY READ-ONLY and facts only: the user's words verbatim, a day count,
 * a percent. No score, no verdict, no colour for up/down (a colour would
 * read as a judgement of the sell), no prompt to do anything. Renders
 * nothing while loading, on error, or when there is nothing to show — an
 * empty block would read as a nudge.
 */
import * as React from "react";
import { useSellMomentForPending, useSellMomentForTyped, type TypedSell } from "@/lib/hooks";
import { kstDateOf } from "@/lib/research";
import type { SellMomentResponse, SellMomentSource } from "@/lib/types";

export const SELL_MOMENT_SOURCE_LABEL: Record<SellMomentSource, string> = {
  pause: "멈춤",
  fill_reason: "체결 이유",
  research: "리서치",
  note: "관찰 노트",
};

/** Typing in the modal should not fire a request per keystroke. */
const TYPED_DEBOUNCE_MS = 400;

/** "−4.0%" / "+12.3%" / "0.0%" — a typographic minus, one decimal. */
export function signedPct(pct: number): string {
  // Sign from the shown value — −0.04 is "0.0%", not "−0.0%".
  const shown = Number(pct.toFixed(1));
  const sign = shown > 0 ? "+" : shown < 0 ? "−" : "";
  return `${sign}${Math.abs(shown).toFixed(1)}%`;
}

/** "9월 1일", or "2025년 9월 1일" when it was not this year. */
export function quoteDate(isoUtc: string, thisYear: number): string {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(kstDateOf(isoUtc));
  if (!m) return "";
  const md = `${Number(m[2])}월 ${Number(m[3])}일`;
  return Number(m[1]) === thisYear ? md : `${Number(m[1])}년 ${md}`;
}

/** "34일 보유 · 산 값 대비 −4.0%" — or "" when neither fact is known. */
export function factsLine(data: SellMomentResponse, sellShares?: number): string {
  const parts: string[] = [];
  if (data.held_days != null) {
    parts.push(data.held_days === 0 ? "하루 미만 보유" : `${data.held_days}일 보유`);
  }
  if (data.vs_cost_pct != null) parts.push(`산 값 대비 ${signedPct(data.vs_cost_pct)}`);
  if (parts.length && sellShares != null && data.matched_shares > 0 && data.matched_shares < sellShares - 1e-9) {
    const n = data.matched_shares.toLocaleString("en-US", { maximumFractionDigits: 4 });
    parts.push(`기록된 ${n}주 기준`);
  }
  return parts.join(" · ");
}

export function SellMomentBlock({
  data,
  sellShares,
}: {
  data: SellMomentResponse | null;
  /** The sell's own shares — to say when only part of it matched recorded lots. */
  sellShares?: number;
}) {
  if (!data) return null;
  const facts = factsLine(data, sellShares);
  // A body without `words` (demo `{}`) draws nothing rather than crashing.
  const words = Array.isArray(data.words) ? data.words : [];
  if (!words.length && !facts) return null;
  const thisYear = new Date().getFullYear();

  return (
    <section
      aria-label="이 종목에 적어 둔 말"
      data-testid="sell-moment"
      className="rounded-[var(--pq-radius-card)] border px-4 py-3"
      style={{ borderColor: "var(--pq-ivory-line)", background: "var(--pq-card-veil)" }}
    >
      {words.length > 0 && (
        <>
          <p className="m-0" style={{ fontSize: "var(--pq-text-eyebrow)", color: "var(--pq-bronze)" }}>
            이 종목에 적어 둔 말
          </p>
          <ul className="mt-2 space-y-2.5 list-none p-0 m-0">
            {words.map((w, i) => (
              <li key={`${w.source}-${w.at}-${i}`} data-testid="sell-moment-quote">
                <div
                  style={{ fontSize: "var(--pq-text-eyebrow)", color: "var(--pq-ivory-faint)", whiteSpace: "nowrap" }}
                >
                  {quoteDate(w.at, thisYear)} · {SELL_MOMENT_SOURCE_LABEL[w.source] ?? ""}
                </div>
                <p
                  className="m-0 mt-0.5"
                  style={{
                    fontSize: "var(--pq-text-body-sm)",
                    lineHeight: 1.55,
                    color: "var(--pq-ivory-strong)",
                    wordBreak: "keep-all",
                  }}
                >
                  {w.text}
                </p>
                {w.invalidation && (
                  <p
                    className="m-0 mt-0.5"
                    style={{ fontSize: "var(--pq-text-body-sm)", lineHeight: 1.55, wordBreak: "keep-all" }}
                  >
                    <span style={{ color: "var(--pq-ivory-faint)" }}>틀렸다고 볼 신호 · </span>
                    <span style={{ color: "var(--pq-ivory-strong)" }}>{w.invalidation}</span>
                  </p>
                )}
              </li>
            ))}
          </ul>
        </>
      )}
      {facts && (
        <p
          className={`m-0 tabular-nums${words.length ? " mt-3" : ""}`}
          data-testid="sell-moment-facts"
          style={{ fontSize: "var(--pq-text-body-sm)", color: "var(--pq-ivory-mid)", wordBreak: "keep-all" }}
        >
          {facts}
        </p>
      )}
    </section>
  );
}

/** A waiting 매도 fill (import inbox, `/journal?pending=<id>`). */
export function PendingSellMoment({ pendingId, sellShares }: { pendingId: number; sellShares?: number }) {
  const { data } = useSellMomentForPending(pendingId);
  return <SellMomentBlock data={data} sellShares={sellShares} />;
}

/** The value after it has stopped changing for `ms`. */
function useDebounced<T>(value: T, ms: number): T {
  const [settled, setSettled] = React.useState(value);
  React.useEffect(() => {
    const id = setTimeout(() => setSettled(value), ms);
    return () => clearTimeout(id);
  }, [value, ms]);
  return settled;
}

/**
 * A 매도 being typed (portfolio sell modal). Fetches only once ticker,
 * shares and price are all known and positive; the hook disables itself
 * otherwise.
 */
export function TypedSellMoment({ ticker, shares, price, date, currency }: TypedSell) {
  const key = JSON.stringify({ ticker, shares, price, date, currency });
  const settled = useDebounced(key, TYPED_DEBOUNCE_MS);
  const sell = React.useMemo(() => JSON.parse(settled) as TypedSell, [settled]);
  const ready = Number.isFinite(sell.shares) && sell.shares > 0 && Number.isFinite(sell.price) && sell.price > 0;
  const { data } = useSellMomentForTyped(ready ? sell : null);
  if (!ready) return null;
  return <SellMomentBlock data={data} sellShares={sell.shares} />;
}

export default SellMomentBlock;
