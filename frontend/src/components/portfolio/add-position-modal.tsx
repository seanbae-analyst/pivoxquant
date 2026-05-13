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
import { PORTFOLIO_POSITIONS } from "@/lib/endpoints";
import { apiFetch, ApiError } from "@/lib/api";

interface AddPositionModalProps {
  open: boolean;
  onClose: () => void;
  onSuccess?: () => void;
}

export function AddPositionModal({
  open,
  onClose,
  onSuccess,
}: AddPositionModalProps) {
  const [symbol, setSymbol] = useState("");
  const [quantity, setQuantity] = useState("");
  const [price, setPrice] = useState("");
  const [notes, setNotes] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (submitting) return;

    // Backend (routes/portfolio.py::create_position_alias) reads only
    // {symbol, quantity, price, note}. The Position model has no `side` or
    // `purchase_date` columns, so previously-collected values were silently
    // dropped — matched UI to that reality (2026-05-01).
    const payload = {
      symbol: symbol.trim().toUpperCase(),
      quantity: Number(quantity) || 0,
      price: Number(price) || 0,
      note: notes.trim(),
    };
    if (!payload.symbol || payload.quantity <= 0 || payload.price <= 0) {
      toast.error("Symbol, quantity, and price required.");
      return;
    }

    setSubmitting(true);
    try {
      await apiFetch(PORTFOLIO_POSITIONS, {
        method: "POST",
        body: JSON.stringify(payload),
      });
      toast.success("Position recorded — informational only, not advice.");
      onSuccess?.();
      reset();
      onClose();
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        if (typeof window !== "undefined") window.location.href = "/login";
        return;
      }
      const message = err instanceof Error ? err.message : "Failed to add position";
      toast.error(message);
    } finally {
      setSubmitting(false);
    }
  }

  function reset() {
    setSymbol("");
    setQuantity("");
    setPrice("");
    setNotes("");
  }

  return (
    <PortfolioModal
      open={open}
      onClose={onClose}
      title="Add Position"
      subtitle="Log a holding you already own. User-entered record only — not investment advice."
      footer={
        <>
          <CancelButton onClick={onClose} />
          <PrimaryButton
            type="button"
            onClick={() => {
              const form = document.getElementById(
                "add-position-form",
              ) as HTMLFormElement | null;
              form?.requestSubmit();
            }}
          >
            {submitting ? "Saving…" : "Add"}
          </PrimaryButton>
        </>
      }
    >
      <form
        id="add-position-form"
        onSubmit={handleSubmit}
        className="grid grid-cols-2 gap-x-4 gap-y-4 pb-6"
      >
        <div className="col-span-2 sm:col-span-1">
          <Field label="Symbol">
            <input
              required
              className={inputClass}
              placeholder="AAPL · 005930.KS"
              value={symbol}
              onChange={(e) => setSymbol(e.target.value)}
              autoComplete="off"
            />
          </Field>
        </div>

        <div className="col-span-2 sm:col-span-1">
          <Field label="Quantity">
            <input
              required
              type="number"
              min="0"
              step="any"
              className={inputClass}
              placeholder="0"
              value={quantity}
              onChange={(e) => setQuantity(e.target.value)}
            />
          </Field>
        </div>

        <div className="col-span-2 sm:col-span-1">
          <Field label="Purchase Price">
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

        <div className="col-span-2">
          <Field label="Notes">
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
