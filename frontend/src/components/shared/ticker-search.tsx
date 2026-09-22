"use client";

/**
 * <TickerSearch /> — the shared debounced /api/search autocomplete.
 *
 * Extracted 2026-09-22 from `portfolio/v2/add-position-modal-v2.tsx`, which
 * held the only copy of this behaviour inline. The observation-note composer
 * needs the same picker, and a second hand-rolled copy is how the two drift
 * (docs/design/observation-notes_2026-09-22.md §5).
 *
 * Behaviour is preserved byte-for-byte from the add-position version:
 *   - 300ms debounce on the typed query, cleared on every keystroke;
 *   - an AbortController per in-flight request so a stale response can never
 *     overwrite a newer one;
 *   - a `picked` flag that closes the popover after a selection AND
 *     short-circuits the effect, so writing the canonical ticker back into
 *     the input does not fire another search. Editing the field re-arms it.
 *
 * `/api/search` is the ONE market route that stays live while
 * MARKET_DATA_DISPLAY_ENABLED is off (routes/market.py) — it resolves names,
 * not quotes. Nothing here renders a price.
 *
 * The raw `fetch` is deliberate: apiFetch does not forward an AbortSignal in
 * a way that lets us pre-empt stale keystrokes, and this is a read with no
 * CSRF surface. See the regression-guards opt-out comment below.
 */

import * as React from "react";
import { SEARCH } from "@/lib/endpoints";
import { displayName, normalizeTicker } from "@/lib/format";

/** One `/api/search` hit. Mirrors the backend result shape 1:1. */
export interface TickerSearchResult {
  ticker: string;
  name: string;
  exchange?: string;
  currency?: string;
  is_korean?: boolean;
}

export interface TickerSearchProps {
  /** Controlled input text. The parent owns it (add-position validates on it). */
  value: string;
  /**
   * Raw text changed. Already upper-cased, matching the add-position field.
   * Required because callers read the half-typed symbol before a pick.
   */
  onChange: (value: string) => void;
  /** A suggestion was chosen. `result.ticker` is the canonical exchange form. */
  onPick: (result: TickerSearchResult) => void;
  placeholder?: string;
  /** Max suggestions requested from the backend. */
  limit?: number;
  disabled?: boolean;
  autoFocus?: boolean;
  /** Accessible name of the input. Default matches the add-position field. */
  ariaLabel?: string;
  /** Forwarded to the input — the HTML `required` attribute. */
  required?: boolean;
  /** Inline style for the input (add-position passes its hairline field style). */
  inputStyle?: React.CSSProperties;
  /** Class list for the input (composer passes the journal bordered style). */
  inputClassName?: string;
  /**
   * Show the resolved company name under the input after a pick. The
   * composer turns this off because it renders a chip instead.
   */
  showPickedName?: boolean;
}

const DEBOUNCE_MS = 300;

