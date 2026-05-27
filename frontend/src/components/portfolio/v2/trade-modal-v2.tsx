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
 * Two modes for buy/sell (2026-05-22, CEO decision) — mirrors
 * <AddPositionModalV2 />'s holding/new split. A toggle at the top of the form:
 *   - "이미 체결됨 · 기록만" (RECORD, default): the trade already happened —
 *     the user is journaling a past fill (like an asset sync). The 7-question
 *     reflection is inappropriate (the decision is done), so this mode SKIPS
 *     the friction and calls commitTrade() directly on submit. Thesis (note)
 *     is OPTIONAL — empty is allowed.
 *   - "신규 검토 · 7문항" (REVIEW): the original flow — "should I buy/sell
 *     right now?". Submitting hands off to <PreTradeFrictionModal /> (buy=ENTRY
 *     / sell=EXIT) — the 7-question reflection. The real POST fires only on its
 *     onProceed; Cancel writes nothing. Thesis REQUIRED at ≥MIN_RATIONALE_CHARS.
 * `edit` (avg-cost/memo adjustment) is NOT a buy/sell event and has NO mode —
 * it commits directly via PATCH without friction (unchanged).
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
import { displayTicker, isKrTicker, normalizeTicker } from "@/lib/format";
import { useFocusTrap } from "@/lib/useFocusTrap";
import type { Position, TradeAction } from "@/components/portfolio/types";
import { PreTradeFrictionModal } from "@/components/pre-trade/pre-trade-friction-modal";
import { MIN_RATIONALE_CHARS } from "@/components/pre-trade/pre-trade-friction-core";

interface TradeModalV2Props {
  open: boolean;
  onClose: () => void;
  action: TradeAction;
  position: Position | null;
  onSuccess?: () => void;
}

/** Trade mode (buy/sell only) — recording an already-filled trade vs.
 *  reflecting on a fresh decision. Mirrors AddPositionModalV2's EntryMode. */
type TradeMode = "record" | "review";

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

/** Mode-specific copy for buy/sell. RECORD reads as journaling a done trade;
 *  REVIEW reads as the original "reflect before deciding" flow. `edit` ignores
 *  this and uses COPY.edit directly. */
function modeCopy(action: TradeAction, mode: TradeMode): CopyEntry {
  const base = COPY[action];
  const isBuy = action === "buy";
  if (mode === "record") {
    return {
      ...base,
      eyebrow: isBuy ? "Record · Add" : "Record · Trim",
      headline: isBuy ? "Log an" : "Log a",
      accentWord: isBuy ? "executed buy." : "executed sell.",
      cta: "Record · 기록",
      helper: isBuy
        ? "이미 체결한 추가 매수를 책에 기록합니다. 질문 없이 바로 저장."
        : "이미 체결한 매도를 책에 기록합니다. 질문 없이 바로 저장.",
    };
  }
  // review
  return {
    ...base,
    eyebrow: isBuy ? "Observation · Add" : "Observation · Trim",
    headline: isBuy ? "Add to" : "Trim",
    accentWord: "this position.",
    cta: "Continue · 7 questions →",
    helper: isBuy
      ? "지금 추가 매수할지 검토합니다. 7개 질문을 거친 뒤 기록됩니다."
      : "지금 매도할지 검토합니다. 7개 질문을 거친 뒤 기록됩니다.",
  };
}

