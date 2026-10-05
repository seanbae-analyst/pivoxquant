"use client";

/**
 * /journal/report — the monthly mirror report, read in the app.
 *
 * Until 2026-10-05 the report existed only as an emailed PDF (and, from the
 * same day, a download button on /settings). This screen shows the same
 * report in the app's own design.
 *
 * Nothing is computed or worded here. `GET /api/reports/mirror` returns the
 * report dict from `build_mirror_report` and the copy from `mirror_labels` —
 * the exact pair the PDF template renders — so the two surfaces cannot drift.
 * This file is layout only: the sections, their order and their empty states
 * follow services/reports/templates/mirror_report.html.j2.
 *
 * The (dashboard) layout mounts the DisclaimerBanner for /journal/*; this
 * page does not mount its own. No quote is read: every figure is the user's
 * own recorded price × quantity. No score, no grade.
 *
 * Tone: v3 — Vantablack + Bronze + Playfair UPRIGHT.
 */

import * as React from "react";
import Link from "next/link";
import { toast } from "sonner";
import { useLocale } from "@/lib/locale";
import {
  RuledKicker,
  Caption,
  EditorialHead,
  FootSignature,
} from "@/components/ui/editorial";
import { ErrorBoundary } from "@/components/ui/error-boundary";
import {
  downloadMirrorPdf,
  fill,
  fmt,
  money,
  signed,
  useMirrorReport,
  type MirrorLabels,
  type ReportBlock,
} from "@/lib/reports";

/* ── small layout pieces ───────────────────────────────────────────────── */

function Section({
  title,
  lede,
  children,
}: {
  title: string;
  lede?: string;
  children: React.ReactNode;
}) {
  return (
    <section
      className="rounded-[2px] border p-5 sm:p-6"
      style={{ borderColor: "var(--pq-ivory-line)", background: "var(--pq-card-veil)" }}
    >
      <EditorialHead as="h2" size={22}>
        {title}
      </EditorialHead>
      {lede && (
        <p className="mt-2 max-w-[62ch] font-serif text-pq-body leading-relaxed text-[var(--pq-ivory-mid)]">
          {lede}
        </p>
      )}
      <div className="mt-5 space-y-4">{children}</div>
    </section>
  );
}

function Tiles({ children }: { children: React.ReactNode }) {
  return <div className="grid grid-cols-2 gap-px overflow-hidden rounded-[2px] border border-[var(--pq-ivory-line)] bg-[var(--pq-ivory-line)] md:grid-cols-4">{children}</div>;
}

function Tile({ k, v, unit }: { k: string; v: string; unit?: string }) {
  return (
    <div className="min-w-0 bg-[var(--pq-ink,#050505)] p-3 sm:p-4">
      <div className="font-mono text-pq-eyebrow uppercase tracking-[0.12em] text-[var(--pq-ivory-faint)]">
        {k}
      </div>
      <div className="mt-2 font-display text-[var(--pq-ivory)]" style={{ fontSize: 26, lineHeight: 1.1 }}>
        {v}
        {unit && v !== "—" && (
          <span className="ml-1 font-mono text-pq-mono-sm text-[var(--pq-ivory-dim)]">{unit}</span>
        )}
      </div>
    </div>
  );
}

/**
 * A long description goes in `caption` (rendered above the table), not in
 * the first header cell — a sentence-long first header widened two-column
 * tables past a phone screen and pushed the counts off it. Only tables
 * wider than three columns get a minimum width; those scroll sideways.
 */
