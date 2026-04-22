"use client";

import { fmtUsd, fmtPct } from "@/lib/format";
import type { Position, TradeAction } from "./types";

interface PositionsTableProps {
  positions: Position[];
  totalMarketValue: number;
  onAction: (action: TradeAction, position: Position) => void;
}

export function PositionsTable({
  positions,
  totalMarketValue,
  onAction,
}: PositionsTableProps) {
  return (
    <section className="bg-white">
      <header className="flex items-center justify-between border-b border-slate-200 pb-3">
        <h2 className="font-serif text-[20px] italic text-slate-900">
          Positions
        </h2>
        <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">
          {positions.length} holdings
        </span>
      </header>

      <div className="overflow-x-auto">
        <table
          className="w-full text-[13px]"
          style={{ tableLayout: "fixed" }}
        >
          <colgroup>
            <col style={{ width: "14%" }} />
            <col style={{ width: "8%" }} />
            <col style={{ width: "10%" }} />
            <col style={{ width: "10%" }} />
            <col style={{ width: "13%" }} />
            <col style={{ width: "13%" }} />
            <col style={{ width: "8%" }} />
            <col style={{ width: "24%" }} />
          </colgroup>
          <thead>
            <tr className="border-b border-slate-200 text-[11px] font-semibold uppercase tracking-wider text-slate-500">
              <th className="py-3 pr-2 text-left">Symbol</th>
              <th className="py-3 pr-2 text-right">Shares</th>
              <th className="py-3 pr-2 text-right">Avg Cost</th>
              <th className="py-3 pr-2 text-right">Current</th>
              <th className="py-3 pr-2 text-right">Market Value</th>
              <th className="py-3 pr-2 text-right">Unreal. P&L</th>
              <th className="py-3 pr-2 text-right">Weight</th>
              <th className="py-3 pl-2 text-right">Actions</th>
            </tr>
          </thead>
          <tbody>
            {positions.map((p) => {
              const mv = p.shares * p.current;
              const cost = p.shares * p.avgCost;
              const pnl = mv - cost;
              const pnlPct = cost > 0 ? (pnl / cost) * 100 : 0;
              const weight =
                totalMarketValue > 0 ? (mv / totalMarketValue) * 100 : 0;
              const pnlTone =
                pnl > 0
                  ? "text-emerald-600"
                  : pnl < 0
                    ? "text-red-600"
                    : "text-slate-500";

              return (
                <tr
                  key={p.id}
                  className="group border-b border-slate-100 transition-colors hover:bg-[#8B6F47]/[0.03]"
                  style={{
                    borderLeft: "2px solid transparent",
                  }}
                >
                  <td className="py-3 pr-2">
                    <div className="flex flex-col">
                      <span className="font-mono text-[13px] font-semibold text-slate-900 group-hover:text-[#8B6F47]">
                        {p.symbol}
                      </span>
                      <span className="truncate text-[11px] text-slate-500">
                        {p.name}
                      </span>
                    </div>
                  </td>
                  <td className="py-3 pr-2 text-right font-mono tabular-nums text-slate-900">
                    {p.shares}
                  </td>
                  <td className="py-3 pr-2 text-right font-mono tabular-nums text-slate-700">
                    {fmtUsd(p.avgCost)}
                  </td>
                  <td className="py-3 pr-2 text-right font-mono tabular-nums text-slate-900">
                    {fmtUsd(p.current)}
                  </td>
                  <td className="py-3 pr-2 text-right font-mono tabular-nums text-slate-900">
                    {fmtUsd(mv)}
                  </td>
                  <td
                    className={
                      "py-3 pr-2 text-right font-mono tabular-nums " + pnlTone
                    }
                  >
                    <div className="flex flex-col items-end leading-tight">
                      <span>{fmtUsd(pnl)}</span>
                      <span className="text-[11px]">{fmtPct(pnlPct)}</span>
                    </div>
                  </td>
                  <td className="py-3 pr-2 text-right font-mono tabular-nums text-slate-700">
                    {weight.toFixed(1)}%
                  </td>
                  <td className="py-3 pl-2">
                    <div className="flex items-center justify-end gap-1.5">
                      <RowButton onClick={() => onAction("buy", p)}>
                        Buy More
                      </RowButton>
                      <RowButton onClick={() => onAction("sell", p)}>
                        Sell
                      </RowButton>
                      <RowButton onClick={() => onAction("edit", p)} ghost>
                        Edit
                      </RowButton>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function RowButton({
  children,
  onClick,
  ghost = false,
}: {
  children: React.ReactNode;
  onClick: () => void;
  ghost?: boolean;
}) {
  const base =
    "h-7 rounded-sm px-2.5 text-[11px] font-medium transition-colors";
  const styles = ghost
    ? "text-slate-600 hover:bg-slate-100"
    : "border border-slate-200 bg-white text-slate-700 hover:border-[#8B6F47] hover:text-[#8B6F47]";
  return (
    <button type="button" onClick={onClick} className={base + " " + styles}>
      {children}
    </button>
  );
}
