/**
 * Support metadata — category + status label/color maps (single source of
 * truth for the support surfaces). Pure data, no JSX, importable from both
 * client and server components.
 *
 * Colors use v3 tokens only. The "answered" status uses the bronze accent
 * (`--pq-bronze`) — the calm "done / resolved" hue. open/closed stay neutral
 * ivory so the bronze reads as a positive resolution mark, not an alarm.
 * (Carmine/indigo are reserved for price direction — never used here.)
 */

import type { SupportCategory, SupportStatus } from "@/lib/types";

export interface MetaEntry {
  /** Korean label (primary). */
  ko: string;
  /** English sublabel (de-emphasised). */
  en: string;
  /** Foreground token for the badge text/dot. */
  color: string;
  /** Border token for the badge outline. */
  border: string;
}

export const SUPPORT_CATEGORY_META: Record<SupportCategory, MetaEntry> = {
  billing: {
    ko: "결제·환불",
    en: "Billing",
    color: "var(--pq-bronze-light)",
    border: "var(--pq-ivory-line)",
  },
  account: {
    ko: "계정",
    en: "Account",
    color: "var(--pq-ivory-soft)",
    border: "var(--pq-ivory-line)",
  },
  technical: {
    ko: "기술",
    en: "Technical",
    color: "var(--pq-ivory-soft)",
    border: "var(--pq-ivory-line)",
  },
  other: {
    ko: "기타",
    en: "Other",
    color: "var(--pq-ivory-dim)",
    border: "var(--pq-ivory-line)",
  },
};

export const SUPPORT_STATUS_META: Record<SupportStatus, MetaEntry> = {
  open: {
    ko: "접수",
    en: "Open",
    color: "var(--pq-ivory-dim)",
    border: "var(--pq-ivory-line)",
  },
  answered: {
    // Bronze accent — the "resolved / replied" positive resolution mark.
    ko: "답변완료",
    en: "Answered",
    color: "var(--pq-bronze)",
    border: "var(--pq-bronze)",
  },
  closed: {
    ko: "종료",
    en: "Closed",
    color: "var(--pq-ivory-faint)",
    border: "var(--pq-ivory-line-soft)",
  },
};

/** Category options for the inquiry form select, in display order. */
export const SUPPORT_CATEGORY_OPTIONS: ReadonlyArray<{
  value: SupportCategory;
  label: string;
}> = [
  { value: "billing", label: "결제·환불" },
  { value: "account", label: "계정" },
  { value: "technical", label: "기술" },
  { value: "other", label: "기타" },
];

/** Narrowing guards so unknown server values degrade gracefully. */
export function isSupportCategory(v: unknown): v is SupportCategory {
  return v === "billing" || v === "account" || v === "technical" || v === "other";
}

export function isSupportStatus(v: unknown): v is SupportStatus {
  return v === "open" || v === "answered" || v === "closed";
}
