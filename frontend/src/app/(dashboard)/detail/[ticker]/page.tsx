"use client";

import { useState, useMemo } from "react";
import { useParams, useRouter } from "next/navigation";
import useSWR from "swr";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { usePortfolio, useAiStatus } from "@/lib/hooks";
import { apiFetch } from "@/lib/api";
import { API } from "@/lib/endpoints";
import { fmtUsd, fmtPct, pnlColor, scoreColor } from "@/lib/format";
import { QuickBuyModal, QuickSellModal, BuyNewModal } from "@/components/dashboard/action-modals";
import type {
  Position,
  AiSwotResponse,
  AiCommentaryResponse,
  AiCompetitorResponse,
  AiSectorTrendResponse,
} from "@/lib/types";
import { motion, AnimatePresence } from "framer-motion";

const fetcher = (url: string) => fetch(url, { credentials: "include" }).then((r) => r.json());

/* ── Tab definitions ── */
const TABS = [
  { id: "overview", label: "Overview", icon: "M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-4 0a1 1 0 01-1-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 01-1 1" },
  { id: "chart", label: "Chart", icon: "M7 12l3-3 3 3 4-4M8 21l4-4 4 4M3 4h18M4 4v16" },
  { id: "fundamentals", label: "Fundamentals", icon: "M9 7h6m0 10v-3m-3 3h.01M9 17h.01M9 14h.01M12 14h.01M15 11h.01M12 11h.01M9 11h.01M7 21h10a2 2 0 002-2V5a2 2 0 00-2-2H7a2 2 0 00-2 2v14a2 2 0 002 2z" },
  { id: "ai", label: "AI Analysis", icon: "M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" },
  { id: "news", label: "News", icon: "M19 20H5a2 2 0 01-2-2V6a2 2 0 012-2h10a2 2 0 012 2v1m2 13a2 2 0 01-2-2V7m2 13a2 2 0 002-2V9a2 2 0 00-2-2h-2m-4-3H9M7 16h6M7 8h6v4H7V8z" },
  { id: "technicals", label: "Technicals", icon: "M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" },
  { id: "backtest", label: "Backtest", icon: "M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" },
] as const;

type TabId = (typeof TABS)[number]["id"];

/* ── Spinner component ── */
function Spinner({ size = "sm" }: { size?: "sm" | "md" }) {
  const cls = size === "md" ? "h-5 w-5" : "h-3 w-3";
  return <span className={`${cls} animate-spin rounded-full border border-current border-t-transparent inline-block`} />;
}

/* ── Section label ── */
function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <p className="mb-4 font-mono text-[10px] font-semibold uppercase tracking-[1.2px] text-muted-foreground/50">
      {children}
    </p>
  );
}

/* ── Stat box ── */
function StatBox({ label, value, color }: { label: string; value: string | number; color?: string }) {
  return (
    <div className="rounded-lg bg-muted/20 p-2.5 text-center">
      <p className="text-[9px] uppercase tracking-wider text-muted-foreground/40">{label}</p>
      <p className={`mt-0.5 font-mono text-sm font-bold ${color ?? "text-foreground"}`}>{value}</p>
    </div>
  );
}

