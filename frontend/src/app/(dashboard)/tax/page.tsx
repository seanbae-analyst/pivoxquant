"use client";

import { useState, useMemo } from "react";
import { usePortfolio } from "@/lib/hooks";
import { fmtUsd, fmtKrw } from "@/lib/format";
import { Receipt, Calculator, DollarSign, Info } from "lucide-react";
import type { Position } from "@/lib/types";

/* ── Tax rules by residency ── */

// Korean resident investing in US stocks
const KR_RESIDENT = {
  label: "Korean Resident",
  overseas_rate: 0.22, // 소득세 20% + 지방세 2%
  basic_deduction_krw: 2_500_000, // ₩250만 기본공제
  domestic_taxable: false, // 국내주식 비과세 (일반 투자자)
  description: "Overseas stock gains taxed at 22% (income 20% + local 2%) above ₩2.5M annual deduction. Korean domestic stocks are tax-exempt for non-major shareholders.",
};

// US resident investing
const US_RESIDENT = {
  label: "US Resident",
  long_term_rate: 0.15,
  short_term_rate: 0.22,
  foreign_rate: 0.15, // US tax on Korean stock gains
  description: "Long-term capital gains (held >1yr) taxed at 15%. Short-term at 22%. Foreign stock gains taxed at same rates.",
};

type Residency = "KR" | "US";

interface TaxRow {
  ticker: string;
  name: string;
  shares: number;
  costBasis: number;
  currentValue: number;
  gainLoss: number;
  estimatedTax: number;
  isKorean: boolean;
  taxable: boolean;
  taxNote: string;
}

function computeRows(positions: Position[], residency: Residency, fxRate: number): TaxRow[] {
  return positions.map((p) => {
    const gainLoss = (p.current_price - p.avg_cost) * p.shares;
    let estimatedTax = 0;
    let taxable = true;
    let taxNote = "";

    if (gainLoss <= 0) {
      taxable = false;
      taxNote = "No gain";
    } else if (residency === "KR") {
      if (p.is_korean) {
        // Korean resident + Korean stock = tax-exempt (non-major shareholder)
        taxable = false;
        estimatedTax = 0;
        taxNote = "Tax-exempt (domestic)";
      } else {
        // Korean resident + US stock = 22% on KRW gains above deduction
        estimatedTax = gainLoss * fxRate * KR_RESIDENT.overseas_rate;
        taxNote = `22% on ₩ gain`;
      }
    } else {
      // US resident
      if (p.is_korean) {
        estimatedTax = gainLoss * US_RESIDENT.foreign_rate;
        taxNote = `${US_RESIDENT.foreign_rate * 100}% foreign gains`;
      } else {
        estimatedTax = gainLoss * US_RESIDENT.long_term_rate;
        taxNote = `${US_RESIDENT.long_term_rate * 100}% long-term`;
      }
    }

    return {
      ticker: p.ticker,
      name: p.name,
      shares: p.shares,
      costBasis: p.avg_cost * p.shares,
      currentValue: p.current_price * p.shares,
      gainLoss,
      estimatedTax,
      isKorean: p.is_korean,
      taxable,
      taxNote,
    };
  });
}

function SummaryCard({ icon, label, value, sub }: { icon: React.ReactNode; label: string; value: string; sub?: string }) {
  return (
    <div className="glass-surface rounded-xl p-5 spring-transition transition-all duration-300 hover:shadow-[0_4px_20px_rgba(0,0,0,0.3)]">
      <div className="flex items-center gap-2 text-zinc-600 mb-2">
        {icon}
        <span className="text-[10px] font-semibold uppercase tracking-[0.1em]">{label}</span>
      </div>
      <p className="text-xl font-bold font-mono text-white">{value}</p>
      {sub && <p className="text-[13px] text-zinc-500 mt-1">{sub}</p>}
    </div>
  );
}

