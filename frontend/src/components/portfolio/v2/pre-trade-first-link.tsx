"use client";

/**
 * <PreTradeFirstLink /> — one quiet line on the portfolio buy-record forms
 * (AddPositionModalV2, TradeModalV2 action=buy) pointing to /pre-trade.
 *
 * 2026-10-13 (CEO): the 7-question pause and the ledger are split by time.
 * Before buying → /pre-trade only, which never writes to the ledger. After
 * buying → these modals, record-only. A user who opened a record form before
 * actually buying gets this pointer instead of an in-modal reflection mode.
 * A plain link, not a CTA.
 */

import type { CSSProperties } from "react";
import Link from "next/link";

export const PRE_TRADE_FIRST_COPY = "아직 사기 전이라면 — 먼저 멈춤에서 7문항";

export function PreTradeFirstLink({ style }: { style?: CSSProperties }) {
  return (
    <p className="font-mono" style={{ margin: 0, ...style }}>
      <Link
        href="/pre-trade"
        data-testid="pre-trade-first-link"
        style={{
          fontSize: "var(--pq-text-eyebrow)",
          letterSpacing: "0.02em",
          color: "var(--pq-ivory-dim)",
          textDecoration: "underline",
          textUnderlineOffset: 3,
        }}
      >
        {PRE_TRADE_FIRST_COPY}
      </Link>
    </p>
  );
}

export default PreTradeFirstLink;
