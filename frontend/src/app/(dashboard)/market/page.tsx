"use client";

import { useState } from "react";
import { OverviewTab } from "@/components/market/overview-tab";
import { IntradayTab } from "@/components/market/intraday-tab";
import { ScannerTab } from "@/components/market/scanner-tab";
import { motion } from "framer-motion";
import { Globe, TrendingUp, Search } from "lucide-react";

type Tab = "overview" | "intraday" | "scanner";

const tabs = [
  { key: "overview" as Tab, label: "Overview", desc: "Macro & Indices", icon: Globe },
  { key: "intraday" as Tab, label: "Intraday", desc: "Day Trading", icon: TrendingUp },
  { key: "scanner" as Tab, label: "Scanner", desc: "Discovery", icon: Search },
];

export default function MarketPage() {
  const [tab, setTab] = useState<Tab>("overview");

  return (
    <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }} className="space-y-5">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-white" style={{ fontFamily: "var(--font-geist-heading), sans-serif" }}>
          Market
        </h1>
        <p className="mt-1 text-[13px] text-zinc-600">Real-time market data, indices, and stock discovery</p>
      </div>

      {/* Tab bar */}
      <div className="flex gap-2">
        {tabs.map((t) => (
          <button key={t.key} onClick={() => setTab(t.key)}
            className={`flex items-center gap-3 rounded-xl px-5 py-3 text-sm font-medium spring-transition transition-all duration-300 border ${
              tab === t.key
                ? "bg-emerald-500/6 border-emerald-500/15 text-white shadow-[0_0_24px_rgba(16,185,129,0.06)]"
                : "border-[rgba(255,255,255,0.04)] bg-[rgba(255,255,255,0.02)] text-zinc-500 hover:text-zinc-300 hover:bg-[rgba(255,255,255,0.04)] hover:border-[rgba(255,255,255,0.08)]"
            }`}
          >
            <t.icon size={16} className={tab === t.key ? "text-emerald-400" : ""} />
            <div className="text-left">
              <p className="font-semibold">{t.label}</p>
              <p className={`text-[10px] ${tab === t.key ? "text-zinc-400" : "text-zinc-600"}`}>{t.desc}</p>
            </div>
          </button>
        ))}
      </div>

      {tab === "overview" && <OverviewTab />}
      {tab === "intraday" && <IntradayTab />}
      {tab === "scanner" && <ScannerTab />}
    </motion.div>
  );
}
