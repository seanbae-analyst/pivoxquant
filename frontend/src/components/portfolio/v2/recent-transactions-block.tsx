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
import { fmtMoneyPlain } from "@/lib/format";
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
function fmtMoney(n: number, currency: "USD" | "KRW"): string {
  return fmtMoneyPlain(n, currency, currency === "KRW" ? 0 : 2);
}

function fmtSignedAmount(amount: number, signed: number, currency: "USD" | "KRW"): string {
  if (!Number.isFinite(amount) || amount === 0) return "—";
  const sign = signed > 0 ? "+" : signed < 0 ? "−" : "";
  return `${sign}${fmtMoney(Math.abs(amount), currency)}`;
}

function shortDate(iso?: string): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

function amountColor(signed: number): string {
  if (signed > 0) return "var(--pq-positive, #b8956a)"; // KR convention
  if (signed < 0) return "var(--pq-negative, #d18888)";
  return "rgba(245,240,232,0.55)";
}

export function RecentTransactionsBlock({
  limit = 7,
}: RecentTransactionsBlockProps) {
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
            color: "rgba(245,240,232,0.55)",
            fontSize: "var(--pq-text-body)",
          }}
        className="font-serif" >
          Loading entries…
        </div>
      ) : error || trades.length === 0 ? (
        <div
          style={{
            flex: 1,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            color: "rgba(245,240,232,0.55)",
            fontSize: "var(--pq-text-body)",
          }}
        className="font-serif" >
          No recent entries.
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
          {trades.map((t, i) => {
            const { label, signed } = actionLabel(t);
            const cur = (t.currency as "USD" | "KRW") ?? "USD";
            const shares = t.qty ?? t.shares ?? 0;
            const price = t.price ?? 0;
            const amount = (t.amount ?? shares * price) || 0;
            const meta = `${label} · ${shares} sh @ ${fmtMoney(price, cur)} · ${shortDate(t.date)}`;
            return (
              <li
                key={t.id ?? `${t.symbol}-${t.date}-${i}`}
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
                    {t.name ?? t.symbol ?? "—"}
                  </div>
                  <div
                    className="font-serif"
                    style={{
                      fontSize: "var(--pq-text-eyebrow)",
                      color: "rgba(245,240,232,0.55)",
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
