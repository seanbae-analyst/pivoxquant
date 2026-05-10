"use client";

/**
 * <TradeModalV2 /> — Add / Trim / Close / Edit a position.
 *
 * Mockup §BLOCK 4 / SPEC §5. Same editorial dialog shell as AddPositionModalV2.
 *
 * Legal vocabulary (CEO directive 2026-04-26):
 *   buy   → "Add to position"
 *   sell  → "Trim position"  (and "Close" if qty == position.shares)
 *   edit  → "Adjust observation"
 *
 * Backend contract (verified 2026-04-27):
 *   - Add/Trim: POST PORTFOLIO_TRADES = `/api/portfolio/trades` with
 *     {position_id, action: "buy"|"sell", quantity, price, date, note}
 *   - Edit: PATCH `${PORTFOLIO_POSITIONS}/${id}` with {avg_cost, note}
 *   (matches existing trade-modal.tsx contract — endpoints unchanged.)
 */

import * as React from "react";
import { toast } from "sonner";
import { PORTFOLIO_POSITIONS, PORTFOLIO_TRADES } from "@/lib/endpoints";
import { apiFetch, ApiError } from "@/lib/api";
import { useFocusTrap } from "@/lib/useFocusTrap";
import type { Position, TradeAction } from "@/components/portfolio/types";

interface TradeModalV2Props {
  open: boolean;
  onClose: () => void;
  action: TradeAction;
  position: Position | null;
  onSuccess?: () => void;
}

interface CopyEntry {
  eyebrow: string;
  headline: string;
  accentWord: string;
  cta: string;
  toast: string;
  helper: string;
}

const COPY: Record<TradeAction, CopyEntry> = {
  buy: {
    eyebrow: "Observation · Add",
    headline: "Add to",
    accentWord: "this position.",
    cta: "Save observation →",
    toast: "Trade recorded · informational only, not advice.",
    helper: "Record an additional purchase. Saved to your book.",
  },
  sell: {
    eyebrow: "Observation · Trim",
    headline: "Trim",
    accentWord: "this position.",
    cta: "Save observation →",
    toast: "Trade recorded · informational only, not advice.",
    helper: "Record a partial or full close. Saved to your book.",
  },
  edit: {
    eyebrow: "Observation · Adjust",
    headline: "Adjust",
    accentWord: "the entry.",
    cta: "Update observation →",
    toast: "Position updated.",
    helper: "Edit the average cost or memo for this holding.",
  },
};

