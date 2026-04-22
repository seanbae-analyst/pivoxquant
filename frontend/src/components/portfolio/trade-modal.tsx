"use client";

import { useState, type FormEvent } from "react";
import {
  PortfolioModal,
  Field,
  inputClass,
  CancelButton,
  PrimaryButton,
} from "./portfolio-modal";
import type { Position, TradeAction } from "./types";

interface TradeModalProps {
  open: boolean;
  onClose: () => void;
  action: TradeAction;
  position: Position | null;
  onSubmit?: (payload: {
    action: TradeAction;
    positionId: string;
    quantity: number;
    price: number;
    date: string;
    notes: string;
  }) => void;
}

const COPY: Record<
  TradeAction,
  { title: string; subtitle: string; cta: string }
> = {
  buy: {
    title: "Add to Position",
    subtitle: "Record an additional purchase of this symbol.",
    cta: "Save",
  },
  sell: {
    title: "Reduce Position",
    subtitle: "Record a partial or full close of this holding.",
    cta: "Save",
  },
  edit: {
    title: "Edit Position",
    subtitle: "Adjust the cost basis or notes for this holding.",
    cta: "Update",
  },
};

export function TradeModal({
  open,
  onClose,
  action,
  position,
  onSubmit,
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

  // When the target position changes, sync local state.
  // (Simple approach — parent remounts via key when needed.)
  if (position && action === "edit" && avgCost === "" && position.avgCost) {
    setAvgCost(String(position.avgCost));
  }

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!position) return;
    const payload = {
      action,
      positionId: position.id,
      quantity: Number(quantity) || 0,
      price: Number(price) || Number(avgCost) || 0,
      date,
      notes: notes.trim(),
    };
    // eslint-disable-next-line no-console
    console.log("[PortfolioRecord] trade", payload);
    onSubmit?.(payload);
    onClose();
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
            {copy.cta}
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
                  className={inputClass + " bg-slate-50 text-slate-500"}
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
      </form>
    </PortfolioModal>
  );
}
