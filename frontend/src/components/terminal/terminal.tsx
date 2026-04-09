"use client";

import { useState } from "react";
import { useAuth } from "@/lib/auth";
import { MarketTicker } from "@/components/layout/market-ticker";
import { TerminalNav } from "./terminal-nav";
import { TerminalMetrics } from "./terminal-metrics";
import { TerminalChart } from "./terminal-chart";
import { TerminalTabs } from "./terminal-tabs";
import { RightPanel } from "./right-panel";

export function Terminal() {
  const { user, logout } = useAuth();
  const [panelOpen, setPanelOpen] = useState(true);

  if (!user) return null;

  return (
    <div className="h-[100dvh] flex flex-col overflow-hidden relative" style={{ background: "var(--db-bg)" }}>
      {/* Gradient mesh background */}
      <div className="absolute inset-0 gradient-mesh pointer-events-none" />
      <div className="absolute inset-0 noise-overlay pointer-events-none" />

      {/* Top nav */}
      <div className="relative z-10">
        <TerminalNav
          user={user}
          onLogout={logout}
          onTogglePanel={() => setPanelOpen(!panelOpen)}
          isPanelOpen={panelOpen}
        />
      </div>

      {/* Market ticker */}
      <div className="relative z-10 h-7 glass-surface border-b border-[rgba(255,255,255,0.04)] shrink-0 flex items-center overflow-hidden px-2">
        <MarketTicker />
      </div>

      {/* Metrics strip */}
      <div className="relative z-10">
        <TerminalMetrics />
      </div>

      {/* Main body */}
      <div className="relative z-10 flex flex-1 min-h-0 overflow-hidden">
        {/* Left: Chart + Tabs */}
        <div className="flex-1 flex flex-col min-w-0">
          <div className="flex-[3] min-h-[200px]">
            <TerminalChart />
          </div>
          <div className="flex-[2] min-h-[120px]">
            <TerminalTabs />
          </div>
        </div>

        {/* Right panel */}
        {panelOpen && <RightPanel />}
      </div>
    </div>
  );
}
