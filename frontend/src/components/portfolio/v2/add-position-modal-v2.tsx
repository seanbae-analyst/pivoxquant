"use client";

/**
 * <AddPositionModalV2 /> — CRITICAL bug fix half of /portfolio v2.
 *
 * Mockup §BLOCK 4 / SPEC §5. Editorial dialog with:
 *   - Eyebrow + Playfair display-h2 headline
 *   - Form fields with mono labels + hairline-bottom inputs
 *   - "Save observation" CTA (legal-safe vocabulary)
 *
 * Backend contract (verified 2026-04-27):
 *   POST PORTFOLIO_POSITIONS = `/api/portfolio/positions`
 *   payload: {symbol, side: "Long", quantity, price, purchase_date, note}
 *   (matches existing add-position-modal.tsx contract, untouched)
 *
 * A11y: role=dialog, aria-modal, focus trap via useFocusTrap, Escape closes.
 */

import * as React from "react";
import { toast } from "sonner";
import { PORTFOLIO_POSITIONS } from "@/lib/endpoints";
import { apiFetch, ApiError } from "@/lib/api";
import { useFocusTrap } from "@/lib/useFocusTrap";

interface AddPositionModalV2Props {
  open: boolean;
  onClose: () => void;
  onSuccess?: () => void;
}

const SECTOR_OPTIONS = [
  "Technology",
  "Communication",
  "Consumer",
  "Healthcare",
  "Financials",
  "Industrials",
  "Energy",
  "Materials",
  "Utilities",
  "Real Estate",
  "Other",
];

