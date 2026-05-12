"use client";

/**
 * <SignalsFilterBar /> — sticky 4-column filter rail.
 *
 * Source: design-mockups/signals-v2/SPEC.md §2.
 * Sticky to top of <main>, Vantablack background, 32px gap.
 *
 *   col 1 — 3 toggle chips (POSITIVE / NEGATIVE / NEUTRAL)
 *   col 2 — Strength range slider (0..1, two-handle)
 *   col 3 — Symbol autocomplete (datalist from watchlist + positions)
 *   col 4 — Time toggle (Today / 7d / 30d) + Refresh button
 *
 * No banned vocabulary in any visible label.
 */

import * as React from "react";
import { RefreshCw } from "lucide-react";
import type { SignalLabel } from "@/lib/types";

interface FilterValue {
  labels: Set<SignalLabel>;
  strengthMin: number;
  strengthMax: number;
  symbol: string | null;
  window: "today" | "7d" | "30d" | "all";
}

interface Props {
  value: FilterValue;
  onChange: (next: FilterValue) => void;
  counts?: { positive: number; negative: number; neutral: number };
  symbolHints?: string[];
  onRefresh?: () => void;
  refreshing?: boolean;
}

const LABELS: Array<{ key: SignalLabel; display: string; tone: string }> = [
  { key: "POSITIVE", display: "Positive", tone: "var(--pq-positive, #dc2626)" },
  { key: "NEGATIVE", display: "Negative", tone: "var(--pq-negative, #2563eb)" },
  { key: "NEUTRAL", display: "Neutral", tone: "rgba(245,240,232,0.55)" },
];

const WINDOWS: Array<{ key: FilterValue["window"]; display: string }> = [
  { key: "all", display: "All" },
  { key: "today", display: "Today" },
  { key: "7d", display: "7d" },
  { key: "30d", display: "30d" },
];

function chipBaseStyle(active: boolean): React.CSSProperties {
  return {
    appearance: "none",
    background: active ? "var(--pq-bronze-08, rgba(184,149,106,0.08))" : "transparent",
    border: active
      ? "1px solid var(--pq-bronze, #B8956A)"
      : "1px solid var(--pq-hairline, var(--pq-ivory-line))",
    borderRadius: "var(--pq-radius-cta, 2px)",
    padding: "8px 12px",
    fontSize: "var(--pq-text-eyebrow)",
    letterSpacing: "0.18em",
    textTransform: "uppercase",
    color: active ? "var(--pq-ivory, #F5F0E8)" : "rgba(245,240,232,0.55)",
    cursor: "pointer",
    transition: "border-color 200ms cubic-bezier(0.16, 1, 0.3, 1), background 200ms",
  };
}

