"use client";

/**
 * Price direction color conventions.
 *
 * KR (default): 상승 = 빨강, 하락 = 파랑 (Korean exchange convention)
 * US: 상승 = 녹색, 하락 = 빨강 (Western/NYSE convention)
 *
 * The actual hex values live as CSS variables (--up / --down) in globals.css.
 * Setting [data-price-mode="us"] on <html> swaps the variables at the CSS level,
 * so all `up-color` / `down-color` classes across the app switch together.
 *
 * This module exposes:
 *   - getPriceMode() / setPriceMode()   — persists the user's pick in localStorage
 *   - usePriceMode()                     — React hook for client components
 *   - upClass() / downClass()            — helper that returns the right class
 *                                           for a numeric change (handles 0 → neutral)
 */

import { useEffect, useState } from "react";

export type PriceMode = "kr" | "us";
const STORAGE_KEY = "pq.priceMode";
const DEFAULT_MODE: PriceMode = "kr";

export function getPriceMode(): PriceMode {
  if (typeof window === "undefined") return DEFAULT_MODE;
  const v = window.localStorage.getItem(STORAGE_KEY);
  return v === "us" ? "us" : "kr";
}

export function setPriceMode(mode: PriceMode) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(STORAGE_KEY, mode);
  applyPriceMode(mode);
  // Broadcast so sibling components can re-render.
  window.dispatchEvent(new CustomEvent("pq:price-mode", { detail: mode }));
}

export function applyPriceMode(mode: PriceMode) {
  if (typeof document === "undefined") return;
  document.documentElement.setAttribute("data-price-mode", mode);
}

export function usePriceMode(): [PriceMode, (m: PriceMode) => void] {
  // Lazy initializer: read stored mode exactly once at mount. Safe on SSR
  // because getPriceMode() returns DEFAULT_MODE when window is undefined,
  // and the first client render will agree with the server render.
  const [mode, setMode] = useState<PriceMode>(() => getPriceMode());

  // Sync the <html data-price-mode="..."> attribute with React state.
  // Runs on mount (in case the attribute wasn't set yet) and whenever mode
  // changes via setPriceMode() locally.
  useEffect(() => {
    applyPriceMode(mode);
  }, [mode]);

  // Subscribe to external price-mode broadcasts (other tabs / sibling
  // components). The setState inside the handler is a subscription callback,
  // not a synchronous effect body call — allowed by react-hooks/set-state-in-effect.
  useEffect(() => {
    const handler = (e: Event) => {
      const ce = e as CustomEvent<PriceMode>;
      if (ce.detail) setMode(ce.detail);
    };
    window.addEventListener("pq:price-mode", handler);
    return () => window.removeEventListener("pq:price-mode", handler);
  }, []);

  return [mode, setPriceMode];
}

/**
 * Return the semantic color class for a numeric change.
 * Pass a number (percent or absolute). Zero maps to neutral.
 */
export function changeColorClass(value: number | null | undefined): string {
  if (value === null || value === undefined || value === 0) return "neutral-color";
  return value > 0 ? "up-color" : "down-color";
}
