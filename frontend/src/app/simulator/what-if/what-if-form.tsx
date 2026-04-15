"use client";

/**
 * What-If Simulator — Input Form
 *
 * 4-step form:
 *   1. Ticker search (debounced /api/lookup/{ticker})
 *   2. Start date (HTML date input, min=1990-01-01, max=today)
 *   3. Amount (number input, currency toggle USD/KRW)
 *   4. Recurring strategy (radio: lump | monthly | weekly)
 *
 * All state is lifted — this component just reports changes to the parent,
 * which owns URL sync and SWR fetch.
 */

import { useEffect, useRef, useState } from "react";
import { Search, Calendar, Coins, Repeat, Sparkles } from "lucide-react";
import { useT } from "@/lib/locale";
import { API } from "@/lib/endpoints";
import type { LookupResult, RecurringMode } from "@/lib/types";
import { cn } from "@/lib/utils";

export interface WhatIfFormState {
  ticker: string;
  tickerName?: string;
  startDate: string; // YYYY-MM-DD
  amount: number;
  currency: "USD" | "KRW";
  recurring: RecurringMode;
}

interface WhatIfFormProps {
  value: WhatIfFormState;
  onChange: (next: WhatIfFormState) => void;
  onSubmit: () => void;
  isLoading: boolean;
}

const TODAY = new Date().toISOString().slice(0, 10);
const MIN_DATE = "1990-01-01";

/** Popular preset tickers for one-tap exploration. */
const PRESETS: Array<{
  ticker: string;
  date: string;
  amount: number;
  currency: "USD" | "KRW";
  labelKo: string;
  labelEn: string;
}> = [
  {
    ticker: "NVDA",
    date: "2020-03-23",
    amount: 5_000_000,
    currency: "KRW",
    labelKo: "NVDA · 코로나 바닥",
    labelEn: "NVDA · COVID bottom",
  },
  {
    ticker: "AAPL",
    date: "2009-01-02",
    amount: 1_000_000,
    currency: "KRW",
    labelKo: "AAPL · 금융위기 후",
    labelEn: "AAPL · post-GFC",
  },
  {
    ticker: "TSLA",
    date: "2019-06-03",
    amount: 3_000_000,
    currency: "KRW",
    labelKo: "TSLA · 상승 직전",
    labelEn: "TSLA · pre-rally",
  },
  {
    ticker: "SPY",
    date: "2015-01-02",
    amount: 500_000,
    currency: "KRW",
    labelKo: "SPY · 10년 DCA",
    labelEn: "SPY · 10-yr DCA",
  },
];

