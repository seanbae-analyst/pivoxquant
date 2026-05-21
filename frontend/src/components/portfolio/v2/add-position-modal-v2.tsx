"use client";

/**
 * <AddPositionModalV2 /> — CRITICAL bug fix half of /portfolio v2.
 *
 * Mockup §BLOCK 4 / SPEC §5. Editorial dialog with:
 *   - Eyebrow + Playfair display-h2 headline
 *   - Form fields with mono labels + hairline-bottom inputs
 *   - "Save observation" CTA (legal-safe vocabulary)
 *
 * Pre-Trade Friction (Feature 6) — INLINE at the moment of action
 * (2026-05-21): submitting this form no longer writes the position
 * directly. It hands the entry to <PreTradeFrictionModal /> (ENTRY) — the
 * 7-question reflection + cooldown. The real `POST /api/portfolio/positions`
 * fires only on `onProceed`. Cancel → nothing is recorded. The friction is
 * the point; it must live where the action happens, not on a page no one
 * visits. The thesis (memo) is therefore REQUIRED at ≥50 chars (matches the
 * reflection's MIN_RATIONALE_CHARS) and prefills the reflection.
 *
 * Backend contract (re-verified 2026-05-01 against routes/portfolio.py
 * ::create_position_alias):
 *   POST PORTFOLIO_POSITIONS = `/api/portfolio/positions`
 *   payload: {symbol, quantity, price, note}
 *   The Position model has no `side` / `purchase_date` / `sector` /
 *   `currency` columns, so collecting those fields in the form was
 *   silently dropping user input. Mirrors V1 modal trim (commit
 *   1ee4786) so V2 stops lying to the user about what gets saved.
 *
 * A11y: role=dialog, aria-modal, focus trap via useFocusTrap, Escape closes.
 */

import * as React from "react";
import { toast } from "sonner";
import { PORTFOLIO_POSITIONS } from "@/lib/endpoints";
import { apiFetch, ApiError } from "@/lib/api";
import { useFocusTrap } from "@/lib/useFocusTrap";
import { PreTradeFrictionModal } from "@/components/pre-trade/pre-trade-friction-modal";
import { MIN_RATIONALE_CHARS } from "@/components/pre-trade/pre-trade-friction-core";

interface AddPositionModalV2Props {
  open: boolean;
  onClose: () => void;
  onSuccess?: () => void;
}

