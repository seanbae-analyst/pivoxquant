"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { OverviewTab } from "@/components/market/overview-tab";
import { IntradayTab } from "@/components/market/intraday-tab";
import { ScannerTab } from "@/components/market/scanner-tab";

type Tab = "overview" | "intraday" | "scanner";

const tabs: { key: Tab; label: string }[] = [
  { key: "overview", label: "Overview" },
  { key: "intraday", label: "Intraday" },
  { key: "scanner", label: "Scanner" },
];

export default function MarketPage() {
  const [tab, setTab] = useState<Tab>("overview");

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      {/* Tab header */}
      <div className="flex items-center gap-1 rounded-lg border border-border bg-card p-1">
        {tabs.map((t) => (
          <Button
            key={t.key}
            variant={tab === t.key ? "default" : "ghost"}
            size="sm"
            onClick={() => setTab(t.key)}
            className="flex-1"
          >
            {t.label}
          </Button>
        ))}
      </div>

      {/* Tab content */}
      {tab === "overview" && <OverviewTab />}
      {tab === "intraday" && <IntradayTab />}
      {tab === "scanner" && <ScannerTab />}
    </div>
  );
}