export default function DetailPage() {
  const params = useParams();
  const router = useRouter();
  const ticker = decodeURIComponent(params.ticker as string);
  const { data: portfolio, mutate: refreshPortfolio } = usePortfolio();
  const { data: analysis, mutate: refreshAnalysis } = useSWR(API.signals.one(ticker), fetcher);

  const position = portfolio?.positions.find((p) => p.ticker === ticker);

  const [activeTab, setActiveTab] = useState<TabId>("overview");

  const price = analysis?.price ?? position?.current_price ?? 0;
  const priceDisplay = analysis?.price_display ?? `$${price}`;
  const currency = analysis?.is_korean ? "KRW" : "USD";

  const handleTradeDone = () => {
    refreshPortfolio();
    refreshAnalysis();
  };

  const handleDelete = async () => {
    if (!position || !confirm(`Delete ${ticker}?`)) return;
    await apiFetch(API.portfolio.deletePosition(position.id), { method: "DELETE" });
    refreshPortfolio(); router.push("/dashboard");
  };

  /* ── Loading state ── */
  if (!analysis) {
    return (
      <div className="flex flex-col items-center justify-center py-20">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
        <span className="mt-3 font-mono text-[10px] tracking-wider text-muted-foreground/40">ANALYZING {ticker}</span>
      </div>
    );
  }

  const signalBg = analysis.signal === "BUY"
    ? "border-success/30 bg-success/10 text-success"
    : analysis.signal === "SELL"
      ? "border-destructive/30 bg-destructive/10 text-destructive"
      : "border-border bg-muted/30 text-muted-foreground";

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.4 }}
      className="mx-auto max-w-4xl space-y-4"
    >
      {/* Back */}
      <button onClick={() => router.back()} className="flex items-center gap-1.5 text-xs text-muted-foreground/50 transition hover:text-muted-foreground">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M19 12H5M12 19l-7-7 7-7" /></svg>
        Back
      </button>

      {/* Hero Header — always visible */}
      <Card className="glass-card overflow-hidden p-5">
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0">
            <div className="flex items-center gap-2.5 flex-wrap">
              <h1 className="text-xl font-bold text-foreground sm:text-2xl">{analysis.name ?? ticker}</h1>
              <Badge variant="outline" className={`text-xs font-bold ${signalBg}`}>
                {analysis.signal}
              </Badge>
            </div>
            <p className="mt-1 text-xs text-muted-foreground/60">
              {ticker} · {analysis.sector ?? ""} · {analysis.is_korean ? "KRX" : "NYSE/NASDAQ"}
            </p>
          </div>
          <div className="text-right shrink-0">
            <p className="text-2xl font-bold text-foreground sm:text-3xl">{priceDisplay}</p>
            <p className={`mt-0.5 text-sm font-semibold ${pnlColor(analysis.change_pct ?? 0)}`}>
              {(analysis.change_pct ?? 0) >= 0 ? "+" : ""}{(analysis.change_pct ?? 0).toFixed(2)}%
            </p>
          </div>
        </div>

        {/* Score bar */}
        <div className="mt-4">
          <div className="flex items-center justify-between text-xs">
            <span className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground/40">Quant Score</span>
            <span className={`font-mono text-sm font-bold ${scoreColor(analysis.score ?? 0)}`}>{analysis.score?.toFixed(1)}/100</span>
          </div>
          <div className="mt-1.5 h-1.5 w-full overflow-hidden rounded-full bg-muted/50">
            <div className={`h-full rounded-full transition-all duration-1000 ${scoreColor(analysis.score ?? 0)}`} style={{ width: `${analysis.score ?? 0}%` }} />
          </div>
        </div>
      </Card>

      {/* Tab Navigation */}
      <div className="scrollbar-hide -mx-1 flex gap-1 overflow-x-auto px-1 pb-1">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`shrink-0 rounded-lg px-3 py-2 text-xs font-semibold transition-all duration-200 ${
              activeTab === tab.id
                ? "bg-primary/15 text-primary border border-primary/25"
                : "text-muted-foreground/60 hover:text-muted-foreground hover:bg-muted/30 border border-transparent"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      <AnimatePresence mode="wait">
        <motion.div
          key={activeTab}
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -8 }}
          transition={{ duration: 0.2 }}
          className="space-y-4"
        >
          {activeTab === "overview" && (
            <OverviewTab
              analysis={analysis}
              position={position}
              ticker={ticker}
              price={price}
              priceDisplay={priceDisplay}
              currency={currency}
              onTradeDone={handleTradeDone}
              handleDelete={handleDelete}
            />
          )}
          {activeTab === "chart" && <ChartTab ticker={ticker} isKorean={analysis.is_korean} />}
          {activeTab === "fundamentals" && <FundamentalsTab analysis={analysis} ticker={ticker} />}
          {activeTab === "ai" && <AIAnalysisTab analysis={analysis} />}
          {activeTab === "news" && <NewsTab ticker={ticker} />}
          {activeTab === "technicals" && <TechnicalsTab analysis={analysis} />}
          {activeTab === "backtest" && <BacktestTab ticker={ticker} />}
        </motion.div>
      </AnimatePresence>
    </motion.div>
  );
}

/* ══════════════════════════════════════════════════════
   TAB 1: OVERVIEW
   ══════════════════════════════════════════════════════ */
interface OverviewProps {
  analysis: Record<string, unknown>;
  position: Position | undefined;
  ticker: string;
  price: number;
  priceDisplay: string;
  currency: string;
  onTradeDone: () => void;
  handleDelete: () => void;
}

function OverviewTab({ analysis, position, ticker, price, priceDisplay, currency, onTradeDone, handleDelete }: OverviewProps) {
  const a = analysis as Record<string, unknown>;
  const snap = a.snapshot as Record<string, number | string | null> | undefined;

  return (
    <>
      {/* Score Breakdown + Key Stats */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card className="glass-card p-5">
          <SectionLabel>Score Breakdown</SectionLabel>
          <div className="grid grid-cols-4 gap-3 text-center">
            {[
              { label: "Technical", score: a.tech_score as number },
              { label: "Fundamental", score: a.fund_score as number },
              { label: "Sentiment", score: a.news_score as number },
              { label: "Quant", score: a.quant_score as number },
            ].map((s) => (
              <div key={s.label} className="rounded-lg bg-muted/20 p-3">
                <p className="text-[9px] uppercase tracking-wider text-muted-foreground/40">{s.label}</p>
                <p className={`mt-1 text-xl font-bold ${scoreColor(s.score ?? 0)}`}>{(s.score ?? 0).toFixed(0)}</p>
                <div className="mx-auto mt-1.5 h-1 w-10 overflow-hidden rounded-full bg-muted/50">
                  <div className={`h-full rounded-full ${scoreColor(s.score ?? 0)}`} style={{ width: `${s.score ?? 0}%` }} />
                </div>
              </div>
            ))}
          </div>
        </Card>

        {snap && (
          <Card className="glass-card p-5">
            <SectionLabel>Key Stats</SectionLabel>
            <div className="grid grid-cols-4 gap-2 text-xs">
              {[
                { label: "P/E", value: (snap.pe_ratio as number)?.toFixed(1) },
                { label: "EPS", value: (snap.eps as number)?.toFixed(2) },
                { label: "Beta", value: (snap.beta as number)?.toFixed(2) },
                { label: "MCap", value: snap.market_cap ? `$${((snap.market_cap as number) / 1e9).toFixed(1)}B` : null },
              ].filter(f => f.value).map((f) => (
                <StatBox key={f.label} label={f.label} value={f.value!} />
              ))}
            </div>
          </Card>
        )}
      </div>

      {/* Signals */}
      <Card className="glass-card p-5">
        <SectionLabel>
          Signals ({(a.signals as unknown[])?.length ?? 0})
        </SectionLabel>
        <div className="space-y-1">
          {(a.signals as Array<{type: string; msg: string}>)?.map((s, i) => (
            <p key={i} className={`rounded-md px-2.5 py-1.5 text-xs ${
              s.type === "bullish" ? "bg-success/5 text-success" : s.type === "bearish" ? "bg-destructive/5 text-destructive" : "text-muted-foreground"
            }`}>
              {s.type === "bullish" ? "▲" : s.type === "bearish" ? "▼" : "●"} {s.msg}
            </p>
          ))}
        </div>
      </Card>

      {/* TP/SL */}
      {((a.take_profit as number) || (a.stop_loss as number)) && (
        <div className="grid grid-cols-2 gap-4">
          {(a.take_profit as number) > 0 && (
            <Card className="glass-card border-success/10 p-5 text-center">
              <p className="text-[10px] font-medium uppercase tracking-wider text-success/50">Take Profit</p>
              <p className="mt-1 text-xl font-bold text-success">
                {a.is_korean ? `₩${(a.take_profit as number)?.toLocaleString()}` : fmtUsd(a.take_profit as number)}
              </p>
              <p className="mt-0.5 text-xs text-success/50">{fmtPct(a.tp_pct as number)}</p>
            </Card>
          )}
          {(a.stop_loss as number) > 0 && (
            <Card className="glass-card border-destructive/10 p-5 text-center">
              <p className="text-[10px] font-medium uppercase tracking-wider text-destructive/50">Stop Loss</p>
              <p className="mt-1 text-xl font-bold text-destructive">
                {a.is_korean ? `₩${(a.stop_loss as number)?.toLocaleString()}` : fmtUsd(a.stop_loss as number)}
              </p>
              <p className="mt-0.5 text-xs text-destructive/50">{fmtPct(a.sl_pct as number)}</p>
            </Card>
          )}
        </div>
      )}

      {/* Position + Trade */}
      {position && (
        <>
          <Card className="glass-card p-5">
            <SectionLabel>Your Position</SectionLabel>
            <div className="grid grid-cols-3 gap-4 text-center">
              <div className="rounded-lg bg-muted/20 p-3">
                <p className="text-[9px] uppercase text-muted-foreground/40">Shares</p>
                <p className="mt-1 text-lg font-bold text-foreground">{position.shares as number}</p>
              </div>
              <div className="rounded-lg bg-muted/20 p-3">
                <p className="text-[9px] uppercase text-muted-foreground/40">Avg Cost</p>
                <p className="mt-1 text-lg font-bold text-foreground">{fmtUsd(position.avg_cost as number)}</p>
              </div>
              <div className="rounded-lg bg-muted/20 p-3">
                <p className="text-[9px] uppercase text-muted-foreground/40">P&L</p>
                <p className={`mt-1 text-lg font-bold ${pnlColor(position.pnl_pct as number)}`}>{(position.pnl_pct as number) >= 0 ? "+" : ""}{fmtPct(position.pnl_pct as number)}</p>
              </div>
            </div>
          </Card>

          <div className="flex items-center gap-2">
            <QuickBuyModal
              positionId={position.id}
              ticker={ticker}
              currentPrice={price}
              priceDisplay={priceDisplay}
              recShares={a.rec_shares as number | undefined}
              currency={currency}
              onDone={onTradeDone}
            />
            <QuickSellModal
              positionId={position.id}
              ticker={ticker}
              currentPrice={price}
              priceDisplay={priceDisplay}
              maxShares={position.shares as number}
              avgCost={position.avg_cost as number}
              currency={currency}
              onDone={onTradeDone}
            />
          </div>

          <button onClick={handleDelete} className="w-full text-center text-[11px] text-muted-foreground/25 transition hover:text-destructive">
            Remove from portfolio
          </button>
        </>
      )}

      {/* Buy new position if not held */}
      {!position && (
        <BuyNewModal
          ticker={ticker}
          name={(a.name as string) ?? ticker}
          currentPrice={price}
          priceDisplay={priceDisplay}
          recShares={a.rec_shares as number | undefined}
          currency={currency}
          onDone={onTradeDone}
        />
      )}
    </>
  );
}

/* ══════════════════════════════════════════════════════
   TAB 2: CHART
   ══════════════════════════════════════════════════════ */
function ChartTab({ ticker, isKorean }: { ticker: string; isKorean: boolean }) {
  const [period, setPeriod] = useState("6mo");
  const { data, error } = useSWR(`${API.market.chart(ticker)}?period=${period}`, fetcher, {
    revalidateOnFocus: false, dedupingInterval: 60_000,
  });

  const chartData = data?.data as Array<{ date: string; close: number; volume: number }> | undefined;

  const { minPrice, maxPrice } = useMemo(() => {
    if (!chartData?.length) return { minPrice: 0, maxPrice: 0 };
    const closes = chartData.map(d => d.close);
    return { minPrice: Math.min(...closes), maxPrice: Math.max(...closes) };
  }, [chartData]);

  const periods = ["1d", "5d", "1mo", "3mo", "6mo", "1y", "2y"];

  return (
    <Card className="glass-card p-5">
      <div className="flex items-center justify-between mb-4">
        <SectionLabel>Price Chart</SectionLabel>
        <div className="flex gap-1">
          {periods.map((p) => (
            <button
              key={p}
              onClick={() => setPeriod(p)}
              className={`rounded px-2 py-1 text-[10px] font-semibold transition ${
                period === p ? "bg-primary/15 text-primary" : "text-muted-foreground/50 hover:text-muted-foreground"
              }`}
            >
              {p.toUpperCase()}
            </button>
          ))}
        </div>
      </div>

      {error ? (
        <div className="flex items-center justify-center py-12 text-xs text-destructive/60">Failed to load chart data</div>
      ) : !chartData ? (
        <div className="flex items-center justify-center py-12"><Spinner size="md" /></div>
      ) : chartData.length === 0 ? (
        <div className="flex items-center justify-center py-12 text-xs text-muted-foreground/40">No chart data available</div>
      ) : (
        <>
          {/* SVG Chart */}
          <div className="relative w-full" style={{ height: 240 }}>
            <svg viewBox={`0 0 ${chartData.length} 200`} preserveAspectRatio="none" className="h-full w-full">
              <defs>
                <linearGradient id="chartGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="rgb(16,185,129)" stopOpacity="0.3" />
                  <stop offset="100%" stopColor="rgb(16,185,129)" stopOpacity="0" />
                </linearGradient>
              </defs>
              {/* Area fill */}
              <path
                d={`${chartData.map((d, i) => {
                  const x = i;
                  const y = 200 - ((d.close - minPrice) / (maxPrice - minPrice || 1)) * 180 - 10;
                  return `${i === 0 ? "M" : "L"}${x},${y}`;
                }).join(" ")} L${chartData.length - 1},200 L0,200 Z`}
                fill="url(#chartGrad)"
              />
              {/* Line */}
              <path
                d={chartData.map((d, i) => {
                  const x = i;
                  const y = 200 - ((d.close - minPrice) / (maxPrice - minPrice || 1)) * 180 - 10;
                  return `${i === 0 ? "M" : "L"}${x},${y}`;
                }).join(" ")}
                fill="none"
                stroke="rgb(16,185,129)"
                strokeWidth="1.5"
                vectorEffect="non-scaling-stroke"
              />
            </svg>
          </div>

          {/* Price range */}
          <div className="mt-3 flex justify-between text-[10px] text-muted-foreground/40">
            <span>{chartData[0]?.date}</span>
            <span>Low: {isKorean ? `₩${minPrice.toLocaleString()}` : `$${minPrice.toFixed(2)}`} | High: {isKorean ? `₩${maxPrice.toLocaleString()}` : `$${maxPrice.toFixed(2)}`}</span>
            <span>{chartData[chartData.length - 1]?.date}</span>
          </div>
        </>
      )}
    </Card>
  );
}

/* ══════════════════════════════════════════════════════
   TAB 3: FUNDAMENTALS
   ══════════════════════════════════════════════════════ */
function FundamentalsTab({ analysis, ticker }: { analysis: Record<string, unknown>; ticker: string }) {
  const snap = analysis.snapshot as Record<string, number | string | null> | undefined;
  const { data: profile } = useSWR(API.market.profile(ticker), fetcher, {
    revalidateOnFocus: false, dedupingInterval: 300_000,
  });
  const { data: dividend } = useSWR(API.market.dividend(ticker), fetcher, {
    revalidateOnFocus: false, dedupingInterval: 300_000,
  });
  const { data: peers } = useSWR(API.market.peers(ticker), fetcher, {
    revalidateOnFocus: false, dedupingInterval: 300_000,
  });

  const fundamentalRows = useMemo(() => {
    if (!snap) return [];
    return [
      { label: "P/E Ratio", value: (snap.pe_ratio as number)?.toFixed(1) },
      { label: "Forward P/E", value: (snap.forward_pe as number)?.toFixed(1) },
      { label: "EPS", value: (snap.eps as number)?.toFixed(2) },
      { label: "Revenue Growth", value: snap.revenue_growth ? `${((snap.revenue_growth as number) * 100).toFixed(1)}%` : null },
      { label: "Profit Margin", value: snap.profit_margin ? `${((snap.profit_margin as number) * 100).toFixed(1)}%` : null },
      { label: "Debt/Equity", value: (snap.debt_equity as number)?.toFixed(0) },
      { label: "Beta", value: (snap.beta as number)?.toFixed(2) },
      { label: "Market Cap", value: snap.market_cap ? `$${((snap.market_cap as number) / 1e9).toFixed(1)}B` : null },
      { label: "ROE", value: snap.roe ? `${((snap.roe as number) * 100).toFixed(1)}%` : null },
      { label: "ROA", value: snap.roa ? `${((snap.roa as number) * 100).toFixed(1)}%` : null },
      { label: "Current Ratio", value: (snap.current_ratio as number)?.toFixed(2) },
      { label: "Book Value", value: (snap.book_value as number)?.toFixed(2) },
    ].filter(f => f.value != null);
  }, [snap]);

  return (
    <>
      {/* Fundamental grid */}
      <Card className="glass-card p-5">
        <SectionLabel>Valuation & Financials</SectionLabel>
        {fundamentalRows.length > 0 ? (
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            {fundamentalRows.map((f) => (
              <StatBox key={f.label} label={f.label} value={f.value!} />
            ))}
          </div>
        ) : (
          <p className="text-xs text-muted-foreground/40 py-8 text-center">No fundamental data available</p>
        )}
      </Card>

      {/* Company Profile */}
      {profile && !profile.error && (
        <Card className="glass-card p-5">
          <SectionLabel>Company Profile</SectionLabel>
          <div className="grid grid-cols-2 gap-2 text-xs sm:grid-cols-3">
            {profile.industry && <StatBox label="Industry" value={profile.industry} />}
            {profile.country && <StatBox label="Country" value={profile.country} />}
            {profile.employees && <StatBox label="Employees" value={Number(profile.employees).toLocaleString()} />}
          </div>
          {profile.summary && (
            <p className="mt-3 text-xs leading-relaxed text-muted-foreground/70 line-clamp-4">{profile.summary}</p>
          )}
          {profile.website && (
            <a href={profile.website} target="_blank" rel="noopener noreferrer" className="mt-2 inline-block text-xs text-primary hover:underline">
              {profile.website}
            </a>
          )}
        </Card>
      )}

      {/* Dividend */}
      {dividend?.has_dividend && (
        <Card className="glass-card p-5">
          <SectionLabel>Dividend Info</SectionLabel>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
            {dividend.dividend_yield != null && <StatBox label="Yield" value={`${dividend.dividend_yield}%`} color="text-success" />}
            {dividend.dividend_rate != null && <StatBox label="Annual Rate" value={`$${dividend.dividend_rate}`} />}
            {dividend.ex_dividend_date && <StatBox label="Ex-Div Date" value={dividend.ex_dividend_date} />}
          </div>
        </Card>
      )}

      {/* Peer Comparison */}
      {peers?.peers?.length > 0 && (
        <Card className="glass-card p-5">
          <SectionLabel>Peer Comparison ({peers.sector})</SectionLabel>
          {peers.rank > 0 && (
            <p className="mb-3 text-xs text-muted-foreground/60">
              Rank #{peers.rank} of {peers.total} in sector by quant score
            </p>
          )}
          <div className="space-y-1 max-h-64 overflow-y-auto scrollbar-thin">
            {peers.peers.map((peer: Record<string, unknown>) => (
              <div
                key={peer.ticker as string}
                className={`flex items-center justify-between rounded-md px-3 py-2 text-xs ${
                  peer.is_target ? "bg-primary/10 border border-primary/20" : "hover:bg-muted/20"
                }`}
              >
                <div className="flex items-center gap-2">
                  <span className="font-mono font-semibold text-foreground">{peer.ticker as string}</span>
                  <span className="text-muted-foreground/50 truncate max-w-[120px]">{peer.name as string}</span>
                </div>
                <div className="flex items-center gap-3">
                  <span className="text-muted-foreground/60">{peer.price_display as string}</span>
                  <span className={`font-mono font-bold ${scoreColor(peer.score as number)}`}>{(peer.score as number)?.toFixed(0)}</span>
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}
    </>
  );
}

/* ══════════════════════════════════════════════════════
   TAB 4: AI ANALYSIS
   ══════════════════════════════════════════════════════ */
function AIAnalysisTab({ analysis }: { analysis: Record<string, unknown> }) {
  const { data: aiStatus } = useAiStatus();
  const [swot, setSwot] = useState<AiSwotResponse | null>(null);
  const [competitor, setCompetitor] = useState<AiCompetitorResponse | null>(null);
  const [sectorTrend, setSectorTrend] = useState<AiSectorTrendResponse | null>(null);
  const [commentary, setCommentary] = useState<AiCommentaryResponse | null>(null);
  const [aiLoading, setAiLoading] = useState("");
  const [aiError, setAiError] = useState<string | null>(null);

  const loadWithTimeout = async <T,>(
    key: string,
    endpoint: string,
    body: Record<string, unknown>,
    setter: (v: T) => void,
    current: T | null,
  ) => {
    if (current) { setter(null as unknown as T); return; }
    setAiLoading(key);
    setAiError(null);

    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 90_000);

    try {
      const r = await apiFetch<T>(endpoint, {
        method: "POST",
        body: JSON.stringify(body),
        signal: controller.signal,
      });
      setter(r);
    } catch (err) {
      const msg = (err as Error).name === "AbortError"
        ? "Request timed out. AI may be overloaded."
        : (err as Error).message || "Failed to generate analysis.";
      setAiError(msg);
    } finally {
      clearTimeout(timeout);
      setAiLoading("");
    }
  };

  const loadSwot = () => loadWithTimeout("swot", API.ai.swot, analysis, setSwot, swot);
  const loadCommentary = () => loadWithTimeout("commentary", API.ai.commentary, analysis, setCommentary, commentary);
  const loadCompetitor = () => loadWithTimeout("competitor", API.ai.competitor, analysis, setCompetitor, competitor);
  const loadSectorTrend = () => loadWithTimeout("sector", API.ai.sectorTrend, { sector: analysis.sector }, setSectorTrend, sectorTrend);

  const aiButtons = [
    { key: "commentary", label: "AI Commentary", active: !!commentary, onClick: loadCommentary },
    { key: "swot", label: "SWOT Analysis", active: !!swot, onClick: loadSwot },
    { key: "competitor", label: "Competitor Analysis", active: !!competitor, onClick: loadCompetitor },
    { key: "sector", label: "Sector Trend", active: !!sectorTrend, onClick: loadSectorTrend },
  ];

  // AI not available
  if (aiStatus && !aiStatus.available) {
    return (
      <Card className="glass-card p-5">
        <SectionLabel>AI-Powered Analysis</SectionLabel>
        <div className="flex flex-col items-center justify-center py-8 gap-3">
          <div className="w-10 h-10 rounded-xl bg-amber-50 border border-amber-200 flex items-center justify-center">
            <svg width="16" height="16" viewBox="0 0 20 20" fill="none" className="text-amber-500">
              <path d="M10 2L2 18h16L10 2z" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" />
              <path d="M10 8v4M10 14v1" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
            </svg>
          </div>
          <p className="text-sm font-medium text-slate-700">AI service is not configured</p>
          <p className="text-xs text-muted-foreground/50 text-center max-w-sm">
            An API key is required for AI-powered analysis. Configure it in your server settings.
          </p>
        </div>
      </Card>
    );
  }

  return (
    <>
      <Card className="glass-card p-5">
        <SectionLabel>AI-Powered Analysis</SectionLabel>
        <p className="mb-4 text-xs text-muted-foreground/50">
          Click any button below to generate AI analysis. Powered by Claude.
        </p>
        <div className="flex flex-wrap gap-2">
          {aiButtons.map((btn) => (
            <Button
              key={btn.key}
              variant="outline"
              size="sm"
              onClick={btn.onClick}
              disabled={!!aiLoading}
              className={`text-xs transition-all ${
                btn.active
                  ? "border-primary/40 bg-primary/10 text-primary"
                  : "border-primary/20 hover:bg-primary/10 hover:border-primary/30"
              }`}
            >
              {aiLoading === btn.key ? (
                <span className="flex items-center gap-1.5"><Spinner /> Generating...</span>
              ) : btn.active ? `Hide ${btn.label}` : btn.label}
            </Button>
          ))}
        </div>

        {aiError && (
          <div className="mt-3 rounded-lg bg-red-50 border border-red-200 px-3 py-2">
            <p className="text-[11px] text-red-600">{aiError}</p>
          </div>
        )}
      </Card>

      {commentary && (
        <Card className="glass-card border-primary/10 p-5">
          <SectionLabel>AI Commentary</SectionLabel>
          <p className="whitespace-pre-wrap text-sm leading-relaxed text-foreground/90">{commentary.commentary}</p>
          {commentary.commentary_kr && commentary.commentary_kr !== commentary.commentary && (
            <p className="mt-4 whitespace-pre-wrap border-t border-border/30 pt-4 text-sm leading-relaxed text-muted-foreground">{commentary.commentary_kr}</p>
          )}
          <p className="mt-3 text-[9px] text-muted-foreground/30 italic">AI analysis, not financial advice</p>
        </Card>
      )}

      {swot && (
        <Card className="glass-card border-primary/10 p-5">
          <SectionLabel>SWOT Analysis</SectionLabel>
          <p className="whitespace-pre-wrap text-sm leading-relaxed text-foreground/90">{swot.swot}</p>
          {swot.swot_kr && swot.swot_kr !== swot.swot && (
            <p className="mt-4 whitespace-pre-wrap border-t border-border/30 pt-4 text-sm leading-relaxed text-muted-foreground">{swot.swot_kr}</p>
          )}
          <p className="mt-3 text-[9px] text-muted-foreground/30 italic">AI analysis, not financial advice</p>
        </Card>
      )}

      {competitor && (
        <Card className="glass-card border-primary/10 p-5">
          <SectionLabel>Competitor Analysis</SectionLabel>
          <p className="whitespace-pre-wrap text-sm leading-relaxed text-foreground/90">{competitor.analysis}</p>
          {competitor.analysis_kr && competitor.analysis_kr !== competitor.analysis && (
            <p className="mt-4 whitespace-pre-wrap border-t border-border/30 pt-4 text-sm leading-relaxed text-muted-foreground">{competitor.analysis_kr}</p>
          )}
          <p className="mt-3 text-[9px] text-muted-foreground/30 italic">AI analysis, not financial advice</p>
        </Card>
      )}

      {sectorTrend && (
        <Card className="glass-card border-primary/10 p-5">
          <SectionLabel>Sector Trend ({analysis.sector as string})</SectionLabel>
          <p className="whitespace-pre-wrap text-sm leading-relaxed text-foreground/90">{sectorTrend.trend}</p>
          {sectorTrend.trend_kr && sectorTrend.trend_kr !== sectorTrend.trend && (
            <p className="mt-4 whitespace-pre-wrap border-t border-border/30 pt-4 text-sm leading-relaxed text-muted-foreground">{sectorTrend.trend_kr}</p>
          )}
          <p className="mt-3 text-[9px] text-muted-foreground/30 italic">AI analysis, not financial advice</p>
        </Card>
      )}
    </>
  );
}

/* ══════════════════════════════════════════════════════
   TAB 5: NEWS
   ══════════════════════════════════════════════════════ */
function NewsTab({ ticker }: { ticker: string }) {
  const { data, error } = useSWR(API.market.news(ticker), fetcher, {
    revalidateOnFocus: false, dedupingInterval: 120_000,
  });

  const news = data?.news as Array<{
    title: string;
    link?: string;
    url?: string;
    source?: string;
    publisher?: string;
    published?: string;
    date?: string;
    summary?: string;
    snippet?: string;
  }> | undefined;

  return (
    <Card className="glass-card p-5">
      <SectionLabel>Recent News</SectionLabel>
      {error ? (
        <p className="text-xs text-destructive/60 py-8 text-center">Failed to load news</p>
      ) : !news ? (
        <div className="flex items-center justify-center py-12"><Spinner size="md" /></div>
      ) : news.length === 0 ? (
        <p className="text-xs text-muted-foreground/40 py-8 text-center">No recent news found for {ticker}</p>
      ) : (
        <div className="space-y-3 max-h-[500px] overflow-y-auto scrollbar-thin">
          {news.map((item, i) => {
            const link = item.link || item.url;
            const source = item.source || item.publisher || "";
            const date = item.published || item.date || "";
            const snippet = item.summary || item.snippet || "";
            return (
              <div key={i} className="rounded-lg bg-muted/10 p-3 transition hover:bg-muted/20">
                {link ? (
                  <a href={link} target="_blank" rel="noopener noreferrer" className="text-sm font-semibold text-foreground hover:text-primary transition leading-snug">
                    {item.title}
                  </a>
                ) : (
                  <p className="text-sm font-semibold text-foreground leading-snug">{item.title}</p>
                )}
                {snippet && (
                  <p className="mt-1 text-xs text-muted-foreground/60 line-clamp-2">{snippet}</p>
                )}
                <div className="mt-1.5 flex items-center gap-2 text-[10px] text-muted-foreground/40">
                  {source && <span>{source}</span>}
                  {source && date && <span>·</span>}
                  {date && <span>{date}</span>}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </Card>
  );
}

/* ══════════════════════════════════════════════════════
   TAB 6: TECHNICALS
   ══════════════════════════════════════════════════════ */
function TechnicalsTab({ analysis }: { analysis: Record<string, unknown> }) {
  const snap = analysis.snapshot as Record<string, number | string | null> | undefined;

  const rsi = (snap?.rsi as number) ?? (analysis.rsi as number);
  const macd = (snap?.macd as number) ?? (analysis.macd as number);
  const macd_signal = (snap?.macd_signal as number) ?? (analysis.macd_signal as number);
  const macd_hist = (snap?.macd_hist as number) ?? (analysis.macd_hist as number);
  const bb_upper = (snap?.bb_upper as number) ?? (analysis.bb_upper as number);
  const bb_lower = (snap?.bb_lower as number) ?? (analysis.bb_lower as number);
  const bb_mid = (snap?.bb_middle as number) ?? (snap?.bb_mid as number) ?? (analysis.bb_mid as number);
  const sma_20 = (snap?.sma_20 as number) ?? (analysis.sma_20 as number);
  const sma_50 = (snap?.sma_50 as number) ?? (analysis.sma_50 as number);
  const sma_200 = (snap?.sma_200 as number) ?? (analysis.sma_200 as number);
  const ema_12 = (snap?.ema_12 as number) ?? (analysis.ema_12 as number);
  const ema_26 = (snap?.ema_26 as number) ?? (analysis.ema_26 as number);
  const atr = (snap?.atr as number) ?? (analysis.atr as number);
  const adx = (snap?.adx as number) ?? (analysis.adx as number);
  const vol_ratio = (snap?.vol_ratio as number) ?? (analysis.vol_ratio as number);
  const price = analysis.price as number;

  const rsiColor = rsi != null
    ? rsi > 70 ? "text-destructive" : rsi < 30 ? "text-success" : "text-foreground"
    : "text-muted-foreground/40";

  const rsiLabel = rsi != null
    ? rsi > 70 ? "Overbought" : rsi < 30 ? "Oversold" : "Neutral"
    : "N/A";

  return (
    <>
      {/* RSI */}
      <Card className="glass-card p-5">
        <SectionLabel>RSI (Relative Strength Index)</SectionLabel>
        {rsi != null ? (
          <div>
            <div className="flex items-center justify-between">
              <span className={`text-2xl font-bold font-mono ${rsiColor}`}>{rsi.toFixed(1)}</span>
              <Badge variant="outline" className={`text-xs ${
                rsi > 70 ? "border-destructive/30 text-destructive" : rsi < 30 ? "border-success/30 text-success" : "border-border text-muted-foreground"
              }`}>
                {rsiLabel}
              </Badge>
            </div>
            {/* RSI gauge bar */}
            <div className="mt-3 relative h-2 w-full rounded-full bg-muted/30 overflow-hidden">
              <div className="absolute inset-y-0 left-0 bg-success/30 rounded-l-full" style={{ width: "30%" }} />
              <div className="absolute inset-y-0 left-[30%] bg-muted/20" style={{ width: "40%" }} />
              <div className="absolute inset-y-0 right-0 bg-destructive/30 rounded-r-full" style={{ width: "30%" }} />
              <div
                className="absolute top-1/2 -translate-y-1/2 w-2.5 h-2.5 rounded-full bg-foreground border-2 border-background"
                style={{ left: `${Math.min(Math.max(rsi, 0), 100)}%`, transform: "translate(-50%, -50%)" }}
              />
            </div>
            <div className="mt-1 flex justify-between text-[9px] text-muted-foreground/30">
              <span>0 (Oversold)</span><span>50</span><span>100 (Overbought)</span>
            </div>
          </div>
        ) : (
          <p className="text-xs text-muted-foreground/40 py-4">RSI data not available</p>
        )}
      </Card>

      {/* MACD */}
      <Card className="glass-card p-5">
        <SectionLabel>MACD</SectionLabel>
        <div className="grid grid-cols-3 gap-3">
          <StatBox label="MACD Line" value={macd != null ? macd.toFixed(3) : "N/A"} color={macd != null && macd > 0 ? "text-success" : "text-destructive"} />
          <StatBox label="Signal Line" value={macd_signal != null ? macd_signal.toFixed(3) : "N/A"} />
          <StatBox label="Histogram" value={macd_hist != null ? macd_hist.toFixed(3) : "N/A"} color={macd_hist != null && macd_hist > 0 ? "text-success" : "text-destructive"} />
        </div>
        {macd != null && macd_signal != null && (
          <p className={`mt-3 text-xs px-2.5 py-1.5 rounded-md ${
            macd > macd_signal ? "bg-success/5 text-success" : "bg-destructive/5 text-destructive"
          }`}>
            {macd > macd_signal ? "▲ MACD above signal line (Bullish crossover)" : "▼ MACD below signal line (Bearish crossover)"}
          </p>
        )}
      </Card>

      {/* Bollinger Bands */}
      <Card className="glass-card p-5">
        <SectionLabel>Bollinger Bands</SectionLabel>
        <div className="grid grid-cols-3 gap-3">
          <StatBox label="Upper Band" value={bb_upper != null ? bb_upper.toFixed(2) : "N/A"} color="text-destructive/70" />
          <StatBox label="Middle" value={bb_mid != null ? bb_mid.toFixed(2) : "N/A"} />
          <StatBox label="Lower Band" value={bb_lower != null ? bb_lower.toFixed(2) : "N/A"} color="text-success/70" />
        </div>
        {bb_upper != null && bb_lower != null && price != null && (
          <div className="mt-3">
            <div className="relative h-2 w-full rounded-full bg-muted/30 overflow-hidden">
              <div className="absolute inset-0 bg-gradient-to-r from-success/20 via-muted/10 to-destructive/20 rounded-full" />
              <div
                className="absolute top-1/2 -translate-y-1/2 w-2.5 h-2.5 rounded-full bg-foreground border-2 border-background"
                style={{
                  left: `${Math.min(Math.max(((price - bb_lower) / (bb_upper - bb_lower || 1)) * 100, 0), 100)}%`,
                  transform: "translate(-50%, -50%)",
                }}
              />
            </div>
            <div className="mt-1 flex justify-between text-[9px] text-muted-foreground/30">
              <span>Lower ({bb_lower.toFixed(2)})</span>
              <span>Price ({price.toFixed(2)})</span>
              <span>Upper ({bb_upper.toFixed(2)})</span>
            </div>
          </div>
        )}
      </Card>

      {/* Moving Averages */}
      <Card className="glass-card p-5">
        <SectionLabel>Moving Averages</SectionLabel>
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
          {[
            { label: "SMA 20", value: sma_20, aboveBelow: price && sma_20 ? price > sma_20 : null },
            { label: "SMA 50", value: sma_50, aboveBelow: price && sma_50 ? price > sma_50 : null },
            { label: "SMA 200", value: sma_200, aboveBelow: price && sma_200 ? price > sma_200 : null },
            { label: "EMA 12", value: ema_12, aboveBelow: price && ema_12 ? price > ema_12 : null },
            { label: "EMA 26", value: ema_26, aboveBelow: price && ema_26 ? price > ema_26 : null },
          ].filter(m => m.value != null).map((m) => (
            <div key={m.label} className="rounded-lg bg-muted/20 p-2.5 text-center">
              <p className="text-[9px] uppercase tracking-wider text-muted-foreground/40">{m.label}</p>
              <p className="mt-0.5 font-mono text-sm font-bold text-foreground">{m.value!.toFixed(2)}</p>
              {m.aboveBelow != null && (
                <p className={`text-[9px] mt-0.5 ${m.aboveBelow ? "text-success" : "text-destructive"}`}>
                  Price {m.aboveBelow ? "above" : "below"}
                </p>
              )}
            </div>
          ))}
        </div>
      </Card>

      {/* Other Technical Indicators */}
      {(atr != null || adx != null || vol_ratio != null) && (
        <Card className="glass-card p-5">
          <SectionLabel>Other Indicators</SectionLabel>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
            {atr != null && <StatBox label="ATR" value={atr.toFixed(3)} />}
            {adx != null && (
              <StatBox
                label="ADX"
                value={adx.toFixed(1)}
                color={adx > 25 ? "text-success" : "text-muted-foreground"}
              />
            )}
            {vol_ratio != null && (
              <StatBox
                label="Vol Ratio"
                value={`${vol_ratio.toFixed(2)}x`}
                color={vol_ratio > 1.5 ? "text-warning" : "text-foreground"}
              />
            )}
          </div>
        </Card>
      )}

      {/* Signals summary */}
      {(analysis.signals as unknown[])?.length > 0 && (
        <Card className="glass-card p-5">
          <SectionLabel>Technical Signals</SectionLabel>
          <div className="space-y-1">
            {(analysis.signals as Array<{type: string; msg: string}>)
              ?.filter(s => s.type === "bullish" || s.type === "bearish")
              .map((s, i) => (
                <p key={i} className={`rounded-md px-2.5 py-1.5 text-xs ${
                  s.type === "bullish" ? "bg-success/5 text-success" : "bg-destructive/5 text-destructive"
                }`}>
                  {s.type === "bullish" ? "▲" : "▼"} {s.msg}
                </p>
              ))}
          </div>
        </Card>
      )}
    </>
  );
}

/* ══════════════════════════════════════════════════════
   TAB 7: BACKTEST
   ══════════════════════════════════════════════════════ */
function BacktestTab({ ticker }: { ticker: string }) {
  const [period, setPeriod] = useState("1y");
  const [capital, setCapital] = useState("10000");
  const [result, setResult] = useState<Record<string, unknown> | null>(null);
  const [btLoading, setBtLoading] = useState(false);
  const [btError, setBtError] = useState("");

  const runBacktest = async () => {
    setBtLoading(true);
    setBtError("");
    setResult(null);
    try {
      const r = await apiFetch<Record<string, unknown>>(
        `${API.backtest(ticker)}?period=${period}&capital=${capital}`
      );
      if (r.error) {
        setBtError(r.error as string);
      } else {
        setResult(r);
      }
    } catch (e: unknown) {
      setBtError((e as Error).message);
    } finally {
      setBtLoading(false);
    }
  };

  return (
    <>
      <Card className="glass-card p-5">
        <SectionLabel>Quick Backtest</SectionLabel>
        <p className="mb-4 text-xs text-muted-foreground/50">
          Simulate this stock&apos;s performance using StockPilot&apos;s quant signals.
        </p>
        <div className="flex flex-wrap items-end gap-3">
          <div>
            <label className="text-[10px] uppercase tracking-wider text-muted-foreground/40 block mb-1">Period</label>
            <div className="flex gap-1">
              {["3mo", "6mo", "1y", "2y"].map((p) => (
                <button
                  key={p}
                  onClick={() => setPeriod(p)}
                  className={`rounded px-2.5 py-1.5 text-[10px] font-semibold transition ${
                    period === p ? "bg-primary/15 text-primary" : "text-muted-foreground/50 hover:text-muted-foreground bg-muted/20"
                  }`}
                >
                  {p.toUpperCase()}
                </button>
              ))}
            </div>
          </div>
          <div>
            <label className="text-[10px] uppercase tracking-wider text-muted-foreground/40 block mb-1">Capital ($)</label>
            <Input
              type="number"
              value={capital}
              onChange={(e) => setCapital(e.target.value)}
              className="h-8 w-28 border-border/40 bg-muted/20 text-sm"
              min={1000}
              step={1000}
            />
          </div>
          <Button
            onClick={runBacktest}
            disabled={btLoading}
            size="sm"
            className="bg-primary text-primary-foreground hover:bg-primary/80 font-semibold text-xs"
          >
            {btLoading ? <span className="flex items-center gap-1.5"><Spinner /> Running...</span> : "Run Backtest"}
          </Button>
        </div>
      </Card>

      {btError && (
        <Card className="glass-card border-destructive/20 p-5">
          <p className="text-xs text-destructive">{btError}</p>
        </Card>
      )}

      {result && (
        <Card className="glass-card p-5">
          <SectionLabel>Backtest Results ({period.toUpperCase()}, ${Number(capital).toLocaleString()} initial)</SectionLabel>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            {result.total_return != null && (
              <StatBox
                label="Total Return"
                value={`${((result.total_return as number) * 100).toFixed(1)}%`}
                color={pnlColor((result.total_return as number) * 100)}
              />
            )}
            {result.final_value != null && (
              <StatBox label="Final Value" value={fmtUsd(result.final_value as number)} />
            )}
            {result.trades_count != null && (
              <StatBox label="Trades" value={result.trades_count as number} />
            )}
            {result.win_rate != null && (
              <StatBox
                label="Win Rate"
                value={`${((result.win_rate as number) * 100).toFixed(0)}%`}
                color={(result.win_rate as number) >= 0.5 ? "text-success" : "text-destructive"}
              />
            )}
            {result.max_drawdown != null && (
              <StatBox
                label="Max Drawdown"
                value={`${((result.max_drawdown as number) * 100).toFixed(1)}%`}
                color="text-destructive"
              />
            )}
            {result.sharpe_ratio != null && (
              <StatBox
                label="Sharpe Ratio"
                value={(result.sharpe_ratio as number).toFixed(2)}
                color={(result.sharpe_ratio as number) > 1 ? "text-success" : "text-foreground"}
              />
            )}
            {result.buy_hold_return != null && (
              <StatBox
                label="Buy & Hold"
                value={`${((result.buy_hold_return as number) * 100).toFixed(1)}%`}
                color={pnlColor((result.buy_hold_return as number) * 100)}
              />
            )}
            {result.alpha != null && (
              <StatBox
                label="Alpha"
                value={`${((result.alpha as number) * 100).toFixed(1)}%`}
                color={pnlColor((result.alpha as number) * 100)}
              />
            )}
          </div>

          {/* Trades list */}
          {(result.trades as Array<Record<string, unknown>>)?.length > 0 && (
            <div className="mt-4">
              <p className="text-[10px] uppercase tracking-wider text-muted-foreground/40 mb-2">
                Trade History ({(result.trades as unknown[]).length} trades)
              </p>
              <div className="max-h-48 overflow-y-auto scrollbar-thin space-y-1">
                {(result.trades as Array<Record<string, unknown>>).map((t, i) => (
                  <div key={i} className="flex items-center justify-between rounded-md bg-muted/10 px-2.5 py-1.5 text-[11px]">
                    <div className="flex items-center gap-2">
                      <span className={`font-semibold ${
                        t.action === "BUY" ? "text-success" : "text-destructive"
                      }`}>
                        {t.action as string}
                      </span>
                      <span className="text-muted-foreground/50">{t.date as string}</span>
                    </div>
                    <div className="flex items-center gap-3">
                      <span className="text-muted-foreground/60">@ ${(t.price as number)?.toFixed(2)}</span>
                      {t.pnl_pct != null && (
                        <span className={`font-mono font-bold ${pnlColor(t.pnl_pct as number)}`}>
                          {(t.pnl_pct as number) >= 0 ? "+" : ""}{(t.pnl_pct as number)?.toFixed(1)}%
                        </span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </Card>
      )}
    </>
  );
}
