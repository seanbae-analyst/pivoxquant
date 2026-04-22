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
import type { Side } from "./types";
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
  const [side, setSide] = useState<Side>("Long");
  const [quantity, setQuantity] = useState("");
  const [price, setPrice] = useState("");
  const [date, setDate] = useState(() =>
    new Date().toISOString().slice(0, 10),
  );
  const [notes, setNotes] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (submitting) return;

    const payload = {
      symbol: symbol.trim().toUpperCase(),
      side,
      quantity: Number(quantity) || 0,
      price: Number(price) || 0,
      purchase_date: date,
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
    setSide("Long");
    setQuantity("");
    setPrice("");
    setDate(new Date().toISOString().slice(0, 10));
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
              placeholder="AAPL"
              value={symbol}
              onChange={(e) => setSymbol(e.target.value)}
              autoComplete="off"
            />
          </Field>
        </div>

        <div className="col-span-2 sm:col-span-1">
          <Field label="Side">
            <div className="flex h-10 overflow-hidden rounded-sm border border-slate-200">
              {(["Long", "Short"] as Side[]).map((opt) => {
                const active = side === opt;
                return (
                  <button
                    key={opt}
                    type="button"
                    onClick={() => setSide(opt)}
                    className={
                      "flex-1 text-[13px] font-medium transition-colors " +
                      (active
                        ? "bg-slate-900 text-white"
                        : "bg-white text-slate-600 hover:bg-slate-50")
                    }
                  >
                    {opt}
                  </button>
                );
              })}
            </div>
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

        <div className="col-span-2 sm:col-span-1">
          <Field label="Purchase Date">
            <input
              required
              type="date"
              className={inputClass}
              value={date}
              onChange={(e) => setDate(e.target.value)}
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

        <p className="col-span-2 text-[11px] text-slate-500">
          User-entered record only. Not investment advice.
        </p>
      </form>
    </PortfolioModal>
  );
}
