"use client";

/**
 * <RecentTransactionsBlock /> — corner card with recent trade entries.
 *
 * Mockup §BLOCK 3c / SPEC §4.3.
 * Action vocabulary mapped legal-safe: buy → 추가, sell → 정리/전량 정리.
 * Uses local hooks-v2.ts → useTransactions() (does NOT touch lib/hooks.ts).
 *
 * 2026-10-09: no "전체 내역 ›" footer. It linked to /portfolio — the page
 * this card sits on (on a phone, its own pager page) — because there is no
 * full trade-history screen to send it to. A link that promises a screen we
 * do not have is gone until that screen exists.
 */

import * as React from "react";
import { fmtMoneyPlain, pctColor, displayTicker, parseIsoUtc } from "@/lib/format";
import { useLocale } from "@/lib/locale";
import { useIsPhone } from "@/lib/use-phone";
import { useTransactions, type TransactionRow } from "./hooks-v2";

interface RecentTransactionsBlockProps {
  limit?: number;
}

/** `source` of the BUY row written when a holding is registered. */
export const HOLDING_SEED_SOURCE = "holding_seed";
/** `source` of the SELL row written when a holding is lowered by an edit or a
 *  holdings-capture replace, with no recorded sale (2026-09-29). */
export const HOLDING_ADJUST_SOURCE = "holding_adjust";

/** Map backend `side`/`action` to legal-safe display verb. */
function actionLabel(
  row: TransactionRow,
  seedLabel: string,
  adjustLabel: string,
): {
  label: string;
  signed: 1 | -1 | 0;
} {
  // 2026-09-29: a holding-registration seed is stored as a BUY dated the day
  // the holding was entered. Calling it "Add" states a purchase on that day,
  // which never happened — label the registration and drop the cash sign.
  if (row.source === HOLDING_SEED_SOURCE) return { label: seedLabel, signed: 0 };
  // Same for the adjust row: a lowered holding, not a sale on that day.
  if (row.source === HOLDING_ADJUST_SOURCE) return { label: adjustLabel, signed: 0 };
  const a = (row.action ?? "").toLowerCase();
  const s = (row.side ?? "").toLowerCase();
  if (a === "add" || s === "buy" || s === "bought") return { label: "추가", signed: -1 };
  if (a === "trim" || s === "sell" || s === "sold") return { label: "정리", signed: +1 };
  if (a === "close") return { label: "전량 정리", signed: +1 };
  if (a === "deposit") return { label: "입금", signed: +1 };
  if (a === "withdraw") return { label: "출금", signed: -1 };
  return { label: row.action ?? row.side ?? "기록", signed: 0 };
}

// Wave 4-B (2026-05-20): migrated to lib/fmtMoneyPlain.
// fmtMoneyPlain(n, currency, currency==="KRW" ? 0 : 2) is byte-identical to
// the old local helper for non-negative `n` (the only path exercised: the
// caller always passes Math.abs(amount)). Migration locks USD 2-decimal
// across all magnitudes — the original Wave 2 "keep 2dp" concern is now
// preserved in lib via the explicit `dp=2` argument.
// eslint-disable-next-line no-restricted-syntax -- local fmt* helper kept per Wave 2/4-B sweep (delegates to, or intentionally diverges from, @/lib/format); see adjacent note
function fmtMoney(n: number, currency: "USD" | "KRW"): string {
  return fmtMoneyPlain(n, currency, currency === "KRW" ? 0 : 2);
}

function fmtSignedAmount(amount: number, signed: number, currency: "USD" | "KRW"): string {
  if (!Number.isFinite(amount) || amount === 0) return "—";
  const sign = signed > 0 ? "+" : signed < 0 ? "−" : "";
  return `${sign}${fmtMoney(Math.abs(amount), currency)}`;
}

/* 2026-09-19: was `new Date(iso).toLocaleDateString("en-US", …)` — English
   month names under the ko locale, a naive-ISO stamp parsed as LOCAL time
   (the 9h KST drift `parseIsoUtc` exists to stop), and no Asia/Seoul pin, so
   the printed day could differ from the day /journal shows for the same row.
   All three closed here; ko now reads "9. 15." like the rest of the app. */
function shortDate(iso: string | undefined, locale: "ko" | "en"): string {
  if (!iso) return "—";
  const d = parseIsoUtc(iso);
  if (!d) return iso;
  return d.toLocaleDateString(locale === "ko" ? "ko-KR" : "en-US", {
    timeZone: "Asia/Seoul",
    month: locale === "ko" ? "numeric" : "short",
    day: "numeric",
  });
}

// Cash-flow direction color via the site-canonical KR convention helper
// (lib/format.pctColor): inflow (+) → carmine #D18888, outflow (−) → indigo
// #7AA0C8, neutral → muted ivory. The old local helper inverted this
// (inflow → bronze), diverging from detail/watchlist.
function amountColor(signed: number): string {
  return pctColor(signed);
}

