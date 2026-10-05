/**
 * Monthly mirror report — client helpers shared by the /settings card and the
 * in-app /journal/report screen (2026-10-05).
 *
 * The numbers and the words both come from the backend
 * (`GET /api/reports/mirror` → `build_mirror_report` + `mirror_labels`, the
 * same pair the PDF template renders), so the screen and the PDF cannot say
 * different things. This file only fetches and downloads.
 */

import useSWR from "swr";
import { API } from "@/lib/endpoints";
import { fetcher } from "@/lib/hooks";

/** Loose shape — the backend dict is rendered key by key, defensively. */
export type ReportBlock = Record<string, unknown>;

export interface MirrorReport {
  has_content: boolean;
  period_days: number;
  period_start: string;
  period_end: string;
  generated_at: string;
  window_trade_count: number;
  turnover?: ReportBlock;
  averaging_down?: ReportBlock;
  profit_loss?: ReportBlock;
  concentration?: ReportBlock;
  pauses?: ReportBlock;
}

/** Report copy, one locale. `limits` is the only list-valued key. */
export type MirrorLabels = Record<string, string> & { limits?: string[] };

export interface MirrorReportResponse {
  ok: boolean;
  locale: "ko" | "en";
  report: MirrorReport;
  labels: MirrorLabels;
}

export function useMirrorReport(locale: string) {
  const loc = locale === "en" ? "en" : "ko";
  return useSWR<MirrorReportResponse>(
    `${API.reports.mirror}?locale=${loc}`,
    fetcher,
    { revalidateOnFocus: false, dedupingInterval: 60_000, errorRetryCount: 1 },
  );
}

export type PdfDownloadResult = "ok" | "empty" | "rate_limited" | "error";

/**
 * Download the caller's own report PDF. A binary attachment, not JSON — raw
 * fetch, same pattern as the CSV export. 404 = nothing to mirror yet,
 * 429 = the per-user render limit (5/min).
 */
export async function downloadMirrorPdf(): Promise<PdfDownloadResult> {
  try {
    const res = await fetch(API.reports.mirrorPdf, { credentials: "include" });
    if (res.status === 404) return "empty";
    if (res.status === 429) return "rate_limited";
    if (!res.ok) return "error";
    const disposition = res.headers.get("Content-Disposition") ?? "";
    const match = disposition.match(/filename="([^"]+)"/);
    const filename = match?.[1] ?? "pivoxquant_mirror.pdf";
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
    return "ok";
  } catch {
    return "error";
  }
}

/* ── Formatting — mirrors the PDF template's Jinja filters ─────────────── */

const DASH = "—";

function num(v: unknown): number | null {
  if (v === null || v === undefined || v === "") return null;
  const n = typeof v === "number" ? v : Number(v);
  return Number.isFinite(n) ? n : null;
}

/** Thousands-separated number; null/NaN → em dash. (`| fmt`) */
export function fmt(v: unknown, digits = 0): string {
  const n = num(v);
  if (n === null) return DASH;
  return n.toLocaleString("en-US", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

/** Signed number, loss sign kept as recorded. (`| signed`) */
export function signed(v: unknown, digits = 2): string {
  const n = num(v);
  if (n === null) return DASH;
  return `${n >= 0 ? "+" : "−"}${fmt(Math.abs(n), digits)}`;
}

/** KRW without decimals, everything else two. (`| money`) */
export function money(v: unknown, currency?: unknown): string {
  return fmt(v, String(currency ?? "").toUpperCase() === "KRW" ? 0 : 2);
}

/** `{key}` placeholder fill for server copy (the template's `| replace`). */
export function fill(text: string | undefined, params: Record<string, unknown>): string {
  let out = text ?? "";
  for (const [k, v] of Object.entries(params)) {
    out = out.split(`{${k}}`).join(String(v));
  }
  return out;
}
