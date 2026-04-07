"use client";

import { useState } from "react";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";

const terms = [
  { term: "Alpha", def: "Excess return of an investment relative to its benchmark index." },
  { term: "ATR", def: "Average True Range — measures market volatility by decomposing the entire range of an asset price." },
  { term: "Beta", def: "Measure of a stock's volatility relative to the overall market." },
  { term: "Bollinger Bands", def: "Volatility bands placed above and below a moving average, using standard deviation." },
  { term: "Drawdown", def: "Peak-to-trough decline during a specific period, measuring downside risk." },
  { term: "EMA", def: "Exponential Moving Average — weighted moving average giving more importance to recent prices." },
  { term: "Fear & Greed Index", def: "Composite indicator measuring market sentiment from 0 (extreme fear) to 100 (extreme greed)." },
  { term: "MACD", def: "Moving Average Convergence Divergence — trend-following momentum indicator showing relationship between two EMAs." },
  { term: "P/E Ratio", def: "Price-to-Earnings ratio — stock price divided by earnings per share." },
  { term: "Quant Score", def: "StockPilot proprietary 0-100 composite score combining technical, fundamental, and momentum signals." },
  { term: "RSI", def: "Relative Strength Index — momentum oscillator (0-100). Below 30 = oversold, above 70 = overbought." },
  { term: "Sharpe Ratio", def: "Risk-adjusted return metric. (Portfolio return - risk-free rate) / portfolio standard deviation." },
  { term: "SMA", def: "Simple Moving Average — arithmetic mean of prices over a specified period." },
  { term: "Stop Loss", def: "Predetermined price at which a position is automatically sold to limit losses." },
  { term: "Take Profit", def: "Predetermined price at which a position is automatically sold to lock in gains." },
  { term: "VIX", def: "CBOE Volatility Index — market's expectation of 30-day forward-looking volatility. Above 25 = high fear." },
  { term: "Volume Ratio", def: "Current volume compared to average volume. Above 2x suggests unusual activity." },
  { term: "VWAP", def: "Volume Weighted Average Price — average price weighted by volume, used as intraday benchmark." },
  { term: "Yield Curve", def: "Graph of bond yields across maturities. Inversion (short > long) historically signals recession." },
];

export default function GlossaryPage() {
  const [search, setSearch] = useState("");

  const filtered = terms.filter(
    (t) =>
      t.term.toLowerCase().includes(search.toLowerCase()) ||
      t.def.toLowerCase().includes(search.toLowerCase()),
  );

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <h1 className="text-lg font-semibold text-foreground">GS Glossary</h1>

      <Input
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        placeholder="Search terms..."
        className="max-w-sm bg-muted"
      />

      <div className="space-y-2">
        {filtered.map((t) => (
          <Card key={t.term} className="border-border bg-card px-4 py-3">
            <p className="text-sm font-semibold text-primary">{t.term}</p>
            <p className="mt-1 text-xs text-muted-foreground">{t.def}</p>
          </Card>
        ))}
        {filtered.length === 0 && (
          <p className="py-6 text-center text-sm text-muted-foreground">No matching terms</p>
        )}
      </div>
    </div>
  );
}
