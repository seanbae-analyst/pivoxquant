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

import { useEffect, useRef, useState, type CSSProperties } from "react";
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
      // P1 (wave1-critical): abort any in-flight lookup so a late
      // response can't write to a stale `setSuggestions` after unmount
      // (or after the user picked a suggestion mid-flight).
      abortRef.current?.abort();
      abortRef.current = null;
    };
    // P1 (wave1-critical): include `value.ticker` in deps. The early-bail
    // guard `q === value.ticker` reads the prop, so when the parent
    // updates value.ticker (e.g. URL navigation, preset apply, suggestion
    // pick) the effect must re-evaluate to avoid a stale comparison
    // against a previous parent value. The bail prevents an unnecessary
    // network call when tickerInput already matches the new parent ticker.
  }, [tickerInput, value.ticker]);

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

  // v3 Vantablack tokens — surfaces, hairlines, bronze focus rings, ivory text.
  // Shared input class to keep ticker/date/amount visually consistent.
  const INPUT_CLASS =
    "h-11 w-full rounded-sm px-4 text-sm font-medium outline-none transition focus:ring-1";
  const INPUT_STYLE: CSSProperties = {
    backgroundColor: "rgba(255, 255, 255, 0.02)",
    border: "1px solid var(--pq-ivory-line)",
    color: "var(--pq-ivory)",
  };

  return (
    <div
      className="rounded-sm border p-5 sm:p-6"
      style={{
        borderColor: "var(--pq-ivory-line)",
        backgroundColor: "rgba(255, 255, 255, 0.015)",
      }}
    >
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        {/* Ticker search */}
        <div className="relative sm:col-span-2" ref={wrapperRef}>
          <label
            className="pq-ink-label mb-1.5 flex items-center gap-1.5"
            style={{ color: "var(--pq-bronze)" }}
          >
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
            className={INPUT_CLASS}
            style={{
              ...INPUT_STYLE,
              ["--tw-ring-color" as string]: "var(--pq-bronze)",
            }}
          />
          {showSuggestions && tickerInput.length > 0 && (
            <div
              className="absolute left-0 right-0 top-full z-20 mt-1 overflow-hidden rounded-sm border"
              style={{
                borderColor: "var(--pq-ivory-line)",
                backgroundColor: "rgba(5, 5, 5, 0.96)",
                backdropFilter: "blur(6px)",
              }}
            >
              {searching ? (
                <div
                  className="px-4 py-3 text-xs"
                  style={{ color: "rgba(245, 240, 232, 0.55)" }}
                >
                  {t("topbar.searching")}
                </div>
              ) : suggestions.length === 0 ? (
                <div
                  className="px-4 py-3 text-xs"
                  style={{ color: "rgba(245, 240, 232, 0.4)" }}
                >
                  {t("topbar.noResults", { query: tickerInput })}
                </div>
              ) : (
                suggestions.map((r) => (
                  <button
                    key={r.ticker}
                    type="button"
                    onClick={() => pickSuggestion(r)}
                    className="flex w-full items-center justify-between gap-3 px-4 py-2.5 text-left transition hover:bg-[rgba(184,149,106,0.08)]"
                  >
                    <div className="min-w-0">
                      <div
                        className="truncate text-sm font-bold"
                        style={{ color: "var(--pq-ivory)" }}
                      >
                        {r.name || r.ticker}
                      </div>
                      <div
                        className="truncate font-mono text-xs"
                        style={{ color: "rgba(245, 240, 232, 0.55)" }}
                      >
                        {r.ticker}
                      </div>
                    </div>
                    <span
                      className="rounded-sm px-2 py-0.5 font-mono text-[10px] font-semibold"
                      style={{
                        backgroundColor: "rgba(184, 149, 106, 0.12)",
                        color: "var(--pq-bronze)",
                      }}
                    >
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
          <label
            className="pq-ink-label mb-1.5 flex items-center gap-1.5"
            style={{ color: "var(--pq-bronze)" }}
          >
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
            // colorScheme: dark — matches Vantablack so native date picker
            // glyph isn't bright white on the ink field.
            className={INPUT_CLASS}
            style={{
              ...INPUT_STYLE,
              colorScheme: "dark",
              ["--tw-ring-color" as string]: "var(--pq-bronze)",
            }}
          />
        </div>

        {/* Amount + currency */}
        <div>
          <label
            className="pq-ink-label mb-1.5 flex items-center gap-1.5"
            style={{ color: "var(--pq-bronze)" }}
          >
            <Coins className="h-3.5 w-3.5" />
            {t("whatIf.form.amount")}
          </label>
          <div
            className="flex h-11 overflow-hidden rounded-sm transition focus-within:ring-1"
            style={{
              border: "1px solid var(--pq-ivory-line)",
              backgroundColor: "rgba(255, 255, 255, 0.02)",
              ["--tw-ring-color" as string]: "var(--pq-bronze)",
            }}
          >
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
              className="min-w-0 flex-1 bg-transparent px-4 font-mono text-sm font-medium tabular-nums outline-none"
              style={{ color: "var(--pq-ivory)" }}
            />
            <div
              className="flex text-xs font-semibold"
              style={{
                borderLeft: "1px solid var(--pq-ivory-line)",
                backgroundColor: "rgba(255, 255, 255, 0.015)",
              }}
            >
              {(["KRW", "USD"] as const).map((c) => {
                const active = value.currency === c;
                return (
                  <button
                    key={c}
                    type="button"
                    onClick={() => onChange({ ...value, currency: c })}
                    className="px-3 transition"
                    style={{
                      backgroundColor: active
                        ? "var(--pq-bronze)"
                        : "transparent",
                      color: active
                        ? "var(--pq-ink)"
                        : "rgba(245, 240, 232, 0.65)",
                    }}
                  >
                    {c === "KRW" ? t("whatIf.form.krw") : t("whatIf.form.usd")}
                  </button>
                );
              })}
            </div>
          </div>
        </div>

        {/* Recurring strategy */}
        <div className="sm:col-span-2">
          <label
            className="pq-ink-label mb-1.5 flex items-center gap-1.5"
            style={{ color: "var(--pq-bronze)" }}
          >
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
                  className="h-11 rounded-sm text-xs font-semibold transition"
                  style={
                    active
                      ? {
                          border: "1px solid var(--pq-bronze)",
                          backgroundColor: "rgba(184, 149, 106, 0.12)",
                          color: "var(--pq-ivory)",
                        }
                      : {
                          border: "1px solid var(--pq-ivory-line)",
                          backgroundColor: "rgba(255, 255, 255, 0.02)",
                          color: "rgba(245, 240, 232, 0.65)",
                        }
                  }
                >
                  {opt.label}
                </button>
              );
            })}
          </div>
        </div>
      </div>

      {/* Submit — bronze CTA pill, consistent with header sign-up CTA. */}
      <button
        type="button"
        onClick={onSubmit}
        disabled={!canSubmit}
        className={cn(
          "pq-ink-btn-bronze mt-5 h-12 w-full justify-center",
          "disabled:cursor-not-allowed disabled:opacity-50",
        )}
        style={{ fontSize: "var(--pq-text-button)" }}
      >
        {isLoading
          ? t("whatIf.form.calculating")
          : t("whatIf.form.calculate")}
      </button>

      {/* Presets */}
      <div
        className="mt-5 pt-4"
        style={{ borderTop: "1px solid var(--pq-ivory-line-soft)" }}
      >
        <div
          className="pq-ink-label mb-2 flex items-center gap-1.5"
          style={{ color: "rgba(245, 240, 232, 0.5)" }}
        >
          <Sparkles className="h-3 w-3" />
          {t("whatIf.result.presets")}
        </div>
        <div className="flex flex-wrap gap-2">
          {PRESETS.map((p) => (
            <button
              key={`${p.ticker}-${p.date}`}
              type="button"
              onClick={() => applyPreset(p)}
              className="rounded-full px-3 py-1.5 text-[11px] font-semibold transition hover:bg-[rgba(184,149,106,0.08)]"
              style={{
                border: "1px solid var(--pq-ivory-line)",
                backgroundColor: "rgba(255, 255, 255, 0.02)",
                color: "rgba(245, 240, 232, 0.75)",
              }}
            >
              {p.labelKo}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
