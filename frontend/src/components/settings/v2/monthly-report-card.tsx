"use client";

/**
 * <MonthlyReportCard /> — what the monthly mirror email is, whether it will
 * actually go out, and the same PDF on demand.
 *
 * Until 2026-10-05 the only trace of the report on screen was one row in the
 * notifications matrix; the on-demand route (`GET /api/reports/mirror.pdf`,
 * routes/reports.py) had no caller at all, so nobody could see what the
 * email carries before turning it on.
 *
 * The send gate is three switches owned by three different places
 * (services/reports_delivery.py): the matrix cell (`monthly_mirror` × email),
 * B2 email delivery (`email_opt_out`) and B3 consent. This card lists all
 * three and says plainly whether the next run would send. "Unknown" (still
 * loading) is never shown as off.
 *
 * The PDF reads only the user's own records — no quote, no score — and does
 * not carry the reasons written in a pause (services/reports/mirror_pdf.py).
 */

import * as React from "react";
import { toast } from "sonner";

import { API } from "@/lib/endpoints";
import { useNotificationPreferences } from "@/lib/hooks";
import { useT } from "@/lib/locale";
import {
  EMAIL_DELIVERY_ANCHOR,
  MARKETING_CONSENT_ANCHOR,
} from "@/components/settings/v2/notifications-matrix";

/** The cron: day 1, 08:30 KST (services/scheduler/cron_jobs.py). */
const SEND_DAY = 1;
const SEND_MINUTES_KST = 8 * 60 + 30;
const KST_OFFSET_MS = 9 * 60 * 60 * 1000;

/**
 * Next run of the monthly send as a KST calendar date ("YYYY-MM-DD"). Pure —
 * exported for tests.
 */
export function nextMonthlySendDate(now: Date): string {
  const kst = new Date(now.getTime() + KST_OFFSET_MS);
  const y = kst.getUTCFullYear();
  const m = kst.getUTCMonth();
  const minutes = kst.getUTCHours() * 60 + kst.getUTCMinutes();
  const thisMonth = kst.getUTCDate() === SEND_DAY && minutes < SEND_MINUTES_KST;
  const target = thisMonth ? new Date(Date.UTC(y, m, SEND_DAY)) : new Date(Date.UTC(y, m + 1, SEND_DAY));
  return target.toISOString().slice(0, 10);
}

type GateState = boolean | undefined;

/** True / false once all three are known; undefined while any is loading. */
export function monthlyReportWillSend(
  cell: GateState,
  delivery: GateState,
  consent: GateState,
): boolean | undefined {
  if (cell === false || delivery === false || consent === false) return false;
  if (cell === undefined || delivery === undefined || consent === undefined) return undefined;
  return true;
}