export function TradeModalV2({
  open,
  onClose,
  action,
  position,
  onSuccess,
}: TradeModalV2Props) {
  const headlineId = "trade-v2-headline";
  const trapRef = useFocusTrap<HTMLDivElement>(open);

  // buy/sell carry a mode (record/review); edit has none. RECORD is default.
  const [mode, setMode] = React.useState<TradeMode>("record");

  const [shares, setShares] = React.useState("");
  const [price, setPrice] = React.useState("");
  const [date, setDate] = React.useState(() =>
    new Date().toISOString().slice(0, 10),
  );
  const [avgCost, setAvgCost] = React.useState("");
  const [note, setNote] = React.useState("");
  const [submitting, setSubmitting] = React.useState(false);
  // Inline Pre-Trade Friction — only for buy (ENTRY) / sell (EXIT) in REVIEW
  // mode. Edit commits directly; RECORD mode skips friction.
  const [frictionOpen, setFrictionOpen] = React.useState(false);

  // Mode-aware copy for buy/sell; edit always uses its static entry.
  const copy = action === "edit" ? COPY.edit : modeCopy(action, mode);

  // Thesis is required only for buy/sell in REVIEW mode (the reflection needs
  // ≥MIN_RATIONALE_CHARS). edit and RECORD mode treat the note as an optional memo.
  const requiresThesis = action !== "edit" && mode === "review";
  const noteOk = !requiresThesis || note.trim().length >= MIN_RATIONALE_CHARS;
  const noteRemaining = Math.max(0, MIN_RATIONALE_CHARS - note.trim().length);

  // Reset form whenever position/action changes or close
  React.useEffect(() => {
    if (!open) {
      setMode("record");
      setFrictionOpen(false);
      return;
    }
    // Mode resets to default whenever the modal opens or action changes.
    setMode("record");
    setFrictionOpen(false);
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

  // Escape closes — only when the friction modal is NOT open.
  React.useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !frictionOpen) onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, onClose, frictionOpen]);

  if (!open || !position) return null;

  // Validate the form. For edit → commit immediately. For buy/sell → open
  // the reflection (real write happens on its onProceed).
  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!position || submitting || frictionOpen) return;

    if (action === "edit") {
      const parsedCost = Number(avgCost);
      if (!Number.isFinite(parsedCost) || parsedCost <= 0) {
        toast.error("Average cost must be positive.");
        return;
      }
      setSubmitting(true);
      try {
        await apiFetch(`${PORTFOLIO_POSITIONS}/${position.id}`, {
          method: "PATCH",
          body: JSON.stringify({ avg_cost: parsedCost, note: note.trim() }),
        });
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
      return;
    }

    // buy / sell — validate then either record directly (RECORD) or hand to
    // the reflection (REVIEW). Quantity/price/over-trim guards apply to BOTH.
    const parsedQty = Number(shares);
    const parsedPrice = Number(price);
    if (!Number.isFinite(parsedQty) || parsedQty <= 0) {
      toast.error("Shares must be a positive number.");
      return;
    }
    if (!Number.isFinite(parsedPrice) || parsedPrice <= 0) {
      toast.error("Price must be positive.");
      return;
    }
    if (action === "sell" && parsedQty > position.shares) {
      toast.error(`Cannot trim more than ${position.shares} shares held.`);
      return;
    }

    if (mode === "review") {
      // REVIEW: thesis required ≥MIN_RATIONALE_CHARS; hand off to the 7-question
      // reflection. Nothing is written until the modal calls onProceed.
      if (!noteOk) {
        toast.error(`Thesis는 ${MIN_RATIONALE_CHARS}자 이상 적어주세요 (현재 ${note.trim().length}자).`);
        return;
      }
      setFrictionOpen(true);
      return;
    }

    // RECORD: the trade already happened — skip the reflection and write it.
    void commitTrade();
  }

  // Commit the real buy/sell trade. Two callers:
  //   - RECORD mode: directly from handleSubmit (no friction).
  //   - REVIEW mode: from the friction modal's onProceed.
  async function commitTrade() {
    if (!position) return;
    const parsedQty = Number(shares);
    const parsedPrice = Number(price);
    setSubmitting(true);
    try {
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
      toast.success(copy.toast);
      onSuccess?.();
      // RECORD mode owns its own close (no friction modal to do it).
      if (mode === "record") {
        onClose();
      }
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        if (typeof window !== "undefined") window.location.href = "/login";
        return;
      }
      const message =
        err instanceof Error ? err.message : "Failed to record entry.";
      if (mode === "record") {
        // No friction modal to surface the error — toast here.
        toast.error(message);
        return;
      }
      // REVIEW: re-throw so the friction modal surfaces it (reflection already
      // stamped; the journal write is what failed).
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
        {/* Hero */}
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
            {copy.eyebrow}
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
            {copy.headline}{" "}
            <span style={{ color: "var(--pq-bronze)" }}>
              {copy.accentWord}
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
            <span style={{ color: "var(--pq-ivory)", fontWeight: 500 }}>
              {displayTicker(position.symbol, position.name)}
            </span>{" "}
            <span
              className="font-mono"
              style={{
                fontSize: "var(--pq-text-eyebrow)",
                color: "rgba(245,240,232,0.55)",
                letterSpacing: "0.16em",
              }}
            >
              {normalizeTicker(position.symbol)}
            </span>{" "}
            · {copy.helper}
          </p>
        </div>

        {/* Mode toggle — buy/sell only. edit has no mode concept. */}
        {action !== "edit" && (
          <div
            role="radiogroup"
            aria-label="기록 방식"
            style={{ display: "flex", gap: 8, marginBottom: 28 }}
          >
            <ModeToggleButton
              active={mode === "record"}
              label="이미 체결됨 · 기록만"
              onClick={() => setMode("record")}
            />
            <ModeToggleButton
              active={mode === "review"}
              label="신규 검토 · 7문항"
              onClick={() => setMode("review")}
            />
          </div>
        )}

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
                <FormField
                  label={`Price (per share) ${
                    (position.currency ?? (isKrTicker(position.symbol) ? "KRW" : "USD")) === "KRW"
                      ? "(KRW)"
                      : "(USD)"
                  }`}
                >
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
                  style={{ ...fieldInputStyle, colorScheme: "dark" }}
                />
              </FormField>
              {mode === "review" ? (
                <FormField label={`Thesis · 한 문단 (${MIN_RATIONALE_CHARS}자 이상)`}>
                  <textarea
                    required
                    value={note}
                    onChange={(e) => setNote(e.target.value)}
                    rows={3}
                    placeholder="왜 지금 이 결정을 하는가? 한 문단으로 정직하게."
                    style={{ ...fieldInputStyle, resize: "vertical", minHeight: 56 }}
                  />
                  <span
                    className="font-mono"
                    style={{
                      fontSize: "var(--pq-text-eyebrow)",
                      letterSpacing: "0.06em",
                      color: noteOk ? "var(--pq-bronze)" : "rgba(245,240,232,0.45)",
                      marginTop: 2,
                    }}
                  >
                    {noteOk
                      ? `✓ ${note.trim().length} chars`
                      : `${noteRemaining} chars more (${note.trim().length}/${MIN_RATIONALE_CHARS})`}
                  </span>
                </FormField>
              ) : (
                <FormField label="메모 · 언제·왜 거래했나 (선택)">
                  <textarea
                    value={note}
                    onChange={(e) => setNote(e.target.value)}
                    rows={3}
                    placeholder="언제, 왜 체결했는지 한 줄로 — 비워도 됩니다."
                    style={{ ...fieldInputStyle, resize: "vertical", minHeight: 56 }}
                  />
                </FormField>
              )}
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
                {submitting ? "Saving…" : copy.cta}
              </button>
            </div>
          </div>
        </form>
      </div>

      {/* Inline Pre-Trade Friction — buy=ENTRY, sell=EXIT. Real POST on
          onProceed; Cancel writes nothing. (edit never opens this.) */}
      <PreTradeFrictionModal
        open={frictionOpen}
        side={action === "buy" ? "ENTRY" : "EXIT"}
        ticker={position.symbol}
        tickerName={position.name}
        shares={shares}
        rationale={note}
        onProceed={async () => {
          await commitTrade();
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
  fontSize: "var(--pq-text-body)",
  letterSpacing: "0.01em",
};

function ModeToggleButton({
  active,
  label,
  onClick,
}: {
  active: boolean;
  label: string;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      role="radio"
      aria-checked={active}
      onClick={onClick}
      className="font-mono uppercase"
      style={{
        flex: 1,
        padding: "9px 12px",
        background: active ? "rgba(184,149,106,0.12)" : "transparent",
        color: active ? "var(--pq-bronze)" : "rgba(245,240,232,0.55)",
        border: `1px solid ${active ? "var(--pq-bronze)" : "rgba(245,240,232,0.12)"}`,
        borderRadius: "var(--pq-radius-cta, 2px)",
        fontSize: "var(--pq-text-eyebrow)",
        letterSpacing: "0.14em",
        cursor: "pointer",
        transition: "all 160ms",
      }}
    >
      {label}
    </button>
  );
}

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

export default TradeModalV2;
