"use client";

/**
 * <RecentTransactionsBlock /> — corner card with recent trade entries.
 *
 * Mockup §BLOCK 3c / SPEC §4.3.
 * Action vocabulary mapped legal-safe: buy → Add, sell → Trim/Close.
 * Uses local hooks-v2.ts → useTransactions() (does NOT touch lib/hooks.ts).
 */

import * as React from "react";
import Link from "next/link";
import { fmtMoneyPlain, pctColor, displayTicker, parseIsoUtc } from "@/lib/format";
import { useLocale } from "@/lib/locale";
import { useTransactions, type TransactionRow } from "./hooks-v2";

interface RecentTransactionsBlockProps {
  limit?: number;
}

/** Map backend `side`/`action` to legal-safe display verb. */
function actionLabel(row: TransactionRow): {
  label: string;
  signed: 1 | -1 | 0;
} {
  const a = (row.action ?? "").toLowerCase();
  const s = (row.side ?? "").toLowerCase();
  if (a === "add" || s === "buy" || s === "bought") return { label: "Add", signed: -1 };
  if (a === "trim" || s === "sell" || s === "sold") return { label: "Trim", signed: +1 };
  if (a === "close") return { label: "Close", signed: +1 };
  if (a === "deposit") return { label: "Deposit", signed: +1 };
  if (a === "withdraw") return { label: "Withdraw", signed: -1 };
  return { label: row.action ?? row.side ?? "Entry", signed: 0 };
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

export function RecentTransactionsBlock({
  limit = 7,
}: RecentTransactionsBlockProps) {
  const { locale, t } = useLocale();
  const { data, isLoading, error } = useTransactions(limit);

  const trades: TransactionRow[] = React.useMemo(() => {
    if (!data) return [];
    return (data.trades ?? data.transactions ?? []).slice(0, limit);
  }, [data, limit]);

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
        className="font-mono uppercase"
        style={{
          fontSize: "var(--pq-text-eyebrow)",
          letterSpacing: "0.22em",
          color: "var(--pq-bronze)",
          marginBottom: 20,
        }}
      >
        Activity · Recent
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
            const { label, signed } = actionLabel(tx);
            const cur = (tx.currency as "USD" | "KRW") ?? "USD";
            const shares = tx.qty ?? tx.shares ?? 0;
            const price = tx.price ?? 0;
            const amount = (tx.amount ?? shares * price) || 0;
            // `sh` and the month name are units and a date, i.e. data — not
            // the English app-shell labels. The action verb stays English on
            // purpose: Add / Trim / Close is the legal-safe vocabulary pinned
            // by this file's header, not a style choice to make here.
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

      <div
        style={{
          marginTop: 16,
          paddingTop: 12,
          borderTop: "1px solid var(--pq-hairline-ink, var(--pq-ivory-line))",
          display: "flex",
          alignItems: "center",
          justifyContent: "flex-end",
        }}
      >
        <Link
          href="/portfolio"
          className="font-mono uppercase"
          style={{
            fontSize: "var(--pq-text-eyebrow)",
            letterSpacing: "0.2em",
            color: "var(--pq-bronze)",
            textDecoration: "none",
            borderBottom: "1px solid rgba(184,149,106,0.35)",
            paddingBottom: 1,
          }}
        >
          Open ledger ›
        </Link>
      </div>
    </div>
  );
}

export default RecentTransactionsBlock;