export default function TaxPage() {
  const { data, isLoading } = usePortfolio();
  const [residency, setResidency] = useState<Residency>("KR");

  const fxRate = data?.fx_rate ?? 1350;
  const positions = data?.positions ?? [];

  const rows = useMemo(() => computeRows(positions, residency, fxRate), [positions, residency, fxRate]);

  const totalGains = useMemo(() => rows.reduce((s, r) => s + Math.max(r.gainLoss, 0), 0), [rows]);
  const totalLosses = useMemo(() => rows.reduce((s, r) => s + Math.min(r.gainLoss, 0), 0), [rows]);

  const totalEstimatedTax = useMemo(() => {
    if (residency === "US") {
      return rows.reduce((s, r) => s + r.estimatedTax, 0);
    }
    // KR resident: only overseas gains are taxed, apply deduction to total
    const totalOverseasGainKrw = rows
      .filter(r => !r.isKorean && r.gainLoss > 0)
      .reduce((s, r) => s + r.gainLoss * fxRate, 0);
    const taxableKrw = Math.max(totalOverseasGainKrw - KR_RESIDENT.basic_deduction_krw, 0);
    return taxableKrw * KR_RESIDENT.overseas_rate;
  }, [rows, residency, fxRate]);

  const netAfterTax = useMemo(() => {
    const netGain = rows.reduce((s, r) => s + r.gainLoss, 0);
    if (residency === "US") return netGain - totalEstimatedTax;
    return netGain - totalEstimatedTax / fxRate;
  }, [rows, totalEstimatedTax, residency, fxRate]);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <span className="w-1.5 h-1.5 rounded-full bg-cyan-500 animate-pulse mr-2" />
        <span className="text-zinc-600 text-[12px]">Loading...</span>
      </div>
    );
  }

  const activeRule = residency === "KR" ? KR_RESIDENT : US_RESIDENT;

  return (
    <div className="space-y-4 pb-24">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2">
            <Calculator className="h-6 w-6" />
            Tax Calculator
          </h1>
          <p className="text-[13px] text-zinc-600 mt-1">
            Estimate capital gains tax based on your tax residency
          </p>
        </div>

        {/* Residency toggle */}
        <div className="flex rounded-xl border border-white/[0.06] overflow-hidden text-sm">
          {(["KR", "US"] as const).map((r) => (
            <button key={r} onClick={() => setResidency(r)}
              className={`px-4 py-2 font-medium spring-transition transition-all duration-300 ${
                residency === r ? "bg-white/[0.06] text-white" : "text-zinc-600 hover:text-zinc-300"
              }`}
            >
              {r === "KR" ? "🇰🇷 Korean Resident" : "🇺🇸 US Resident"}
            </button>
          ))}
        </div>
      </div>

      {/* Tax rule explanation */}
      <div className="glass-surface rounded-xl p-4 flex items-start gap-3">
        <Info className="h-5 w-5 text-cyan-400 shrink-0 mt-0.5" />
        <div>
          <p className="text-sm font-semibold text-white">{activeRule.label} Tax Rules</p>
          <p className="text-[13px] text-zinc-400 mt-1">{activeRule.description}</p>
        </div>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <SummaryCard
          icon={<DollarSign className="h-4 w-4" />}
          label="Total Unrealized Gains"
          value={residency === "KR" ? fmtKrw(totalGains * fxRate) : fmtUsd(totalGains)}
          sub={totalLosses < 0 ? `Losses: ${residency === "KR" ? fmtKrw(totalLosses * fxRate) : fmtUsd(totalLosses)}` : undefined}
        />
        <SummaryCard
          icon={<Receipt className="h-4 w-4" />}
          label="Total Estimated Tax"
          value={residency === "KR" ? fmtKrw(totalEstimatedTax) : fmtUsd(totalEstimatedTax)}
          sub={residency === "KR"
            ? `22% on overseas gains above ${fmtKrw(KR_RESIDENT.basic_deduction_krw)}`
            : `${US_RESIDENT.long_term_rate * 100}% long-term rate`
          }
        />
        <SummaryCard
          icon={<Calculator className="h-4 w-4" />}
          label="Net After Tax"
          value={residency === "KR" ? fmtKrw(netAfterTax * fxRate) : fmtUsd(netAfterTax)}
        />
      </div>

      {/* Per-position table */}
      <div className="glass-surface rounded-xl overflow-hidden">
        <div className="px-5 py-4 border-b border-white/[0.06]">
          <h2 className="text-white font-semibold">Per-Position Breakdown</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left border-b border-white/[0.06]">
                <th className="px-5 py-3 text-[10px] font-semibold text-zinc-600 uppercase tracking-[0.1em]">Stock</th>
                <th className="px-5 py-3 text-right text-[10px] font-semibold text-zinc-600 uppercase tracking-[0.1em]">Shares</th>
                <th className="px-5 py-3 text-right text-[10px] font-semibold text-zinc-600 uppercase tracking-[0.1em]">Cost Basis</th>
                <th className="px-5 py-3 text-right text-[10px] font-semibold text-zinc-600 uppercase tracking-[0.1em]">Current</th>
                <th className="px-5 py-3 text-right text-[10px] font-semibold text-zinc-600 uppercase tracking-[0.1em]">Gain/Loss</th>
                <th className="px-5 py-3 text-right text-[10px] font-semibold text-zinc-600 uppercase tracking-[0.1em]">Tax</th>
                <th className="px-5 py-3 text-right text-[10px] font-semibold text-zinc-600 uppercase tracking-[0.1em]">Note</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.ticker} className="border-b border-white/[0.06] last:border-b-0 spring-transition transition-all duration-300 hover:bg-white/[0.02]">
                  <td className="px-5 py-3">
                    <p className="text-sm font-semibold text-white">{r.name || r.ticker}</p>
                    <p className="text-[11px] text-zinc-600">{r.ticker}{r.isKorean ? " · KRX" : ""}</p>
                  </td>
                  <td className="px-5 py-3 text-right font-mono text-zinc-300">{r.shares}</td>
                  <td className="px-5 py-3 text-right font-mono text-zinc-300">{fmtUsd(r.costBasis)}</td>
                  <td className="px-5 py-3 text-right font-mono text-zinc-300">{fmtUsd(r.currentValue)}</td>
                  <td className={`px-5 py-3 text-right font-mono font-medium ${r.gainLoss >= 0 ? "text-emerald-400" : "text-red-400"}`}>
                    {r.gainLoss >= 0 ? "+" : ""}{fmtUsd(r.gainLoss)}
                  </td>
                  <td className="px-5 py-3 text-right font-mono text-zinc-300">
                    {r.taxable && r.estimatedTax > 0
                      ? (residency === "KR" ? fmtKrw(r.estimatedTax) : fmtUsd(r.estimatedTax))
                      : "--"
                    }
                  </td>
                  <td className="px-5 py-3 text-right text-[11px] text-zinc-500">{r.taxNote}</td>
                </tr>
              ))}
              {rows.length === 0 && (
                <tr><td colSpan={7} className="px-5 py-8 text-center text-zinc-600">No positions found</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* What if I sell now? */}
      <div className="glass-surface rounded-xl p-5">
        <h2 className="text-white font-semibold mb-3 flex items-center gap-2">
          <Receipt className="h-5 w-5" />
          What if I sell now?
        </h2>
        <p className="text-zinc-400 text-sm mb-4">
          Estimated tax if you liquidate all positions today.
        </p>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div className="rounded-xl bg-white/[0.03] p-4">
            <p className="text-[10px] font-semibold text-zinc-600 uppercase tracking-[0.1em] mb-1">Total Tax Bill</p>
            <p className="text-lg font-bold font-mono text-white">
              {residency === "KR" ? fmtKrw(totalEstimatedTax) : fmtUsd(totalEstimatedTax)}
            </p>
          </div>
          <div className="rounded-xl bg-white/[0.03] p-4">
            <p className="text-[10px] font-semibold text-zinc-600 uppercase tracking-[0.1em] mb-1">You Keep (After Tax)</p>
            <p className={`text-lg font-bold font-mono ${netAfterTax >= 0 ? "text-emerald-400" : "text-red-400"}`}>
              {residency === "KR" ? fmtKrw(netAfterTax * fxRate) : fmtUsd(netAfterTax)}
            </p>
          </div>
        </div>
      </div>

      {/* Disclaimer */}
      <p className="text-center text-[11px] text-zinc-700">
        This is an estimate only. Consult a tax professional for accurate advice. Tax-loss harvesting and wash sale rules may apply.
      </p>
    </div>
  );
}