/** KST calendar day of a stamp — "2026-06-15" — or null when unparseable. */
export function kstDayKey(iso: string | undefined): string | null {
  if (!iso) return null;
  const d = parseIsoUtc(iso);
  if (!d) return null;
  return d.toLocaleDateString("en-CA", { timeZone: "Asia/Seoul" });
}

/** "6월 15일 (월)" / "Jun 15 (Mon)" — the day header of a phone group. */
function dayHeading(iso: string | undefined, locale: "ko" | "en"): string {
  const d = iso ? parseIsoUtc(iso) : null;
  if (!d) return "—";
  const tz = "Asia/Seoul";
  if (locale === "ko") {
    const md = d.toLocaleDateString("ko-KR", { timeZone: tz, month: "long", day: "numeric" });
    const wd = d.toLocaleDateString("ko-KR", { timeZone: tz, weekday: "short" });
    return `${md} (${wd})`;
  }
  const md = d.toLocaleDateString("en-US", { timeZone: tz, month: "short", day: "numeric" });
  const wd = d.toLocaleDateString("en-US", { timeZone: tz, weekday: "short" });
  return `${md} (${wd})`;
}

/** Consecutive rows of the same KST day, in the order the backend sent them. */
export function groupByDay<T extends { date?: string }>(rows: T[]): Array<{ key: string; date?: string; rows: T[] }> {
  const groups: Array<{ key: string; date?: string; rows: T[] }> = [];
  for (const r of rows) {
    const key = kstDayKey(r.date) ?? "unknown";
    const last = groups[groups.length - 1];
    if (last && last.key === key) last.rows.push(r);
    else groups.push({ key, date: r.date, rows: [r] });
  }
  return groups;
}