export function MonthlyReportCard({
  emailDeliveryOn,
  marketingConsentOn,
}: {
  emailDeliveryOn: GateState;
  marketingConsentOn: GateState;
}) {
  const t = useT();
  const m = (k: string, params?: Record<string, string>) =>
    t(`settingsV2.monthlyReport.${k}`, params);
  const { data } = useNotificationPreferences();
  const cellOn: GateState = data?.prefs
    ? data.prefs.monthly_mirror?.email === true
    : undefined;
  const willSend = monthlyReportWillSend(cellOn, emailDeliveryOn, marketingConsentOn);
  const [downloading, setDownloading] = React.useState(false);
  const [emptyNote, setEmptyNote] = React.useState(false);

  const download = React.useCallback(async () => {
    setDownloading(true);
    setEmptyNote(false);
    try {
      // A binary attachment, not JSON — same raw-fetch pattern as the CSV
      // export on this page.
      const res = await fetch(API.reports.mirrorPdf, { credentials: "include" });
      if (res.status === 404) {
        setEmptyNote(true);
        return;
      }
      if (res.status === 429) {
        toast.error(m("tooMany"));
        return;
      }
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
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
    } catch {
      toast.error(m("failed"));
    } finally {
      setDownloading(false);
    }
    // `m` is derived from `t`; re-create only when the locale changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [t]);

  const gates: { key: string; on: GateState; href?: string }[] = [
    { key: "gateCell", on: cellOn },
    { key: "gateDelivery", on: emailDeliveryOn, href: `#${EMAIL_DELIVERY_ANCHOR}` },
    { key: "gateConsent", on: marketingConsentOn, href: `#${MARKETING_CONSENT_ANCHOR}` },
  ];

  return (
    <div
      id="monthly-report"
      style={{
        background: "rgba(255,255,255,0.02)",
        border: "1px solid var(--pq-ivory-line)",
        borderRadius: 4,
        padding: 24,
        scrollMarginTop: 96,
      }}
    >
      <div
        className="font-mono uppercase"
        style={{
          fontSize: "var(--pq-text-eyebrow)",
          letterSpacing: "0.22em",
          color: "var(--pq-bronze)",
          marginBottom: 12,
        }}
      >
        {m("eyebrow")}
      </div>
      <p
        className="font-serif"
        style={{ fontSize: "var(--pq-text-body)", color: "var(--pq-ivory)", lineHeight: 1.6, margin: 0 }}
      >
        {m("what")}
      </p>
      <p
        className="font-serif"
        style={{ fontSize: "var(--pq-text-body)", color: "var(--pq-ivory-dim)", lineHeight: 1.6, marginTop: 6 }}
      >
        {m("contents")}
      </p>

      <ul style={{ listStyle: "none", padding: 0, margin: "16px 0 0" }}>
        {gates.map((g) => (
          <li
            key={g.key}
            className="font-mono"
            style={{
              display: "flex",
              justifyContent: "space-between",
              gap: 12,
              padding: "8px 0",
              borderTop: "1px solid var(--pq-ivory-line-soft)",
              fontSize: "var(--pq-text-mono-sm, 12px)",
              letterSpacing: "0.04em",
              color: "var(--pq-ivory-mid)",
            }}
          >
            {g.href ? (
              <a href={g.href} style={{ color: "inherit", textDecoration: "underline", textUnderlineOffset: 3 }}>
                {m(g.key)}
              </a>
            ) : (
              <span>{m(g.key)}</span>
            )}
            <span
              style={{
                color: g.on === true ? "var(--pq-bronze)" : "var(--pq-ivory-faint)",
                whiteSpace: "nowrap",
              }}
            >
              {g.on === undefined ? m("checking") : g.on ? m("on") : m("off")}
            </span>
          </li>
        ))}
      </ul>

      <p
        role="status"
        aria-live="polite"
        className="font-serif"
        style={{
          fontSize: "var(--pq-text-body)",
          color: willSend ? "var(--pq-ivory)" : "var(--pq-ivory-dim)",
          marginTop: 12,
        }}
      >
        {willSend === undefined
          ? m("checking")
          : willSend
            ? m("willSend", { date: nextMonthlySendDate(new Date()) })
            : m("wontSend")}
      </p>

      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          alignItems: "center",
          gap: 12,
          marginTop: 16,
        }}
      >
        <button
          type="button"
          onClick={download}
          disabled={downloading}
          aria-busy={downloading || undefined}
          className="inline-flex items-center gap-2 px-5 py-2 text-pq-mono-sm uppercase tracking-[0.22em] text-[var(--pq-ivory-mid)] border border-[rgba(245,240,232,0.15)] hover:border-[var(--pq-bronze)] hover:text-[var(--pq-bronze)] disabled:opacity-40 disabled:cursor-wait"
        >
          {downloading ? m("downloading") : m("download")}
        </button>
        <span
          className="font-serif"
          style={{ fontSize: "var(--pq-text-body)", color: "var(--pq-ivory-faint)" }}
        >
          {m("downloadNote")}
        </span>
      </div>
      {emptyNote && (
        <p
          role="status"
          className="font-serif"
          style={{ fontSize: "var(--pq-text-body)", color: "var(--pq-ivory-dim)", marginTop: 10 }}
        >
          {m("empty")}
        </p>
      )}
    </div>
  );
}

export default MonthlyReportCard;
