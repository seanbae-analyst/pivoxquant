"use client";

import { useState, type FormEvent } from "react";
import {
  PortfolioModal,
  Field,
  inputClass,
  CancelButton,
  PrimaryButton,
} from "./portfolio-modal";
import type { Side } from "./types";

interface AddPositionModalProps {
  open: boolean;
  onClose: () => void;
  onSubmit?: (payload: {
    symbol: string;
    side: Side;
    quantity: number;
    price: number;
    date: string;
    notes: string;
  }) => void;
}

export function AddPositionModal({
  open,
  onClose,
  onSubmit,
}: AddPositionModalProps) {
  const [symbol, setSymbol] = useState("");
  const [side, setSide] = useState<Side>("Long");
  const [quantity, setQuantity] = useState("");
  const [price, setPrice] = useState("");
  const [date, setDate] = useState(() =>
    new Date().toISOString().slice(0, 10),
  );
  const [notes, setNotes] = useState("");

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const payload = {
      symbol: symbol.trim().toUpperCase(),
      side,
      quantity: Number(quantity) || 0,
      price: Number(price) || 0,
      date,
      notes: notes.trim(),
    };
    // Record-only UX. Parent may wire to backend later.
    // eslint-disable-next-line no-console
    console.log("[PortfolioRecord] add position", payload);
    onSubmit?.(payload);
    reset();
    onClose();
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
      subtitle="Log a holding you already own. Records only — not a transaction."
      footer={
        <>
          <CancelButton onClick={onClose} />
          <PrimaryButton
            type="button"
            onClick={() => {
              // Bridge the submit to the form outside the footer.
              const form = document.getElementById(
                "add-position-form",
              ) as HTMLFormElement | null;
              form?.requestSubmit();
            }}
          >
            Add
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
      </form>
    </PortfolioModal>
  );
}