// SECTOR_OPTIONS removed 2026-05-01 — sector is resolved server-side via
// SignalCache (kr_stock_registry / FMP profile) and is NOT a Position
// model column. User-picked sector was being dropped by the backend.

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
  const [memo, setMemo] = React.useState("");
  const [submitting, setSubmitting] = React.useState(false);
  // Inline Pre-Trade Friction (ENTRY) — opened after the form validates;
  // the real POST fires only on its onProceed.
  const [frictionOpen, setFrictionOpen] = React.useState(false);

  const memoOk = memo.trim().length >= MIN_RATIONALE_CHARS;
  const memoRemaining = Math.max(0, MIN_RATIONALE_CHARS - memo.trim().length);

  // Reset on close
  React.useEffect(() => {
    if (!open) {
      setSymbol("");
      setShares("");
      setAvgCost("");
      setMemo("");
      setSubmitting(false);
      setFrictionOpen(false);
    }
  }, [open]);

  // Escape closes — only when the friction modal is NOT open (it owns Escape
  // during its own lifecycle).
  React.useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !frictionOpen) onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, onClose, frictionOpen]);

  if (!open) return null;

  const sym = symbol.trim().toUpperCase();
  const sharesN = Number(shares);
  const costN = Number(avgCost);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (submitting || frictionOpen) return;

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
    if (!memoOk) {
      toast.error(`Thesis는 ${MIN_RATIONALE_CHARS}자 이상 적어주세요 (현재 ${memo.trim().length}자).`);
      return;
    }

    // Hand off to the 7-question reflection + cooldown. Nothing is written
    // until the user clears the friction and the modal calls onProceed.
    setFrictionOpen(true);
  }

  // Commit the real position — invoked by the friction modal's onProceed.
  // Backend `routes/portfolio.py::create_position_alias` reads only
  // {symbol, quantity, price, note}. side / purchase_date / sector /
  // currency have no Position-model column (mirrors V1 trim commit 1ee4786).
  async function commitPosition() {
    setSubmitting(true);
    try {
      await apiFetch(PORTFOLIO_POSITIONS, {
        method: "POST",
        body: JSON.stringify({
          symbol: sym,
          quantity: sharesN,
          price: costN,
          note: memo.trim(),
        }),
      });
      toast.success("Position recorded · informational only, not advice.");
      onSuccess?.();
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        if (typeof window !== "undefined") window.location.href = "/login";
        return;
      }
      const message =
        err instanceof Error ? err.message : "Failed to record position.";
      // Re-throw so the friction modal surfaces it (the reflection is
      // already stamped; the journal write is what failed).
      throw new Error(message);
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
        {/* Hero block */}
        <div style={{ marginBottom: 28 }}>
          <div
            className="font-mono uppercase"
            style={{
              fontSize: "var(--pq-text-eyebrow)",
              letterSpacing: "0.22em",
              color: "var(--pq-bronze)",
              marginBottom: 14,
            }}
          >
            Observation · New entry
          </div>
          <h2
            id={headlineId}
            className="font-display"
            style={{
              fontWeight: 500,
              fontSize: "var(--pq-text-h3)",
              lineHeight: 1.15,
              letterSpacing: "-0.02em",
              color: "var(--pq-ivory)",
              margin: "0 0 12px 0",
            }}
          >
            Record a{" "}
            <span style={{ color: "var(--pq-bronze)" }}>
              new position.
            </span>
          </h2>
          <p
            className="font-serif"
            style={{
              fontSize: "var(--pq-text-body)",
              lineHeight: 1.5,
              color: "rgba(245,240,232,0.65)",
              margin: 0,
            }}
          >
            Saved to your book · not sent to broker. Journaling only — 7개
            질문을 거친 뒤 기록됩니다.
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
              placeholder="AAPL · 005930.KS"
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

          {/* Thesis — required ≥50 chars; prefills the reflection. */}
          <FormField label={`Thesis · 한 문단 (${MIN_RATIONALE_CHARS}자 이상)`}>
            <textarea
              required
              value={memo}
              onChange={(e) => setMemo(e.target.value)}
              rows={3}
              placeholder="왜 지금 이 종목에 들어가는가? 한 문단으로 정직하게."
              style={{ ...fieldInputStyle, resize: "vertical", minHeight: 56 }}
            />
            <span
              className="font-mono"
              style={{
                fontSize: "var(--pq-text-eyebrow)",
                letterSpacing: "0.06em",
                color: memoOk ? "var(--pq-bronze)" : "rgba(245,240,232,0.45)",
                marginTop: 2,
              }}
            >
              {memoOk
                ? `✓ ${memo.trim().length} chars`
                : `${memoRemaining} chars more (${memo.trim().length}/${MIN_RATIONALE_CHARS})`}
            </span>
          </FormField>

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
                fontSize: "var(--pq-text-eyebrow)",
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
                  fontSize: "var(--pq-text-eyebrow)",
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
                  fontSize: "var(--pq-text-eyebrow)",
                  letterSpacing: "0.2em",
                  cursor: submitting ? "not-allowed" : "pointer",
                }}
              >
                {submitting ? "Saving…" : "Continue · 7 questions →"}
              </button>
            </div>
          </div>
        </form>
      </div>

      {/* Inline Pre-Trade Friction (ENTRY). The real POST fires on onProceed.
          On cancel, nothing is written and we return to this form. */}
      <PreTradeFrictionModal
        open={frictionOpen}
        side="ENTRY"
        ticker={sym}
        shares={shares}
        rationale={memo}
        onProceed={async () => {
          await commitPosition();
          // Position committed — close both modals.
          setFrictionOpen(false);
          onClose();
        }}
        onCancel={() => setFrictionOpen(false)}
        onClose={() => setFrictionOpen(false)}
      />
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
  // 16px to prevent iOS Safari/Chrome auto-zoom on input focus
  fontSize: "var(--pq-text-h6)",
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
          fontSize: "var(--pq-text-eyebrow)",
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
