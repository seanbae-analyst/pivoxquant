"use client";

import { useState, type FormEvent } from "react";
import { toast } from "sonner";
import {
  PortfolioModal,
  Field,
  inputClass,
  CancelButton,
  PrimaryButton,
} from "./portfolio-modal";
import type { Position, TradeAction } from "./types";
import { PORTFOLIO_POSITIONS, PORTFOLIO_TRADES } from "@/lib/endpoints";
import { apiFetch, ApiError } from "@/lib/api";

interface TradeModalProps {
  open: boolean;
  onClose: () => void;
  action: TradeAction;
  position: Position | null;
  onSuccess?: () => void;
}

const COPY: Record<
  TradeAction,
  { title: string; subtitle: string; cta: string; success: string }
> = {
  buy: {
    title: "Add to Position",
    subtitle: "Record an additional purchase of this symbol.",
    cta: "Save",
    success: "Trade recorded — informational only, not advice.",
  },
  sell: {
    title: "Reduce Position",
    subtitle: "Record a partial or full close of this holding.",
    cta: "Save",
    success: "Trade recorded — informational only, not advice.",
  },
  edit: {
    title: "Edit Position",
    subtitle: "Adjust the cost basis or notes for this holding.",
    cta: "Update",
    success: "Position updated.",
  },
};

export function TradeModal({
  open,
  onClose,
  action,
  position,
  onSuccess,
}: TradeModalProps) {
  const copy = COPY[action];

  const [quantity, setQuantity] = useState("");
  const [price, setPrice] = useState(() =>
    position?.current ? String(position.current) : "",
  );
  const [date, setDate] = useState(() =>
    new Date().toISOString().slice(0, 10),
  );
  const [notes, setNotes] = useState(position?.notes ?? "");
  const [avgCost, setAvgCost] = useState(
    position?.avgCost ? String(position.avgCost) : "",
  );
  const [submitting, setSubmitting] = useState(false);

  if (position && action === "edit" && avgCost === "" && position.avgCost) {
    setAvgCost(String(position.avgCost));
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!position || submitting) return;
    setSubmitting(true);

    try {
      if (action === "edit") {
        const parsedCost = Number(avgCost) || 0;
        if (parsedCost <= 0) {
          toast.error("Average cost must be positive.");
          setSubmitting(false);
          return;
        }
        await apiFetch(`${PORTFOLIO_POSITIONS}/${position.id}`, {
          method: "PATCH",
          body: JSON.stringify({
            avg_cost: parsedCost,
            note: notes.trim(),
          }),
        });
        toast.success(copy.success);
      } else {
        const parsedQty = Number(quantity) || 0;
        const parsedPrice = Number(price) || 0;
        if (parsedQty <= 0 || parsedPrice <= 0) {
          toast.error("Quantity and price required.");
          setSubmitting(false);
          return;
        }
        if (action === "sell" && parsedQty > position.shares) {
          toast.error(`Cannot sell more than ${position.shares} shares held.`);
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
            note: notes.trim(),
          }),
        });
        toast.success(copy.success);
      }
      onSuccess?.();
      onClose();
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        if (typeof window !== "undefined") window.location.href = "/login";
        return;
      }
      const message =
        err instanceof Error ? err.message : "Failed to record trade";
      toast.error(message);
    } finally {
      setSubmitting(false);
    }
  }

  if (!position) return null;

  const maxShares = position.shares;

  return (
    <PortfolioModal
      open={open}
      onClose={onClose}
      title={copy.title}
      subtitle={`${position.symbol} · ${position.name}  ·  ${copy.subtitle}`}
      footer={
        <>
          <CancelButton onClick={onClose} />
          <PrimaryButton
            type="button"
            onClick={() => {
              const form = document.getElementById(
                "trade-form",
              ) as HTMLFormElement | null;
              form?.requestSubmit();
            }}
          >
            {submitting ? "Saving…" : copy.cta}
          </PrimaryButton>
        </>
      }
    >
      <form
        id="trade-form"
        onSubmit={handleSubmit}
        className="grid grid-cols-2 gap-x-4 gap-y-4 pb-6"
      >
        {action === "edit" ? (
          <>
            <div className="col-span-2 sm:col-span-1">
              <Field label="Average Cost">
                <input
                  required
                  type="number"
                  min="0"
                  step="any"
                  className={inputClass}
                  value={avgCost}
                  onChange={(e) => setAvgCost(e.target.value)}
                />
              </Field>
            </div>
            <div className="col-span-2 sm:col-span-1">
              <Field label="Shares">
                <input
                  readOnly
                  className={inputClass + " bg-[var(--pq-ivory-line-faint)] text-[rgba(245,240,232,0.55)]"}
                  value={position.shares}
                />
              </Field>
            </div>
          </>
        ) : (
          <>
            <div className="col-span-2 sm:col-span-1">
              <Field
                label="Quantity"
                hint={
                  action === "sell" ? `Current shares: ${maxShares}` : undefined
                }
              >
                <input
                  required
                  type="number"
                  min="0"
                  max={action === "sell" ? maxShares : undefined}
                  step="any"
                  className={inputClass}
                  placeholder="0"
                  value={quantity}
                  onChange={(e) => setQuantity(e.target.value)}
                />
              </Field>
            </div>

            <div className="col-span-2 sm:col-span-1">
              <Field label="Price">
                <input
                  required
                  type="number"
                  min="0"
                  step="any"
                  className={inputClass}
                  placeholder="0.00"
                  value={price}
                  onChange={(e) => setPrice(e.target.value)}
                />
              </Field>
            </div>

            <div className="col-span-2 sm:col-span-1">
              <Field label="Date">
                <input
                  required
                  type="date"
                  className={inputClass}
                  style={{ colorScheme: "dark" }}
                  value={date}
                  onChange={(e) => setDate(e.target.value)}
                />
              </Field>
            </div>
          </>
        )}

        <div className="col-span-2">
          <Field label="Note">
            <textarea
              rows={3}
              className={inputClass + " h-auto py-2 resize-none"}
              placeholder="Optional context for your own records."
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
            />
          </Field>
        </div>

        <p className="col-span-2 text-[11px] text-[rgba(245,240,232,0.5)]">
          User-entered record only. Not investment advice.
        </p>
      </form>
    </PortfolioModal>
  );
}