export function AddPositionModalV2({
  open,
  onClose,
  onSuccess,
}: AddPositionModalV2Props) {
  const headlineId = "add-pos-v2-headline";
  const trapRef = useFocusTrap<HTMLDivElement>(open);

  const [symbol, setSymbol] = React.useState("");
  const [shares, setShares] = React.useState("");
  const [avgCost, setAvgCost] = React.useState("");
  const [acquiredAt, setAcquiredAt] = React.useState(() =>
    new Date().toISOString().slice(0, 10),
  );
  const [currency, setCurrency] = React.useState<"USD" | "KRW">("USD");
  const [sector, setSector] = React.useState("Technology");
  const [memo, setMemo] = React.useState("");
  const [submitting, setSubmitting] = React.useState(false);

  // Reset on close
  React.useEffect(() => {
    if (!open) {
      setSymbol("");
      setShares("");
      setAvgCost("");
      setAcquiredAt(new Date().toISOString().slice(0, 10));
      setCurrency("USD");
      setSector("Technology");
      setMemo("");
      setSubmitting(false);
    }
  }, [open]);

  // Escape closes
  React.useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (submitting) return;

    const sym = symbol.trim().toUpperCase();
    const sharesN = Number(shares);
    const costN = Number(avgCost);
    if (!sym) {
      toast.error("Symbol is required.");
      return;
    }
    if (!Number.isFinite(sharesN) || sharesN <= 0) {
      toast.error("Shares must be a positive number.");
      return;
    }
    if (!Number.isFinite(costN) || costN <= 0) {
      toast.error("Average cost must be positive.");
      return;
    }

    setSubmitting(true);
    try {
      await apiFetch(PORTFOLIO_POSITIONS, {
        method: "POST",
        body: JSON.stringify({
          symbol: sym,
          side: "Long",
          quantity: sharesN,
          price: costN,
          purchase_date: acquiredAt,
          sector,
          currency,
          note: memo.trim(),
        }),
      });
      toast.success("Position recorded · informational only, not advice.");
      onSuccess?.();
      onClose();
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        if (typeof window !== "undefined") window.location.href = "/login";
        return;
      }
      const message =
        err instanceof Error ? err.message : "Failed to record position.";
      toast.error(message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby={headlineId}
      className="pq-modal-v2"
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 1000,
        background: "rgba(5,5,5,0.78)",
        backdropFilter: "blur(8px)",
        WebkitBackdropFilter: "blur(8px)",
        display: "flex",
        alignItems: "flex-start",
        justifyContent: "center",
        padding: "10vh 24px 24px",
        overflowY: "auto",
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        ref={trapRef}
        style={{
          width: "100%",
          maxWidth: 560,
          background: "rgba(184,149,106,0.025)",
          border: "1px solid var(--pq-hairline-ink, rgba(245,240,232,0.08))",
          borderRadius: "var(--pq-radius-card, 4px)",
          padding: "40px 36px",
          color: "var(--pq-ivory)",
        }}
      >
        {/* Hero block */}
        <div style={{ marginBottom: 28 }}>
          <div
            className="font-mono uppercase"
            style={{
              fontFamily:
                '"JetBrains Mono","SF Mono",ui-monospace,monospace',
              fontSize: 10.5,
              letterSpacing: "0.22em",
              color: "var(--pq-bronze)",
              marginBottom: 14,
            }}
          >
            Observation · New entry
          </div>
          <h2
            id={headlineId}
            className="font-serif"
            style={{
              fontFamily:
                '"Playfair Display","Source Serif 4",Georgia,serif',
              fontWeight: 500,
              fontSize: 30,
              lineHeight: 1.15,
              letterSpacing: "-0.02em",
              color: "var(--pq-ivory)",
              margin: "0 0 12px 0",
            }}
          >
            Record a{" "}
            <span style={{ fontStyle: "italic", color: "var(--pq-bronze)" }}>
              new position.
            </span>
          </h2>
          <p
            className="font-serif"
            style={{
              fontFamily: '"Source Serif 4",Georgia,serif',
              fontSize: 14,
              lineHeight: 1.5,
              color: "rgba(245,240,232,0.65)",
              margin: 0,
            }}
          >
            Saved to your book · not sent to broker. Journaling only.
          </p>
        </div>

        <form
          onSubmit={handleSubmit}
          style={{ display: "flex", flexDirection: "column", gap: 20 }}
        >
          {/* Symbol — full row */}
          <FormField label="Symbol">
            <input
              required
              value={symbol}
              onChange={(e) => setSymbol(e.target.value.toUpperCase())}
              placeholder="AAPL · 005930"
              style={fieldInputStyle}
            />
          </FormField>

          {/* Row 1: Shares + Avg cost */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20 }}>
            <FormField label="Shares">
              <input
                required
                type="number"
                step="any"
                min="0"
                value={shares}
                onChange={(e) => setShares(e.target.value)}
                placeholder="0"
                style={fieldInputStyle}
              />
            </FormField>
            <FormField label="Avg cost">
              <input
                required
                type="number"
                step="any"
                min="0"
                value={avgCost}
                onChange={(e) => setAvgCost(e.target.value)}
                placeholder="0.00"
                style={fieldInputStyle}
              />
            </FormField>
          </div>

          {/* Row 2: Date + Currency */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20 }}>
            <FormField label="Acquired on">
              <input
                required
                type="date"
                value={acquiredAt}
                onChange={(e) => setAcquiredAt(e.target.value)}
                style={fieldInputStyle}
              />
            </FormField>
            <FormField label="Currency">
              <select
                value={currency}
                onChange={(e) => setCurrency(e.target.value as "USD" | "KRW")}
                style={fieldInputStyle}
              >
                <option value="USD">USD · $</option>
                <option value="KRW">KRW · ₩</option>
              </select>
            </FormField>
          </div>

          {/* Sector */}
          <FormField label="Sector">
            <select
              value={sector}
              onChange={(e) => setSector(e.target.value)}
              style={fieldInputStyle}
            >
              {SECTOR_OPTIONS.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </FormField>

          {/* Memo */}
          <FormField label="Memo (optional)">
            <textarea
              value={memo}
              onChange={(e) => setMemo(e.target.value)}
              rows={2}
              placeholder="Why now?"
              style={{ ...fieldInputStyle, resize: "vertical", minHeight: 36 }}
            />
          </FormField>

          {/* Footer */}
          <div
            style={{
              marginTop: 12,
              paddingTop: 20,
              borderTop:
                "1px solid var(--pq-hairline-ink, rgba(245,240,232,0.08))",
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              gap: 12,
              flexWrap: "wrap",
            }}
          >
            <span
              className="font-mono uppercase"
              style={{
                fontFamily:
                  '"JetBrains Mono","SF Mono",ui-monospace,monospace',
                fontSize: 9.5,
                letterSpacing: "0.22em",
                color: "rgba(245,240,232,0.40)",
              }}
            >
              Saved to your book · not sent to broker
            </span>
            <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
              <button
                type="button"
                onClick={onClose}
                className="font-mono uppercase"
                style={{
                  background: "transparent",
                  border: "none",
                  color: "rgba(245,240,232,0.55)",
                  fontFamily:
                    '"JetBrains Mono","SF Mono",ui-monospace,monospace',
                  fontSize: 10.5,
                  letterSpacing: "0.2em",
                  cursor: "pointer",
                  padding: 4,
                }}
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={submitting}
                className="font-mono uppercase"
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 8,
                  padding: "10px 20px",
                  background: submitting
                    ? "rgba(184,149,106,0.5)"
                    : "var(--pq-bronze)",
                  color: "var(--pq-ink, #050505)",
                  border: "none",
                  borderRadius: "var(--pq-radius-cta, 2px)",
                  fontFamily:
                    '"JetBrains Mono","SF Mono",ui-monospace,monospace',
                  fontSize: 11,
                  letterSpacing: "0.2em",
                  cursor: submitting ? "not-allowed" : "pointer",
                }}
              >
                {submitting ? "Saving…" : "Save observation →"}
              </button>
            </div>
          </div>
        </form>
      </div>
    </div>
  );
}

const fieldInputStyle: React.CSSProperties = {
  width: "100%",
  padding: "8px 0",
  background: "transparent",
  border: "none",
  borderBottom: "1px solid var(--pq-hairline-ink, rgba(245,240,232,0.16))",
  outline: "none",
  color: "var(--pq-ivory)",
  fontFamily: '"JetBrains Mono","SF Mono",ui-monospace,monospace',
  fontSize: 14,
  letterSpacing: "0.01em",
};

function FormField({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <label
      style={{
        display: "flex",
        flexDirection: "column",
        gap: 6,
      }}
    >
      <span
        className="font-mono uppercase"
        style={{
          fontFamily: '"JetBrains Mono","SF Mono",ui-monospace,monospace',
          fontSize: 9.5,
          letterSpacing: "0.22em",
          color: "var(--pq-bronze)",
        }}
      >
        {label}
      </span>
      {children}
    </label>
  );
}

export default AddPositionModalV2;
