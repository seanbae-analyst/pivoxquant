"use client";

/**
 * AddSymbolModal — Editorial modal to add a symbol + optional note to the
 * watchlist. Uses the same Ivory/Bronze treatment as the rest of the shell.
 *
 * POSTs to API.watchlist.add with { ticker, note }. The ticker field also
 * runs a debounced /api/search autocomplete so the user can pick from a
 * live suggestion list rather than typing a symbol blindly. The global
 * Cmd+K palette remains available as an escape hatch.
 *
 * Legal: footnote stays "Observations only — no targets, no recommendations."
 * to match the rest of the watchlist surface area.
 */

import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { Search, X, Loader2 } from "lucide-react";
import { ModalShell } from "@/components/ui/modal-shell";
import { apiFetch, ApiError } from "@/lib/api";
import { API, SEARCH } from "@/lib/endpoints";
import { openSearchCommand } from "@/components/ui/search-command";

interface Props {
  onClose: () => void;
  onAdded: () => void;
}

interface Suggestion {
  ticker: string;
  name: string;
  exchange?: string;
  is_korean?: boolean;
}

export function AddSymbolModal({ onClose, onAdded }: Props) {
  const [ticker, setTicker] = useState("");
  const [note, setNote] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
  const [loading, setLoading] = useState(false);
  const [picked, setPicked] = useState(false); // user selected a suggestion; suppress popover
  const abortRef = useRef<AbortController | null>(null);

  // Debounced autocomplete. Pre-empts stale requests like the palette does.
  useEffect(() => {
    const q = ticker.trim();
    if (picked || q.length < 1) {
      setSuggestions([]);
      setLoading(false);
      abortRef.current?.abort();
      return;
    }
    setLoading(true);
    const ctrl = new AbortController();
    abortRef.current?.abort();
    abortRef.current = ctrl;
    const t = window.setTimeout(async () => {
      try {
        const res = await fetch(`${SEARCH}?q=${encodeURIComponent(q)}&limit=6`, {
          credentials: "include",
          signal: ctrl.signal,
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const body: { results?: Suggestion[] } = await res.json();
        setSuggestions(body.results ?? []);
      } catch (err) {
        if ((err as { name?: string })?.name === "AbortError") return;
        setSuggestions([]);
      } finally {
        if (abortRef.current === ctrl) setLoading(false);
      }
    }, 300);
    return () => {
      window.clearTimeout(t);
      ctrl.abort();
    };
  }, [ticker, picked]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    // Re-entrancy guard (2026-04-28): rapid double-submit (Enter twice or
    // double-click) could fire two POSTs before React commits the disabled
    // state on the button. The second submission would race the first and
    // — if the user typed a different ticker between presses — could record
    // the wrong symbol. The button-disabled state is necessary but not
    // sufficient because `submitting` updates asynchronously.
    if (submitting) return;
    const clean = ticker.trim().toUpperCase();
    if (!clean) return;
    setSubmitting(true);
    try {
      await apiFetch(API.watchlist.add, {
        method: "POST",
        body: JSON.stringify({ ticker: clean, note: note.trim() || undefined }),
      });
      toast.success(`${clean} added to watchlist`);
      onAdded();
      onClose();
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        toast.error("Already in watchlist");
      } else {
        toast.error(`Could not add ${clean}`);
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <ModalShell onClose={onClose} ariaLabel="Add symbol">
      <form
        onSubmit={handleSubmit}
        className="w-full max-w-md overflow-hidden rounded-2xl shadow-[0_24px_60px_-20px_rgba(10,10,10,0.35)]"
        style={{ background: "var(--pq-ivory)", border: "0.5px solid var(--pq-hairline)" }}
      >
        {/* Header */}
        <div
          className="flex items-start justify-between gap-3 px-5 py-4"
          style={{ borderBottom: "0.5px solid var(--pq-hairline)" }}
        >
          <div>
            <div
              className="text-[10px] uppercase"
              style={{ letterSpacing: "0.2em", color: "var(--pq-muted)" }}
            >
              Watchlist
            </div>
            <div
              className="mt-0.5 text-xl font-serif"
              style={{ color: "var(--pq-ink)" }}
            >
              Add a symbol
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="flex h-7 w-7 items-center justify-center rounded-md transition-colors hover:bg-[rgba(139,111,71,0.08)]"
            style={{ color: "var(--pq-muted)" }}
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Body */}
        <div className="space-y-5 px-5 py-5">
          {/* Ticker input */}
          <div className="relative">
            <label
              className="block text-[10px] uppercase"
              style={{ letterSpacing: "0.2em", color: "var(--pq-muted)" }}
            >
              Ticker
            </label>
            <div
              className="mt-2 flex items-center gap-2 rounded-md px-3 py-2"
              style={{ border: "0.5px solid var(--pq-hairline)", background: "transparent" }}
            >
              <input
                type="text"
                value={ticker}
                onChange={(e) => {
                  setTicker(e.target.value);
                  setPicked(false);
                }}
                placeholder="AAPL, NVDA, 005930.KS"
                autoFocus
                className="flex-1 bg-transparent font-mono text-sm uppercase outline-none placeholder:normal-case"
                style={{ color: "var(--pq-ink)", letterSpacing: "0.02em" }}
              />
              {loading && (
                <Loader2
                  className="h-3.5 w-3.5 animate-spin"
                  style={{ color: "var(--pq-muted)" }}
                  aria-label="Searching"
                />
              )}
              <button
                type="button"
                onClick={() => openSearchCommand()}
                aria-label="Open search palette"
                className="flex items-center gap-1.5 rounded px-2 py-1 text-[10px] uppercase transition-colors hover:bg-[rgba(139,111,71,0.08)]"
                style={{ color: "var(--pq-bronze)", letterSpacing: "0.15em" }}
              >
                <Search className="h-3 w-3" />
                Search
              </button>
            </div>

            {/* Autocomplete popover */}
            {!picked && ticker.trim().length > 0 && suggestions.length > 0 && (
              <div
                className="absolute left-0 right-0 z-10 mt-1 max-h-56 overflow-y-auto rounded-md"
                style={{
                  background: "var(--pq-ivory)",
                  border: "0.5px solid var(--pq-hairline)",
                  boxShadow: "0 12px 32px -16px rgba(10,10,10,0.25)",
                }}
              >
                {suggestions.map((s) => (
                  <button
                    key={s.ticker}
                    type="button"
                    onClick={() => {
                      setTicker(s.ticker);
                      setPicked(true);
                      setSuggestions([]);
                    }}
                    className="flex w-full items-center gap-3 px-3 py-2 text-left transition-colors hover:bg-[rgba(139,111,71,0.08)]"
                  >
                    <span
                      className="w-24 truncate font-mono text-xs font-semibold"
                      style={{ color: "var(--pq-bronze)" }}
                    >
                      {s.ticker}
                    </span>
                    <span
                      className="flex-1 truncate text-sm"
                      style={{ color: "var(--pq-ink)" }}
                    >
                      {s.name}
                    </span>
                    {s.exchange && (
                      <span
                        className="text-[10px] uppercase"
                        style={{ letterSpacing: "0.12em", color: "var(--pq-muted)" }}
                      >
                        {s.exchange}
                      </span>
                    )}
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Note */}
          <div>
            <label
              className="block text-[10px] uppercase"
              style={{ letterSpacing: "0.2em", color: "var(--pq-muted)" }}
            >
              Note <span className="normal-case" style={{ letterSpacing: 0 }}>(optional)</span>
            </label>
            <textarea
              value={note}
              onChange={(e) => setNote(e.target.value)}
              rows={3}
              placeholder="Why this symbol? What to observe?"
              maxLength={500}
              className="mt-2 w-full resize-none rounded-md bg-transparent px-3 py-2 text-sm outline-none font-serif"
              style={{
                border: "0.5px solid var(--pq-hairline)",
                color: "var(--pq-ink)",
              }}
            />
            <p
              className="mt-1 text-[11px] font-serif"
              style={{ color: "var(--pq-muted)" }}
            >
              Observations only — no targets, no recommendations.
            </p>
          </div>
        </div>

        {/* Footer */}
        <div
          className="flex items-center justify-end gap-3 px-5 py-3"
          style={{ borderTop: "0.5px solid var(--pq-hairline)" }}
        >
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 text-xs uppercase"
            style={{ letterSpacing: "0.18em", color: "var(--pq-muted)" }}
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={!ticker.trim() || submitting}
            className="rounded px-5 py-2 text-xs uppercase transition-opacity disabled:opacity-40"
            style={{
              background: "var(--pq-bronze)",
              color: "var(--pq-ivory)",
              letterSpacing: "0.2em",
            }}
          >
            {submitting ? "Adding…" : "Add"}
          </button>
        </div>
      </form>
    </ModalShell>
  );
}
