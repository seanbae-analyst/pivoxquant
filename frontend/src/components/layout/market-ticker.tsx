"use client";

import { useMarketOverview } from "@/lib/hooks";
import { pnlColor } from "@/lib/format";
import { motion } from "framer-motion";

interface TickerItem {
  label: string;
  price: string;
  change: number;
}

export function MarketTicker() {
  const { data } = useMarketOverview();

  if (!data) return null;

  const m = data.macro as Record<string, unknown>;
  const items: TickerItem[] = [];

  const tryAdd = (key: string, label: string) => {
    const v = m[key];
    if (v && typeof v === "object" && "price" in (v as Record<string, unknown>)) {
      const obj = v as { price: number; change_pct: number };
      items.push({
        label,
        price: obj.price.toLocaleString(undefined, { maximumFractionDigits: 2 }),
        change: obj.change_pct ?? 0,
      });
    }
  };

  tryAdd("sp500", "S&P 500");
  tryAdd("dow", "DOW");
  tryAdd("nasdaq", "NASDAQ");
  tryAdd("kospi", "KOSPI");
  tryAdd("usdkrw", "USD/KRW");
  tryAdd("btc", "BTC");
  tryAdd("gold", "GOLD");

  if (typeof m.vix === "number") {
    items.push({ label: "VIX", price: (m.vix as number).toFixed(1), change: 0 });
  }

  if (items.length === 0) return null;

  const doubled = [...items, ...items];

  return (
    <div className="relative overflow-hidden">
      <motion.div
        className="flex items-center gap-8 whitespace-nowrap py-1"
        animate={{ x: ["0%", "-50%"] }}
        transition={{ duration: 35, ease: "linear", repeat: Infinity }}
      >
        {doubled.map((item, i) => (
          <div key={i} className="flex items-center gap-2 px-1">
            <span className="text-[9px] font-semibold text-zinc-700 uppercase tracking-wider">{item.label}</span>
            <span className="font-mono text-[11px] font-semibold text-zinc-400">{item.price}</span>
            {item.change !== 0 && (
              <span className={`font-mono text-[10px] font-semibold ${pnlColor(item.change)}`}>
                {item.change >= 0 ? "+" : ""}{item.change.toFixed(2)}%
              </span>
            )}
          </div>
        ))}
      </motion.div>
    </div>
  );
}