export function TradeModalV2({
  open,
  onClose,
  action,
  position,
  onSuccess,
}: TradeModalV2Props) {
  const headlineId = "trade-v2-headline";
  const trapRef = useFocusTrap<HTMLDivElement>(open);
  const copy = COPY[action];

  const [shares, setShares] = React.useState("");
  const [price, setPrice] = React.useState("");
  const [date, setDate] = React.useState(() =>
    new Date().toISOString().slice(0, 10),
  );
  const [avgCost, setAvgCost] = React.useState("");
  const [note, setNote] = React.useState("");
  const [submitting, setSubmitting] = React.useState(false);

  // Reset form whenever position/action changes or close
  React.useEffect(() => {
    if (!open) return;
    if (action === "edit") {
      setShares("");
      setPrice("");
      setAvgCost(position?.avgCost ? String(position.avgCost) : "");
      setNote(position?.notes ?? "");
    } else {
      setShares("");
      setPrice(position?.current ? String(position.current) : "");
      setAvgCost("");
      setNote("");
    }
    setDate(new Date().toISOString().slice(0, 10));
  }, [open, action, position]);

  // Escape closes
  React.useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open || !position) return null;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!position || submitting) return;
    setSubmitting(true);
    try {
      if (action === "edit") {
        const parsedCost = Number(avgCost);
        if (!Number.isFinite(parsedCost) || parsedCost <= 0) {
          toast.error("Average cost must be positive.");
          setSubmitting(false);
          return;
        }
        await apiFetch(`${PORTFOLIO_POSITIONS}/${position.id}`, {
          method: "PATCH",
          body: JSON.stringify({
            avg_cost: parsedCost,
            note: note.trim(),
          }),
        });
      } else {
        const parsedQty = Number(shares);
        const parsedPrice = Number(price);
        if (!Number.isFinite(parsedQty) || parsedQty <= 0) {
          toast.error("Shares must be a positive number.");
          setSubmitting(false);
          return;
        }
        if (!Number.isFinite(parsedPrice) || parsedPrice <= 0) {
          toast.error("Price must be positive.");
          setSubmitting(false);
          return;
        }
        if (action === "sell" && parsedQty > position.shares) {
          toast.error(`Cannot trim more than ${position.shares} shares held.`);
          setSubmitting(false);
          return;
        }
        await apiFetch(PORTFOLIO_TRADES, {
          method: "POST",
          body: JSON.stringify({
            position_id: position.id,
            action,
            quantity: parsedQty,
            price: parsedPrice,
            date,
            note: note.trim(),
          }),
        });
      }
      toast.success(copy.toast);
      onSuccess?.();
      onClose();
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        if (typeof window !== "undefined") window.location.href = "/login";
        return;
      }
      const message =
        err instanceof Error ? err.message : "Failed to record entry.";
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
          border: "1px solid var(--pq-hairline-ink, var(--pq-ivory-line))",
          borderRadius: "var(--pq-radius-card, 4px)",
          padding: "40px 36px",
          color: "var(--pq-ivory)",
        }}
      >
        {/* Hero */}
        <div style={{ marginBottom: 28 }}>
          <div
            className="font-mono uppercase"
            style={{
              fontSize: 12,
              letterSpacing: "0.22em",
              color: "var(--pq-bronze)",
              marginBottom: 14,
            }}
          >
            {copy.eyebrow}
          </div>
          <h2
            id={headlineId}
            className="font-display"
            style={{
              fontWeight: 500,
              fontSize: 32,
              lineHeight: 1.15,
              letterSpacing: "-0.02em",
              color: "var(--pq-ivory)",
              margin: "0 0 12px 0",
            }}
          >
            {copy.headline}{" "}
            <span style={{ fontStyle: "italic", color: "var(--pq-bronze)" }}>
              {copy.accentWord}
            </span>
          </h2>
          <p
            className="font-serif"
            style={{
              fontSize: 14,
              lineHeight: 1.5,
              color: "rgba(245,240,232,0.65)",
              margin: 0,
            }}
          >
            <span style={{ color: "var(--pq-ivory)", fontWeight: 500 }}>
              {position.name}
            </span>{" "}
            <span
              className="font-mono"
              style={{
                fontSize: 12,
                color: "rgba(245,240,232,0.55)",
                letterSpacing: "0.16em",
              }}
            >
              {position.symbol}
            </span>{" "}
            · {copy.helper}
          </p>
        </div>

        <form
          onSubmit={handleSubmit}
          style={{ display: "flex", flexDirection: "column", gap: 20 }}
        >
          {action === "edit" ? (
            <>
              <FormField label="Average cost (per share)">
                <input
                  required
                  type="number"
                  step="any"
                  min="0"
                  value={avgCost}
                  onChange={(e) => setAvgCost(e.target.value)}
                  style={fieldInputStyle}
                />
              </FormField>
              <FormField label="Memo">
                <textarea
                  value={note}
                  onChange={(e) => setNote(e.target.value)}
                  rows={2}
                  style={{ ...fieldInputStyle, resize: "vertical", minHeight: 36 }}
                />
              </FormField>
            </>
          ) : (
            <>
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "1fr 1fr",
                  gap: 20,
                }}
              >
                <FormField
                  label={action === "sell" ? `Shares (max ${position.shares})` : "Shares"}
                >
                  {/*
                    `max` HTML constraint removed (2026-04-28). Browser-level
                    validation triggered a silent block (no toast) before the
                    JS `parsedQty > position.shares` check below could fire
                    with a user-friendly toast. JS validation in handleSubmit
                    (L152-156) is the single source of truth.
                  */}
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
                <FormField label="Price (per share)">
                  <input
                    required
                    type="number"
                    step="any"
                    min="0"
                    value={price}
                    onChange={(e) => setPrice(e.target.value)}
                    placeholder="0.00"
                    style={fieldInputStyle}
                  />
                </FormField>
              </div>
              <FormField label="Date">
                <input
                  required
                  type="date"
                  value={date}
                  onChange={(e) => setDate(e.target.value)}
                  style={fieldInputStyle}
                />
              </FormField>
              <FormField label="Memo (optional)">
                <textarea
                  value={note}
                  onChange={(e) => setNote(e.target.value)}
                  rows={2}
                  placeholder="Why now?"
                  style={{ ...fieldInputStyle, resize: "vertical", minHeight: 36 }}
                />
              </FormField>
            </>
          )}

          {/* Footer */}
          <div
            style={{
              marginTop: 12,
              paddingTop: 20,
              borderTop:
                "1px solid var(--pq-hairline-ink, var(--pq-ivory-line))",
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
                fontSize: 12,
                letterSpacing: "0.22em",
                color: "rgba(245,240,232,0.55)",
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
                  fontSize: 12,
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
                  fontSize: 12,
                  letterSpacing: "0.2em",
                  cursor: submitting ? "not-allowed" : "pointer",
                }}
              >
                {submitting ? "Saving…" : copy.cta}
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
          fontSize: 12,
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

export default TradeModalV2;
