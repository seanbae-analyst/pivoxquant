"use client";

import { fmtUsd } from "@/lib/format";
import type { Trade } from "./types";

export function RecentTrades({ trades }: { trades: Trade[] }) {
  return (
    <section className="bg-white">
      <header className="flex items-center justify-between border-b border-slate-200 pb-3">
        <h2 className="font-serif text-[18px] italic text-slate-900">
          Recent Activity
        </h2>
        <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">
          Last {trades.length}
        </span>
      </header>

      <table className="w-full text-[13px]" style={{ tableLayout: "fixed" }}>
        <colgroup>
          <col style={{ width: "22%" }} />
          <col style={{ width: "20%" }} />
          <col style={{ width: "14%" }} />
          <col style={{ width: "14%" }} />
          <col style={{ width: "15%" }} />
          <col style={{ width: "15%" }} />
        </colgroup>
        <thead>
          <tr className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">
            <th className="py-3 pr-2 text-left">Date</th>
            <th className="py-3 pr-2 text-left">Symbol</th>
            <th className="py-3 pr-2 text-left">Action</th>
            <th className="py-3 pr-2 text-right">Qty</th>
            <th className="py-3 pr-2 text-right">Price</th>
            <th className="py-3 pl-2 text-right">Total</th>
          </tr>
        </thead>
        <tbody>
          {trades.map((t) => {
            const total = t.qty * t.price;
            return (
              <tr
                key={t.id}
                className="border-b border-slate-100 text-slate-800 last:border-b-0"
              >
                <td className="py-2.5 pr-2 font-mono tabular-nums text-slate-700">
                  {t.date}
                </td>
                <td className="py-2.5 pr-2 font-mono font-semibold text-slate-900">
                  {t.symbol}
                </td>
                <td className="py-2.5 pr-2">
                  <span
                    className={
                      "inline-flex h-5 items-center rounded-sm px-1.5 text-[10px] font-semibold uppercase tracking-wider " +
                      (t.side === "Bought"
                        ? "bg-emerald-50 text-emerald-700"
                        : "bg-red-50 text-red-700")
                    }
                  >
                    {t.side}
                  </span>
                </td>
                <td className="py-2.5 pr-2 text-right font-mono tabular-nums">
                  {t.qty}
                </td>
                <td className="py-2.5 pr-2 text-right font-mono tabular-nums">
                  {fmtUsd(t.price)}
                </td>
                <td className="py-2.5 pl-2 text-right font-mono tabular-nums">
                  {fmtUsd(total)}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </section>
  );
}
