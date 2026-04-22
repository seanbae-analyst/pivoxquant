"use client";

/**
 * AddSymbolModal — Editorial modal to add a symbol + optional note to the
 * watchlist. Uses the same Ivory/Bronze treatment as the rest of the shell.
 *
 * POSTs to API.watchlist.add with { ticker, note }. Also lets the user launch
 * the global Cmd+K search palette to pick a ticker first.
 */

import { useState } from "react";
import { toast } from "sonner";
import { Search, X } from "lucide-react";
import { ModalShell } from "@/components/ui/modal-shell";
import { apiFetch } from "@/lib/api";
import { API } from "@/lib/endpoints";
import { openSearchCommand } from "@/components/ui/search-command";

interface Props {
  onClose: () => void;
  onAdded: () => void;
}

export function AddSymbolModal({ onClose, onAdded }: Props) {
  const [ticker, setTicker] = useState("");
  const [note, setNote] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
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
    } catch {
      toast.error(`Could not add ${clean}`);
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
              className="mt-0.5 text-xl italic"
              style={{ fontFamily: "var(--font-serif), serif", color: "var(--pq-ink)" }}
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
          <div>
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
                onChange={(e) => setTicker(e.target.value)}
                placeholder="AAPL, NVDA, 005930.KS"
                autoFocus
                className="flex-1 bg-transparent font-mono text-sm uppercase outline-none placeholder:normal-case"
                style={{ color: "var(--pq-ink)", letterSpacing: "0.02em" }}
              />
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
          </div>

          {/* Note */}
          <div>
            <label
              className="block text-[10px] uppercase"
              style={{ letterSpacing: "0.2em", color: "var(--pq-muted)" }}
            >
              Note <span className="normal-case italic" style={{ letterSpacing: 0 }}>(optional)</span>
            </label>
            <textarea
              value={note}
              onChange={(e) => setNote(e.target.value)}
              rows={3}
              placeholder="Why this symbol? What to observe?"
              className="mt-2 w-full resize-none rounded-md bg-transparent px-3 py-2 text-sm outline-none"
              style={{
                border: "0.5px solid var(--pq-hairline)",
                color: "var(--pq-ink)",
                fontFamily: "var(--font-serif), serif",
              }}
            />
            <p
              className="mt-1 text-[11px] italic"
              style={{ fontFamily: "var(--font-serif), serif", color: "var(--pq-muted)" }}
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
