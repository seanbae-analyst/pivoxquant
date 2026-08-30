/**
 * Locale-aware relative time helper.
 *
 * Eliminates the parallel hardcoded English "{n}m ago / {n}h ago" formatters
 * that lived in NotificationDropdown and /alerts (Wave C-1, 2026-05-17).
 *
 * Returns a short, compact string suitable for inline metadata rows:
 *   ko: "방금", "5분", "3시간", "2일", "4주"
 *   en: "just now", "5m", "3h", "2d", "4w"
 *
 * The compact form (no " ago" suffix) matches the existing /alerts UI where
 * the relative time sits in a tabular metadata column. NotificationDropdown
 * previously used the "{n}m ago" verbose form — the compact form is a small
 * regression in EN but unifies the two surfaces so the bell and the page
 * never disagree.
 *
 * Set `verbose: true` to opt into the "{n}분 전 / {n}m ago" expanded form
 * for callers that need it (NotificationDropdown uses verbose).
 */

import type { Locale } from "@/lib/locale";

export interface RelativeTimeOptions {
  /** When true, append "전" (ko) / " ago" (en) to non-"just now" outputs. */
  verbose?: boolean;
}

/**
 * UTC-safe timestamp parse — shared guard against the naive-ISO drift.
 *
 * `new Date("2026-08-30T07:00:00")` is parsed as LOCAL time per ECMA-262, so a
 * naive UTC stamp from the backend read ~9 hours off for KST users. Backend
 * payloads now carry an explicit `Z` (`services/time_utils.observed_at_iso`),
 * but this guard stays as defense-in-depth for legacy/cached responses.
 *
 * Returns epoch milliseconds, or `NaN` when the input is absent/unparseable.
 */
export function parseUtcSafe(input: string | Date | null | undefined): number {
  if (!input) return NaN;
  if (input instanceof Date) return input.getTime();
  const needsUtcGuard =
    typeof input === "string" &&
    !input.endsWith("Z") &&
    !/[+-]\d{2}:?\d{2}$/.test(input);
  return new Date(needsUtcGuard ? input + "Z" : input).getTime();
}

export function relativeTime(
  input: string | Date,
  locale: Locale,
  opts: RelativeTimeOptions = {},
): string {
  if (!input) return "";
  // F3-02 (2026-05-17): defense-in-depth UTC guard. The backend
  // (services/serializers.py) now appends "Z" to naive UTC timestamps,
  // but legacy responses or other surfaces may still hand us a bare
  // "YYYY-MM-DDTHH:MM:SS" string. ``new Date()`` parses that as LOCAL
  // time per ECMA-262 — for KST users this drifted relative-time
  // readings by 9 hours. Force UTC interpretation when no timezone
  // marker is present.
  const t = parseUtcSafe(input);
  if (Number.isNaN(t)) return "";

  const diff = Date.now() - t;
  const mins = Math.floor(diff / 60_000);
  const verbose = opts.verbose ?? false;

  if (locale === "ko") {
    if (mins < 1) return "방금";
    if (mins < 60) return verbose ? `${mins}분 전` : `${mins}분`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return verbose ? `${hrs}시간 전` : `${hrs}시간`;
    const days = Math.floor(hrs / 24);
    if (days < 7) return verbose ? `${days}일 전` : `${days}일`;
    const weeks = Math.floor(days / 7);
    return verbose ? `${weeks}주 전` : `${weeks}주`;
  }

  // en
  if (mins < 1) return "just now";
  if (mins < 60) return verbose ? `${mins}m ago` : `${mins}m`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return verbose ? `${hrs}h ago` : `${hrs}h`;
  const days = Math.floor(hrs / 24);
  if (days < 7) return verbose ? `${days}d ago` : `${days}d`;
  const weeks = Math.floor(days / 7);
  return verbose ? `${weeks}w ago` : `${weeks}w`;
}