export function WhatIfForm({
  value,
  onChange,
  onSubmit,
  isLoading,
}: WhatIfFormProps) {
  const t = useT();
  const [tickerInput, setTickerInput] = useState(value.ticker);
  const [suggestions, setSuggestions] = useState<LookupResult[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [searching, setSearching] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const debounceRef = useRef<number | null>(null);
  const wrapperRef = useRef<HTMLDivElement | null>(null);

  /* Keep local ticker input in sync when parent prop changes (e.g. from URL). */
  useEffect(() => {
    setTickerInput(value.ticker);
  }, [value.ticker]);

  /* Click-outside closes suggestions */
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (
        wrapperRef.current &&
        !wrapperRef.current.contains(e.target as Node)
      ) {
        setShowSuggestions(false);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  /* Debounced ticker lookup */
  useEffect(() => {
    const q = tickerInput.trim().toUpperCase();
    if (!q || q === value.ticker) {
      setSuggestions([]);
      setSearching(false);
      return;
    }
    if (debounceRef.current) window.clearTimeout(debounceRef.current);
    debounceRef.current = window.setTimeout(async () => {
      if (abortRef.current) abortRef.current.abort();
      const ctrl = new AbortController();
      abortRef.current = ctrl;
      setSearching(true);
      try {
        const res = await fetch(API.market.lookup(q), {
          credentials: "include",
          signal: ctrl.signal,
        });
        if (!res.ok) {
          setSuggestions([]);
          return;
        }
        const data: LookupResult = await res.json();
        if (data && (data.ok === undefined || data.ok)) {
          setSuggestions([data]);
        } else {
          setSuggestions([]);
        }
      } catch {
        // ignore — AbortError or network
      } finally {
        setSearching(false);
      }
    }, 350);
    return () => {
      if (debounceRef.current) window.clearTimeout(debounceRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tickerInput]);

  function pickSuggestion(r: LookupResult) {
    onChange({
      ...value,
      ticker: r.ticker,
      tickerName: r.name,
      currency:
        r.currency === "KRW" || r.currency === "USD"
          ? (r.currency as "USD" | "KRW")
          : value.currency,
    });
    setTickerInput(r.ticker);
    setShowSuggestions(false);
  }

  function applyPreset(p: (typeof PRESETS)[number]) {
    onChange({
      ticker: p.ticker,
      startDate: p.date,
      amount: p.amount,
      currency: p.currency,
      recurring: null,
    });
    setTickerInput(p.ticker);
  }

  const canSubmit =
    !!value.ticker &&
    !!value.startDate &&
    value.amount > 0 &&
    value.startDate <= TODAY &&
    !isLoading;

  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        {/* Ticker search */}
        <div className="relative sm:col-span-2" ref={wrapperRef}>
          <label className="mb-1.5 flex items-center gap-1.5 text-xs font-semibold text-slate-700">
            <Search className="h-3.5 w-3.5" />
            {t("whatIf.form.ticker")}
          </label>
          <input
            type="text"
            inputMode="text"
            autoComplete="off"
            autoCapitalize="characters"
            value={tickerInput}
            placeholder={t("whatIf.form.tickerPlaceholder")}
            onChange={(e) => {
              const v = e.target.value.toUpperCase();
              setTickerInput(v);
              setShowSuggestions(true);
              // immediate local update — allows submit without waiting for lookup
              onChange({ ...value, ticker: v, tickerName: undefined });
            }}
            onFocus={() => setShowSuggestions(true)}
            className="h-11 w-full rounded-xl border border-slate-200 bg-white px-4 text-sm font-medium text-slate-900 outline-none transition focus:border-violet-400 focus:ring-2 focus:ring-violet-200"
          />
          {showSuggestions && tickerInput.length > 0 && (
            <div className="absolute left-0 right-0 top-full z-20 mt-1 overflow-hidden rounded-xl border border-slate-200 bg-white shadow-lg">
              {searching ? (
                <div className="px-4 py-3 text-xs text-slate-500">
                  {t("topbar.searching")}
                </div>
              ) : suggestions.length === 0 ? (
                <div className="px-4 py-3 text-xs text-slate-400">
                  {t("topbar.noResults", { query: tickerInput })}
                </div>
              ) : (
                suggestions.map((r) => (
                  <button
                    key={r.ticker}
                    type="button"
                    onClick={() => pickSuggestion(r)}
                    className="flex w-full items-center justify-between gap-3 px-4 py-2.5 text-left hover:bg-slate-50"
                  >
                    <div className="min-w-0">
                      <div className="text-sm font-bold text-slate-900">
                        {r.ticker}
                      </div>
                      <div className="truncate text-xs text-slate-500">
                        {r.name}
                      </div>
                    </div>
                    <span className="rounded-md bg-slate-100 px-2 py-0.5 text-[10px] font-semibold text-slate-600">
                      {r.currency}
                    </span>
                  </button>
                ))
              )}
            </div>
          )}
        </div>

        {/* Start date */}
        <div>
          <label className="mb-1.5 flex items-center gap-1.5 text-xs font-semibold text-slate-700">
            <Calendar className="h-3.5 w-3.5" />
            {t("whatIf.form.startDate")}
          </label>
          <input
            type="date"
            min={MIN_DATE}
            max={TODAY}
            value={value.startDate}
            onChange={(e) =>
              onChange({ ...value, startDate: e.target.value })
            }
            className="h-11 w-full rounded-xl border border-slate-200 bg-white px-4 text-sm font-medium text-slate-900 outline-none transition focus:border-violet-400 focus:ring-2 focus:ring-violet-200"
          />
        </div>

        {/* Amount + currency */}
        <div>
          <label className="mb-1.5 flex items-center gap-1.5 text-xs font-semibold text-slate-700">
            <Coins className="h-3.5 w-3.5" />
            {t("whatIf.form.amount")}
          </label>
          <div className="flex h-11 overflow-hidden rounded-xl border border-slate-200 bg-white transition focus-within:border-violet-400 focus-within:ring-2 focus-within:ring-violet-200">
            <input
              type="number"
              inputMode="numeric"
              min={1000}
              step={value.currency === "KRW" ? 10000 : 10}
              value={value.amount || ""}
              onChange={(e) => {
                const n = Number(e.target.value);
                onChange({
                  ...value,
                  amount: isFinite(n) ? Math.max(0, Math.floor(n)) : 0,
                });
              }}
              className="min-w-0 flex-1 px-4 text-sm font-medium text-slate-900 outline-none"
            />
            <div className="flex border-l border-slate-200 bg-slate-50 text-xs font-semibold">
              {(["KRW", "USD"] as const).map((c) => (
                <button
                  key={c}
                  type="button"
                  onClick={() => onChange({ ...value, currency: c })}
                  className={cn(
                    "px-3 transition",
                    value.currency === c
                      ? "bg-slate-900 text-white"
                      : "text-slate-600 hover:bg-slate-100",
                  )}
                >
                  {c === "KRW" ? t("whatIf.form.krw") : t("whatIf.form.usd")}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Recurring strategy */}
        <div className="sm:col-span-2">
          <label className="mb-1.5 flex items-center gap-1.5 text-xs font-semibold text-slate-700">
            <Repeat className="h-3.5 w-3.5" />
            {t("whatIf.form.recurring")}
          </label>
          <div className="grid grid-cols-3 gap-2">
            {(
              [
                { mode: null, label: t("whatIf.form.lumpSum") },
                { mode: "monthly", label: t("whatIf.form.monthly") },
                { mode: "weekly", label: t("whatIf.form.weekly") },
              ] as const
            ).map((opt) => {
              const active = value.recurring === opt.mode;
              return (
                <button
                  key={String(opt.mode)}
                  type="button"
                  onClick={() =>
                    onChange({
                      ...value,
                      recurring: opt.mode as RecurringMode,
                    })
                  }
                  className={cn(
                    "h-11 rounded-xl border text-xs font-semibold transition",
                    active
                      ? "border-violet-500 bg-violet-50 text-violet-700"
                      : "border-slate-200 bg-white text-slate-700 hover:border-slate-300",
                  )}
                >
                  {opt.label}
                </button>
              );
            })}
          </div>
        </div>
      </div>

      {/* Submit */}
      <button
        type="button"
        onClick={onSubmit}
        disabled={!canSubmit}
        className={cn(
          "mt-5 h-12 w-full rounded-xl text-sm font-bold text-white transition-all",
          "bg-gradient-to-r from-violet-600 via-blue-500 to-pink-500",
          "shadow-lg shadow-violet-500/25 hover:shadow-xl hover:shadow-violet-500/30 active:scale-[0.99]",
          "disabled:cursor-not-allowed disabled:opacity-50 disabled:shadow-none",
        )}
      >
        {isLoading
          ? t("whatIf.form.calculating")
          : t("whatIf.form.calculate")}
      </button>

      {/* Presets */}
      <div className="mt-5 border-t border-slate-100 pt-4">
        <div className="mb-2 flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wide text-slate-500">
          <Sparkles className="h-3 w-3" />
          {t("whatIf.result.presets")}
        </div>
        <div className="flex flex-wrap gap-2">
          {PRESETS.map((p) => (
            <button
              key={`${p.ticker}-${p.date}`}
              type="button"
              onClick={() => applyPreset(p)}
              className="rounded-full border border-slate-200 bg-white px-3 py-1.5 text-[11px] font-semibold text-slate-700 transition hover:border-violet-300 hover:bg-violet-50 hover:text-violet-700"
            >
              {p.labelKo}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
