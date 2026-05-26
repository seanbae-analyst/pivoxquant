/**
 * Support badges — category + status chips reused across the support
 * surfaces (inbox list, detail header, chat escalation card).
 *
 * v3 tone: hairline outline, uppercase mono micro-label, KO primary + EN
 * sub. The "answered" status renders in bronze accent (resolution mark).
 * No carmine/indigo (price-direction only).
 */

import * as React from "react";
import {
  SUPPORT_CATEGORY_META,
  SUPPORT_STATUS_META,
  isSupportCategory,
  isSupportStatus,
} from "./support-meta";
import type { SupportCategory, SupportStatus } from "@/lib/types";

function ChipShell({
  color,
  border,
  dotColor,
  children,
}: {
  color: string;
  border: string;
  dotColor?: string;
  children: React.ReactNode;
}) {
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
        border: `0.5px solid ${border}`,
        background: "var(--pq-ivory-line-faint)",
        color,
        whiteSpace: "nowrap",
      }}
    >
      {dotColor && (
        <span
          aria-hidden="true"
          style={{
            width: 5,
            height: 5,
            borderRadius: "50%",
            background: dotColor,
          }}
        />
      )}
      {children}
    </span>
  );
}

export function CategoryBadge({ category }: { category: SupportCategory | string }) {
  const cat: SupportCategory = isSupportCategory(category) ? category : "other";
  const m = SUPPORT_CATEGORY_META[cat];
  return (
    <ChipShell color={m.color} border={m.border}>
      {m.ko}
      <span style={{ opacity: 0.5 }}>· {m.en}</span>
    </ChipShell>
  );
}

export function StatusBadge({ status }: { status: SupportStatus | string }) {
  const st: SupportStatus = isSupportStatus(status) ? status : "open";
  const m = SUPPORT_STATUS_META[st];
  // The answered chip gets a filled bronze dot; open/closed get a neutral dot.
  const dotColor =
    st === "answered" ? "var(--pq-bronze)" : "rgba(245,240,232,0.4)";
  return (
    <ChipShell color={m.color} border={m.border} dotColor={dotColor}>
      {m.ko}
      <span style={{ opacity: 0.5 }}>· {m.en}</span>
    </ChipShell>
  );
}