export function RecentTransactionsBlock({
  limit = 7,
}: RecentTransactionsBlockProps) {
  const { locale, t } = useLocale();
  const isPhone = useIsPhone();
  const { data, isLoading, error } = useTransactions(limit);

  const trades: TransactionRow[] = React.useMemo(() => {
    if (!data) return [];
    return (data.trades ?? data.transactions ?? []).slice(0, limit);
  }, [data, limit]);

  // Phone (2026-10-10, CEO "앱처럼"): no boxed card repeating the tab's own
  // name — a list grouped under day headers, the way a banking app shows a
  // statement. Same rows, labels, amounts and colours as the card below.
  if (isPhone) {
    return (
      <PhoneActivity
        trades={trades}
        loading={isLoading && trades.length === 0}
        failed={Boolean(error)}
        locale={locale}
        t={t}
      />
    );
  }

  return (
    <div
      className="pq-card"
      style={{
        background: "var(--pq-card-bg-ink, rgba(255,255,255,0.02))",
        border: "1px solid var(--pq-hairline-ink, var(--pq-ivory-line))",
        borderRadius: "var(--pq-radius-card, 4px)",
        padding: 24,
        minHeight: 380,
        display: "flex",
        flexDirection: "column",
      }}
    >
      <div
        className="font-mono"
        style={{
          fontSize: "var(--pq-text-eyebrow)",
          letterSpacing: "0.02em",
          color: "var(--pq-bronze)",
          marginBottom: 20,
        }}
      >
        최근 활동
      </div>

      {isLoading && trades.length === 0 ? (
        <div
          style={{
            flex: 1,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            color: "var(--pq-ivory-dim)",
            fontSize: "var(--pq-text-body)",
          }}
        className="font-serif" >
          {t("dashboard.portfolio.activity.loading")}
        </div>
      ) : error || trades.length === 0 ? (
        <div
          style={{
            flex: 1,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            color: "var(--pq-ivory-dim)",
            fontSize: "var(--pq-text-body)",
          }}
        className="font-serif" >
          {t("dashboard.portfolio.activity.empty")}
        </div>
      ) : (
        <ul
          style={{
            flex: 1,
            listStyle: "none",
            padding: 0,
            margin: 0,
            display: "flex",
            flexDirection: "column",
          }}
        >
          {trades.map((tx, i) => {
            const { label, signed } = actionLabel(
              tx,
              t("dashboard.portfolio.activity.holdingAdded"),
              t("dashboard.portfolio.activity.holdingAdjusted"),
            );
            const cur = (tx.currency as "USD" | "KRW") ?? "USD";
            const shares = tx.qty ?? tx.shares ?? 0;
            const price = tx.price ?? 0;
            const amount = (tx.amount ?? shares * price) || 0;
            // The action verb is the legal-safe 추가 / 정리 / 전량 정리
            // vocabulary pinned by this file's header (never 매수/매도). The
            // holding-registration label is not a trade verb, so it is i18n.
            const meta = `${label} · ${t("dashboard.portfolio.activity.sharesUnit", { n: String(shares) })} @ ${fmtMoney(price, cur)} · ${shortDate(tx.date, locale)}`;
            return (
              <li
                key={tx.id ?? `${tx.symbol}-${tx.date}-${i}`}
                style={{
                  display: "grid",
                  gridTemplateColumns: "1fr auto",
                  gap: 12,
                  padding: "10px 0",
                  alignItems: "center",
                  borderBottom:
                    i < trades.length - 1
                      ? "1px solid var(--pq-hairline-ink, var(--pq-ivory-line-soft))"
                      : "none",
                }}
              >
                <div>
                  <div
                    className="font-display"
                    style={{
                      fontSize: "var(--pq-text-body)",
                      fontWeight: 500,
                      color: "var(--pq-ivory)",
                      lineHeight: 1.2,
                    }}
                  >
                    {tx.symbol ? displayTicker(tx.symbol, tx.name) : (tx.name ?? "—")}
                  </div>
                  <div
                    className="font-serif"
                    style={{
                      fontSize: "var(--pq-text-eyebrow)",
                      color: "var(--pq-ivory-dim)",
                      marginTop: 2,
                    }}
                  >
                    {meta}
                  </div>
                </div>
                <span
                  className="font-mono tabular-nums"
                  style={{
                    fontSize: "var(--pq-text-body)",
                    color: amountColor(signed),
                    whiteSpace: "nowrap",
                  }}
                >
                  {fmtSignedAmount(amount, signed, cur)}
                </span>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}

function PhoneActivity({
  trades,
  loading,
  failed,
  locale,
  t,
}: {
  trades: TransactionRow[];
  loading: boolean;
  failed: boolean;
  locale: "ko" | "en";
  t: (key: string, params?: Record<string, string>) => string;
}) {
  if (loading) {
    return (
      <section aria-label="최근 활동" aria-busy="true" data-testid="activity-phone">
        <div role="status" className="sr-only">{t("dashboard.portfolio.activity.loading")}</div>
        <ul aria-hidden className="-mx-4">
          {[0, 1, 2, 3].map((i) => (
            <li key={i} className="flex items-center justify-between gap-3 px-4 py-3.5">
              <span className="flex flex-col gap-2">
                <span className="pq-skeleton-dark block h-4 w-24" />
                <span className="pq-skeleton-dark block h-3 w-36" />
              </span>
              <span className="pq-skeleton-dark block h-4 w-20" />
            </li>
          ))}
        </ul>
      </section>
    );
  }
  if (failed || trades.length === 0) {
    return (
      <section
        aria-label="최근 활동"
        data-testid="activity-phone"
        className="flex min-h-[40vh] items-center justify-center px-4 text-center text-pq-body text-[var(--pq-ivory-dim)]"
      >
        {t("dashboard.portfolio.activity.empty")}
      </section>
    );
  }
  return (
    <section aria-label="최근 활동" data-testid="activity-phone" className="-mx-4">
      {groupByDay(trades).map((g, gi) => (
        <div key={g.key} role="group" aria-label={dayHeading(g.date, locale)}>
          {/* Not sticky: an opaque sticky band would cut across the page's
              background light. */}
          <div
            aria-hidden
            className={`px-4 pb-2 text-pq-caption text-[var(--pq-ivory-dim)] ${gi === 0 ? "pt-0" : "pt-5"}`}
          >
            {dayHeading(g.date, locale)}
          </div>
          <ul className="border-y border-[var(--pq-ivory-line)]">
            {g.rows.map((tx, i) => {
              const { label, signed } = actionLabel(
                tx,
                t("dashboard.portfolio.activity.holdingAdded"),
                t("dashboard.portfolio.activity.holdingAdjusted"),
              );
              const cur = (tx.currency as "USD" | "KRW") ?? "USD";
              const shares = tx.qty ?? tx.shares ?? 0;
              const price = tx.price ?? 0;
              const amount = (tx.amount ?? shares * price) || 0;
              return (
                <li
                  key={tx.id ?? `${tx.symbol}-${tx.date}-${i}`}
                  className={`flex min-h-[60px] items-center justify-between gap-3 px-4 py-3 ${
                    i > 0 ? "border-t border-[var(--pq-ivory-line)]" : ""
                  }`}
                  data-testid="activity-row"
                >
                  <div className="min-w-0">
                    <div className="truncate text-pq-lead font-medium text-[var(--pq-ivory)]">
                      {tx.symbol ? displayTicker(tx.symbol, tx.name) : (tx.name ?? "—")}
                    </div>
                    <div className="mt-0.5 truncate font-mono text-pq-caption tabular-nums text-[var(--pq-ivory-dim)]">
                      {label} · {t("dashboard.portfolio.activity.sharesUnit", { n: String(shares) })} @ {fmtMoney(price, cur)}
                    </div>
                  </div>
                  <span
                    className="shrink-0 font-mono text-pq-body tabular-nums"
                    style={{ color: amountColor(signed) }}
                  >
                    {fmtSignedAmount(amount, signed, cur)}
                  </span>
                </li>
              );
            })}
          </ul>
        </div>
      ))}
    </section>
  );
}

export default RecentTransactionsBlock;
