/**
 * 리서치 양식 — labels and caps shared by /journal/research and /pre-trade.
 *
 * Caps mirror models/research_note.py one-for-one (the server re-checks every
 * one; these only keep the form from offering what it would refuse).
 * docs/design/research-notes_2026-10-15.md.
 */
import type { ResearchInfoSource, ResearchOutcome, ResearchVerdict } from "@/lib/types";

export const RESEARCH_MAX_THESES = 3;
export const RESEARCH_MAX_BUSINESS = 300;
export const RESEARCH_MAX_THESIS = 300;
export const RESEARCH_MAX_INVALIDATION = 500;
export const RESEARCH_MAX_RISK = 500;
export const RESEARCH_MAX_NUMBERS = 1000;
export const RESEARCH_MAX_REVIEW_NOTE = 500;

export const REVIEW_MONTH_OPTIONS = [1, 3, 6] as const;
export type ReviewMonths = (typeof REVIEW_MONTH_OPTIONS)[number];

export const INFO_SOURCE_ORDER: ResearchInfoSource[] = ["report", "youtube", "social", "ai", "self"];

export const INFO_SOURCE_LABEL: Record<ResearchInfoSource | "none", string> = {
  report: "리포트",
  youtube: "유튜브",
  social: "지인·SNS",
  ai: "AI",
  self: "직접 분석",
  none: "적지 않음",
};

export const VERDICT_ORDER: ResearchVerdict[] = ["right", "wrong", "unknown"];
export const VERDICT_LABEL: Record<ResearchVerdict, string> = {
  right: "맞음",
  wrong: "틀림",
  unknown: "모름",
};

/** The user's own fills on that stock since the note — a fact, not a grade. */
export const OUTCOME_LABEL: Record<ResearchOutcome, string> = {
  gain: "판 뒤 이익",
  loss: "판 뒤 손실",
  flat: "판 뒤 본전",
  open: "아직 안 팖",
};

/** "2026-01-15" → "1월 15일" (KST calendar date as written by the server). */
export function researchDate(iso: string | null | undefined): string {
  if (!iso) return "";
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso);
  if (!m) return "";
  return `${Number(m[2])}월 ${Number(m[3])}일`;
}

/** A UTC timestamp's KST calendar date, "YYYY-MM-DD". */
export function kstDateOf(isoUtc: string | null | undefined): string {
  if (!isoUtc) return "";
  const t = Date.parse(/Z|[+-]\d\d:?\d\d$/.test(isoUtc) ? isoUtc : `${isoUtc}Z`);
  if (Number.isNaN(t)) return "";
  return new Date(t + 9 * 3600_000).toISOString().slice(0, 10);
}