export function SignalsFilterBar({
  value,
  onChange,
  counts,
  symbolHints,
  onRefresh,
  refreshing = false,
}: Props) {
  const toggleLabel = (label: SignalLabel) => {
    const next = new Set(value.labels);
    if (next.has(label)) next.delete(label);
    else next.add(label);
    onChange({ ...value, labels: next });
  };

  const setWindow = (w: FilterValue["window"]) => onChange({ ...value, window: w });

  const setStrengthMin = (n: number) =>
    onChange({ ...value, strengthMin: Math.min(n, value.strengthMax) });
  const setStrengthMax = (n: number) =>
    onChange({ ...value, strengthMax: Math.max(n, value.strengthMin) });

  const symbolInputId = React.useId();
  const dataListId = `${symbolInputId}-list`;

  return (
    <div
      className="signals-filter-bar"
      style={{
        position: "sticky",
        top: 0,
        zIndex: 12,
        background: "rgba(5,5,5,0.92)",
        backdropFilter: "blur(8px)",
        WebkitBackdropFilter: "blur(8px)",
        borderBottom: "1px solid var(--pq-hairline, var(--pq-ivory-line))",
        padding: "16px 0",
        marginBottom: 32,
      }}
    >
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "minmax(240px, 1.1fr) minmax(180px, 1fr) minmax(180px, 1fr) auto",
          gap: 28,
          alignItems: "center",
          flexWrap: "wrap",
        }}
        className="signals-filter-grid"
      >
        {/* col 1 — label chips */}
        <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
          {LABELS.map((l) => {
            const active = value.labels.has(l.key);
            const count =
              l.key === "POSITIVE"
                ? counts?.positive
                : l.key === "NEGATIVE"
                  ? counts?.negative
                  : counts?.neutral;
            return (
              <button
                key={l.key}
                type="button"
                onClick={() => toggleLabel(l.key)}
                aria-pressed={active}
                className="font-mono"
                style={chipBaseStyle(active)}
              >
                <span
                  style={{
                    display: "inline-block",
                    width: 6,
                    height: 6,
                    borderRadius: 0,
                    background: l.tone,
                    marginRight: 8,
                    verticalAlign: "middle",
                  }}
                  aria-hidden
                />
                {l.display}
                {typeof count === "number" && (
                  <span
                    style={{
                      marginLeft: 8,
                      fontVariantNumeric: "tabular-nums",
                      color: "rgba(245,240,232,0.55)",
                    }}
                  >
                    · {count}
                  </span>
                )}
              </button>
            );
          })}
        </div>

        {/* col 2 — strength range */}
        <div>
          <div
            className="font-mono uppercase"
            style={{
              fontSize: "var(--pq-text-eyebrow)",
              letterSpacing: "0.22em",
              color: "rgba(245,240,232,0.55)",
              marginBottom: 6,
            }}
          >
            Strength{" "}
            <span style={{ color: "var(--pq-ivory, #F5F0E8)", fontVariantNumeric: "tabular-nums" }}>
              {value.strengthMin.toFixed(2)} – {value.strengthMax.toFixed(2)}
            </span>
          </div>
          <div style={{ display: "flex", gap: 8 }}>
            <input
              type="range"
              min={0}
              max={1}
              step={0.05}
              value={value.strengthMin}
              onChange={(e) => setStrengthMin(parseFloat(e.target.value))}
              aria-label="Minimum strength"
              aria-valuemin={0}
              aria-valuemax={1}
              aria-valuenow={value.strengthMin}
              style={{ flex: 1, accentColor: "var(--pq-bronze, #B8956A)" }}
            />
            <input
              type="range"
              min={0}
              max={1}
              step={0.05}
              value={value.strengthMax}
              onChange={(e) => setStrengthMax(parseFloat(e.target.value))}
              aria-label="Maximum strength"
              aria-valuemin={0}
              aria-valuemax={1}
              aria-valuenow={value.strengthMax}
              style={{ flex: 1, accentColor: "var(--pq-bronze, #B8956A)" }}
            />
          </div>
        </div>

        {/* col 3 — symbol autocomplete */}
        <div>
          <label
            htmlFor={symbolInputId}
            className="font-mono uppercase"
            style={{
              fontSize: "var(--pq-text-eyebrow)",
              letterSpacing: "0.22em",
              color: "rgba(245,240,232,0.55)",
              display: "block",
              marginBottom: 6,
            }}
          >
            Symbol
          </label>
          <input
            id={symbolInputId}
            list={dataListId}
            value={value.symbol ?? ""}
            onChange={(e) => onChange({ ...value, symbol: e.target.value || null })}
            placeholder="AAPL · 005930.KS …"
            style={{
              width: "100%",
              background: "transparent",
              border: "1px solid var(--pq-hairline, var(--pq-ivory-line))",
              borderRadius: "var(--pq-radius-cta, 2px)",
              padding: "8px 10px",
              // 16px to prevent iOS Safari/Chrome auto-zoom on input focus
              fontSize: "var(--pq-text-h6)",
              color: "var(--pq-ivory, #F5F0E8)",
              letterSpacing: "0.04em",
              outline: "none",
            }}
          className="font-mono" />
          {symbolHints && symbolHints.length > 0 && (
            <datalist id={dataListId}>
              {symbolHints.map((t) => (
                <option key={t} value={t} />
              ))}
            </datalist>
          )}
        </div>

        {/* col 4 — time toggle + refresh */}
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          {WINDOWS.map((w) => {
            const active = value.window === w.key;
            return (
              <button
                key={w.key}
                type="button"
                onClick={() => setWindow(w.key)}
                aria-pressed={active}
                className="font-mono"
                style={chipBaseStyle(active)}
              >
                {w.display}
              </button>
            );
          })}
          {onRefresh && (
            <button
              type="button"
              onClick={onRefresh}
              disabled={refreshing}
              aria-label="Refresh signals"
              style={{
                appearance: "none",
                background: "transparent",
                border: "1px solid var(--pq-hairline, var(--pq-ivory-line))",
                borderRadius: "var(--pq-radius-cta, 2px)",
                padding: "8px 10px",
                color: "var(--pq-bronze, #B8956A)",
                cursor: refreshing ? "default" : "pointer",
                opacity: refreshing ? 0.4 : 1,
                display: "inline-flex",
                alignItems: "center",
                gap: 6,
                fontSize: "var(--pq-text-eyebrow)",
                letterSpacing: "0.18em",
                textTransform: "uppercase",
              }}
            className="font-mono" >
              <RefreshCw
                size={12}
                strokeWidth={1.6}
                className={refreshing ? "animate-spin" : ""}
              />
              Refresh
            </button>
          )}
        </div>
      </div>

      <style jsx>{`
        @media (max-width: 1023px) {
          .signals-filter-grid {
            grid-template-columns: 1fr 1fr !important;
          }
        }
        @media (max-width: 639px) {
          .signals-filter-grid {
            grid-template-columns: 1fr !important;
          }
        }
      `}</style>
    </div>
  );
}