function Table({
  caption,
  head,
  rows,
}: {
  caption?: string;
  head: string[];
  rows: (string | number)[][];
}) {
  const wide = head.length > 3;
  return (
    <div>
      {caption && (
        <p className="mb-2 font-mono text-pq-mono-sm uppercase tracking-[0.06em] text-[var(--pq-ivory-faint)]">
          {caption}
        </p>
      )}
      <div className={wide ? "-mx-5 overflow-x-auto px-5 sm:mx-0 sm:px-0" : ""}>
      <table className={`w-full border-collapse font-mono text-pq-mono-sm ${wide ? "min-w-[440px]" : ""}`}>
        <thead>
          <tr>
            {head.map((h, i) => (
              <th
                key={i}
                className={`border-b border-[var(--pq-ivory-line)] pb-2 font-normal uppercase tracking-[0.08em] text-[var(--pq-ivory-faint)] ${i === 0 ? "text-left" : "text-right"}`}
              >
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, ri) => (
            <tr key={ri}>
              {r.map((c, ci) => (
                <td
                  key={ci}
                  className={`border-b border-[var(--pq-ivory-line-soft)] py-2.5 ${ci === 0 ? "pr-3 text-left font-serif text-pq-body text-[var(--pq-ivory)]" : "pl-3 text-right tabular-nums text-[var(--pq-ivory-mid)]"}`}
                >
                  {c}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      </div>
    </div>
  );
}

function Note({ children }: { children: React.ReactNode }) {
  return (
    <p className="font-mono text-pq-mono-sm tracking-[0.04em] text-[var(--pq-ivory-faint)]">
      {children}
    </p>
  );
}

function None({ children }: { children: React.ReactNode }) {
  return <p className="font-serif text-pq-body text-[var(--pq-ivory-dim)]">{children}</p>;
}

/* ── helpers ───────────────────────────────────────────────────────────── */

const obj = (v: unknown): ReportBlock =>
  v && typeof v === "object" && !Array.isArray(v) ? (v as ReportBlock) : {};
const list = (v: unknown): ReportBlock[] =>
  Array.isArray(v) ? (v.filter((x) => x && typeof x === "object") as ReportBlock[]) : [];
const pct = (v: unknown, L: MirrorLabels) => {
  const s = signed(v);
  return s === "—" ? s : `${s}${L.unit_pct ?? "%"}`;
};

/* ── sections (order = the PDF template) ───────────────────────────────── */

function FillsSection({ d, L }: { d: ReportBlock; L: MirrorLabels }) {
  return (
    <Section title={L.s_fills} lede={L.s_fills_lede}>
      {d.sufficient_data ? (
        <>
          <Tiles>
            <Tile k={L.k_fills} v={fmt(d.trade_count)} unit={L.unit_count} />
            <Tile k={L.k_acquire} v={fmt(d.buy_count)} unit={L.unit_count} />
            <Tile k={L.k_dispose} v={fmt(d.sell_count)} unit={L.unit_count} />
            <Tile k={L.k_days_median} v={fmt(d.median_hold_days, 1)} unit={L.unit_days} />
          </Tiles>
          {list(d.by_currency).length > 0 && (
            <Table
              head={[L.th_currency, L.th_gross, L.th_count]}
              rows={list(d.by_currency).map((r) => [
                String(r.currency ?? ""),
                money(r.gross_value, r.currency),
                fmt(r.trade_count),
              ])}
            />
          )}
          <Note>
            {L.k_days_mean} {fmt(d.mean_hold_days, 1)}
            {L.unit_days}
          </Note>
        </>
      ) : (
        <None>{L.none_fills}</None>
      )}
    </Section>
  );
}

function FollowOnSection({ d, L }: { d: ReportBlock; L: MirrorLabels }) {
  return (
    <Section title={L.s_followon} lede={L.s_followon_lede}>
      {d.sufficient_data ? (
        <>
          <Tiles>
            <Tile k={L.k_followon} v={fmt(d.follow_on_count)} unit={L.unit_count} />
            <Tile k={L.k_below} v={fmt(d.below_avg_count)} unit={L.unit_count} />
            <Tile k={L.k_above} v={fmt(d.above_avg_count)} unit={L.unit_count} />
            <Tile k={L.k_flat} v={fmt(d.flat_count)} unit={L.unit_count} />
          </Tiles>
          {list(d.by_ticker).length > 0 && (
            <Table
              head={[L.th_ticker, L.k_followon, L.k_below, L.k_above]}
              rows={list(d.by_ticker).map((r) => [
                String(r.name || r.ticker || ""),
                fmt(r.follow_on),
                fmt(r.below_avg),
                fmt(r.above_avg),
              ])}
            />
          )}
        </>
      ) : (
        <None>{L.none_followon}</None>
      )}
    </Section>
  );
}

function ClosedSection({ d, L }: { d: ReportBlock; L: MirrorLabels }) {
  const gain = obj(d.take_profit);
  const loss = obj(d.stop_loss);
  return (
    <Section title={L.s_closed} lede={L.s_closed_lede}>
      {d.sufficient_data ? (
        <>
          <Table
            head={["", L.k_count, L.k_days_median_short, L.k_return_median, L.k_return_mean]}
            rows={[
              [L.k_gain_side, fmt(gain.count), fmt(gain.median_hold_days, 1), pct(gain.median_gain_pct, L), pct(gain.mean_gain_pct, L)],
              [L.k_loss_side, fmt(loss.count), fmt(loss.median_hold_days, 1), pct(loss.median_loss_pct, L), pct(loss.mean_loss_pct, L)],
            ]}
          />
          <Note>
            {L.k_total_closed} {fmt(d.total_closed_pairs)}
            {L.unit_count}
          </Note>
          {Boolean(d.one_sided) && <Note>{L.one_sided}</Note>}
        </>
      ) : (
        <None>{L.none_closed}</None>
      )}
    </Section>
  );
}

function PausesSection({ d, L }: { d: ReportBlock; L: MirrorLabels }) {
  const st = obj(d.stopped);
  const cf = obj(d.cancelled_followthrough);
  const rl = obj(d.realised);
  const rw = obj(rl.with_friction);
  const ro = obj(rl.without_friction);
  const comparable = Boolean(rl.comparable);
  return (
    <Section title={L.s_pauses} lede={L.s_pauses_lede}>
      {d.sufficient_data ? (
        <>
          <Tiles>
            <Tile k={L.k_started} v={fmt(st.started)} unit={L.unit_count} />
            <Tile k={L.k_proceeded} v={fmt(st.proceeded)} unit={L.unit_count} />
            <Tile k={L.k_cancelled} v={fmt(st.cancelled)} unit={L.unit_count} />
            <Tile k={L.k_open} v={fmt(st.open)} unit={L.unit_count} />
          </Tiles>
          {Boolean(cf.cancelled) && (
            <>
              <Table
                caption={L.s_pauses_cancel}
                head={["", L.th_count]}
                rows={[
                  [L.k_cancel_total, fmt(cf.cancelled)],
                  [L.k_bought_later, fmt(cf.bought_later_anyway)],
                  [L.k_never_bought, fmt(cf.never_bought)],
                ]}
              />
              {cf.median_days_until_bought !== null && cf.median_days_until_bought !== undefined && (
                <Note>
                  {L.k_days_until} {fmt(cf.median_days_until_bought, 1)}
                  {L.unit_days}
                </Note>
              )}
            </>
          )}
          {(Boolean(rw.n) || Boolean(ro.n)) && (
            <>
              <Table
                caption={L.s_pauses_realised}
                head={comparable ? ["", L.k_count, L.k_return_median] : ["", L.k_count]}
                rows={[
                  comparable
                    ? [L.k_with, fmt(rw.n), pct(rw.median_pct, L)]
                    : [L.k_with, fmt(rw.n)],
                  comparable
                    ? [L.k_without, fmt(ro.n), pct(ro.median_pct, L)]
                    : [L.k_without, fmt(ro.n)],
                ]}
              />
              {!comparable && <Note>{fill(L.realised_hidden, { n: rl.min_group_n ?? 5 })}</Note>}
            </>
          )}
          <Note>
            {fill(L.pauses_attr, {
              links: d.explicit_links ?? 0,
              days: d.attribution_window_days ?? 7,
            })}
          </Note>
        </>
      ) : (
        <None>{L.none_pauses}</None>
      )}
    </Section>
  );
}

function ConcentrationSection({ d, L }: { d: ReportBlock; L: MirrorLabels }) {
  return (
    <Section title={L.s_concentration} lede={L.s_concentration_lede}>
      {d.sufficient_data ? (
        <>
          <div className="grid grid-cols-2 gap-px overflow-hidden rounded-[2px] border border-[var(--pq-ivory-line)] bg-[var(--pq-ivory-line)] md:grid-cols-3">
            <Tile k={L.k_symbols} v={fmt(d.ticker_count)} />
            <Tile k={L.k_max_weight} v={fmt(d.max_weight_pct, 1)} unit={L.unit_pct} />
            <div className="col-span-2 md:col-span-1">
              <Tile k={L.k_largest} v={String(d.largest_ticker || "—")} />
            </div>
          </div>
          {typeof d.cost_basis_note === "string" && d.cost_basis_note && (
            <Note>{d.cost_basis_note}</Note>
          )}
        </>
      ) : (
        <None>{L.none_concentration}</None>
      )}
    </Section>
  );
}

/* ── page ──────────────────────────────────────────────────────────────── */

export default function MirrorReportPage() {
  const { locale, t } = useLocale();
  const { data, error, isLoading, mutate } = useMirrorReport(locale);
  const [downloading, setDownloading] = React.useState(false);
  const r = (k: string) => t(`journal.report.${k}`);

  const onDownload = async () => {
    setDownloading(true);
    const res = await downloadMirrorPdf();
    setDownloading(false);
    if (res === "empty") toast(r("pdfEmpty"));
    else if (res === "rate_limited") toast.error(r("pdfTooMany"));
    else if (res === "error") toast.error(r("pdfFailed"));
  };

  const L = data?.labels;
  const report = data?.report;

  return (
    <ErrorBoundary>
      <div className="mx-auto w-full max-w-3xl space-y-6 px-4 py-8 sm:px-6">
        <header>
          <RuledKicker>{L?.eyebrow ?? r("kicker")}</RuledKicker>
          <EditorialHead as="h1" size={32} className="mt-3">
            {L?.title ?? r("title")}
          </EditorialHead>
          {L?.subtitle && <Caption className="mt-2 max-w-lg">{L.subtitle}</Caption>}
          {report && L && (
            <div className="mt-3 flex flex-wrap gap-x-5 gap-y-1 font-mono text-pq-mono-sm tracking-[0.04em] text-[var(--pq-ivory-dim)]">
              <span>
                {L.period} {report.period_start} — {report.period_end} ({report.period_days}
                {L.unit_days})
              </span>
            </div>
          )}
          <div className="mt-4 flex flex-wrap items-center gap-3">
            <button
              type="button"
              onClick={onDownload}
              disabled={downloading || !report?.has_content}
              aria-busy={downloading || undefined}
              className="pq-ink-btn-bronze inline-flex items-center gap-2 px-5 py-2 text-pq-mono-sm uppercase tracking-[0.22em] disabled:cursor-not-allowed disabled:opacity-30"
            >
              {downloading ? r("pdfBuilding") : r("pdfDownload")}
            </button>
            <Link
              href="/settings#monthly-report"
              className="font-mono text-pq-eyebrow uppercase tracking-[0.16em] text-[var(--pq-bronze-light)] underline-offset-4 hover:underline"
            >
              {r("emailSettings")}
            </Link>
            <Link
              href="/journal"
              className="font-mono text-pq-eyebrow uppercase tracking-[0.16em] text-[var(--pq-ivory-dim)] underline-offset-4 hover:underline"
            >
              {r("backToJournal")}
            </Link>
          </div>
        </header>

        {isLoading && !data && (
          <p role="status" className="font-mono text-pq-mono-sm text-[var(--pq-ivory-faint)]">
            {r("loading")}
          </p>
        )}

        {error && !data && (
          <div role="alert" className="space-y-3">
            <p className="font-serif text-pq-body text-[var(--pq-ivory-mid)]">{r("loadFailed")}</p>
            <button
              type="button"
              onClick={() => mutate()}
              className="font-mono text-pq-eyebrow uppercase tracking-[0.16em] text-[var(--pq-bronze-light)] underline underline-offset-4"
            >
              {r("retry")}
            </button>
          </div>
        )}

        {report && L && (
          <>
            {!report.has_content && (
              <Section title={L.empty_head} lede={L.empty_body}>
                <Note>{r("emptyHint")}</Note>
              </Section>
            )}
            <FillsSection d={obj(report.turnover)} L={L} />
            <FollowOnSection d={obj(report.averaging_down)} L={L} />
            <ClosedSection d={obj(report.profit_loss)} L={L} />
            <PausesSection d={obj(report.pauses)} L={L} />
            <ConcentrationSection d={obj(report.concentration)} L={L} />
            <Section title={L.s_limits}>
              <ul className="list-disc space-y-2 pl-5 font-serif text-pq-body leading-relaxed text-[var(--pq-ivory-mid)]">
                {(L.limits ?? []).map((line, i) => (
                  <li key={i}>{line}</li>
                ))}
              </ul>
            </Section>
          </>
        )}

        <FootSignature />
      </div>
    </ErrorBoundary>
  );
}