export function TickerSearch({
  value,
  onChange,
  onPick,
  placeholder = "AAPL · 005930.KS",
  limit = 6,
  disabled = false,
  autoFocus = false,
  ariaLabel = "Symbol",
  required = false,
  inputStyle,
  inputClassName,
  showPickedName = true,
}: TickerSearchProps) {
  const [suggestions, setSuggestions] = React.useState<TickerSearchResult[]>([]);
  const [searchLoading, setSearchLoading] = React.useState(false);
  const [picked, setPicked] = React.useState(false);
  const [selectedName, setSelectedName] = React.useState("");
  const abortRef = React.useRef<AbortController | null>(null);

  // An externally cleared field (the composer empties it after adding a chip)
  // re-arms the search — otherwise `picked` would suppress the next query.
  React.useEffect(() => {
    if (value === "") {
      setPicked(false);
      setSelectedName("");
    }
  }, [value]);

  // Debounced symbol autocomplete. Pre-empts stale requests; skips while a
  // suggestion is already picked (re-armed when the user edits the field).
  React.useEffect(() => {
    const q = value.trim();
    if (disabled || picked || q.length < 1) {
      setSuggestions([]);
      setSearchLoading(false);
      abortRef.current?.abort();
      return;
    }
    setSearchLoading(true);
    const ctrl = new AbortController();
    abortRef.current?.abort();
    abortRef.current = ctrl;
    const t = window.setTimeout(async () => {
      try {
        // regression-guards: allow-raw-fetch (debounced /api/search autocomplete —
        // needs the AbortController signal to pre-empt stale keystrokes, which
        // apiFetch does not expose).
        const res = await fetch(
          `${SEARCH}?q=${encodeURIComponent(q)}&limit=${limit}`,
          { credentials: "include", signal: ctrl.signal },
        );
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const body: { results?: TickerSearchResult[] } = await res.json();
        setSuggestions(body.results ?? []);
      } catch (err) {
        if ((err as { name?: string })?.name === "AbortError") return;
        setSuggestions([]);
      } finally {
        if (abortRef.current === ctrl) setSearchLoading(false);
      }
    }, DEBOUNCE_MS);
    return () => {
      window.clearTimeout(t);
      ctrl.abort();
    };
  }, [value, picked, disabled, limit]);

  return (
    <div style={{ position: "relative" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <input
          required={required}
          disabled={disabled}
          autoFocus={autoFocus}
          value={value}
          onChange={(e) => {
            onChange(e.target.value.toUpperCase());
            setPicked(false);
            setSelectedName("");
          }}
          placeholder={placeholder}
          autoComplete="off"
          aria-label={ariaLabel}
          className={inputClassName}
          style={inputStyle ? { ...inputStyle, flex: 1 } : { flex: 1 }}
        />
        {searchLoading && (
          <span
            className="font-mono uppercase"
            aria-label="Searching"
            style={{
              fontSize: "var(--pq-text-eyebrow)",
              letterSpacing: "0.14em",
              color: "var(--pq-ivory-faint)",
            }}
          >
            …
          </span>
        )}
      </div>

      {/* Picked-symbol confirmation — shows the resolved company name. */}
      {showPickedName && picked && selectedName && (
        <span
          className="font-serif"
          style={{
            display: "block",
            marginTop: 6,
            fontSize: "var(--pq-text-body)",
            color: "var(--pq-bronze)",
          }}
        >
          {selectedName}
        </span>
      )}

      {/* Autocomplete popover */}
      {!picked && value.trim().length > 0 && suggestions.length > 0 && (
        <div
          role="listbox"
          aria-label="종목 검색 결과"
          style={{
            position: "absolute",
            left: 0,
            right: 0,
            top: "100%",
            zIndex: 20,
            marginTop: 4,
            maxHeight: 224,
            overflowY: "auto",
            background: "var(--pq-ink, #050505)",
            border:
              "1px solid var(--pq-hairline-ink, rgba(245,240,232,0.16))",
            borderRadius: "var(--pq-radius-card, 4px)",
            boxShadow: "0 18px 44px -20px rgba(0,0,0,0.7)",
          }}
        >
          {suggestions.map((s) => (
            <button
              key={s.ticker}
              type="button"
              role="option"
              aria-selected={false}
              onClick={() => {
                // Canonical exchange ticker (e.g. "005930.KS") — the backend
                // resolves this on submit; do NOT strip the suffix.
                setSelectedName(displayName(s.ticker, s.name));
                setPicked(true);
                setSuggestions([]);
                onPick(s);
              }}
              style={{
                display: "flex",
                width: "100%",
                alignItems: "center",
                gap: 12,
                padding: "10px 12px",
                background: "transparent",
                border: "none",
                borderBottom:
                  "1px solid var(--pq-hairline-ink, rgba(245,240,232,0.08))",
                textAlign: "left",
                cursor: "pointer",
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = "rgba(184,149,106,0.12)";
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = "transparent";
              }}
            >
              <span
                className="font-serif"
                style={{
                  flex: 1,
                  minWidth: 0,
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  whiteSpace: "nowrap",
                  fontSize: "var(--pq-text-body)",
                  fontWeight: 600,
                  color: "var(--pq-ivory)",
                }}
              >
                {displayName(s.ticker, s.name)}
              </span>
              <span
                className="font-mono uppercase"
                style={{
                  fontSize: "var(--pq-text-eyebrow)",
                  letterSpacing: "0.12em",
                  color: "var(--pq-bronze)",
                  whiteSpace: "nowrap",
                }}
              >
                {normalizeTicker(s.ticker)}
                {s.exchange ? ` · ${s.exchange}` : ""}
              </span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export default TickerSearch;
