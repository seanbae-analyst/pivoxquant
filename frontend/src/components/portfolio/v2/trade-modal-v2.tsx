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
 * buy/sell are record-only (2026-10-13, CEO): the trade already happened —
 * the user is journaling a past fill. No questions; submit calls
 * commitTrade() directly. Thesis (note) is OPTIONAL — empty is allowed.
 * The 7-question pause lives only on /pre-trade (before buying), which never
 * writes to the ledger; on buy a quiet <PreTradeFirstLink /> points there.
 * A recorded buy can still be linked to a recent pause on this ticker via
 * <ReflectionLinkLine /> (services/pre_trade/link.py). The former in-modal
 * reflection mode wrote the trade the moment the user finished thinking —
 * before any real fill — so the ledger could disagree with the broker.
 * `edit` (avg-cost/memo adjustment) is NOT a buy/sell event — it commits
 * directly via PATCH (unchanged).
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
import { Sheet, SheetFooter, type SheetHandle } from "@/components/ui/sheet";
import { currentLocationPath, loginHref } from "@/lib/login-redirect";
import type { Position, TradeAction } from "@/components/portfolio/types";
import {
  ReflectionLinkLine,
  reflectionLinkBody,
  useReflectionLink,
} from "@/components/pre-trade/reflection-link-line";
import { PreTradeFirstLink } from "@/components/portfolio/v2/pre-trade-first-link";
import { TypedSellMoment } from "@/components/journal/sell-moment";

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

/** buy/sell read as journaling a done trade; edit adjusts a record. */
const COPY: Record<TradeAction, CopyEntry> = {
  buy: {
    eyebrow: "기록 · 추가",
    headline: "이미 체결한",
    accentWord: "추가를 기록합니다.",
    cta: "기록하기",
    toast: "거래를 기록했습니다 · 정보 기록용입니다.",
    helper: "이미 체결한 추가 매수를 책에 기록합니다. 질문 없이 바로 저장.",
  },
  sell: {
    eyebrow: "기록 · 정리",
    headline: "이미 체결한",
    accentWord: "정리를 기록합니다.",
    cta: "기록하기",
    toast: "거래를 기록했습니다 · 정보 기록용입니다.",
    helper: "이미 체결한 매도를 책에 기록합니다. 질문 없이 바로 저장.",
  },
  edit: {
    eyebrow: "기록 · 수정",
    headline: "기록을",
    accentWord: "수정합니다.",
    cta: "기록 수정 →",
    toast: "보유 종목을 수정했습니다.",
    helper: "이 종목의 평균가나 메모를 수정합니다.",
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
  const sheetRef = React.useRef<SheetHandle>(null);
  // Cancel / success close through the sheet so the phone exit animates.
  const close = React.useCallback(() => {
    if (sheetRef.current) sheetRef.current.dismiss();
    else onClose();
  }, [onClose]);

  const [shares, setShares] = React.useState("");
  const [price, setPrice] = React.useState("");
  const [date, setDate] = React.useState(() =>
    new Date().toISOString().slice(0, 10),
  );
  const [avgCost, setAvgCost] = React.useState("");
  const [note, setNote] = React.useState("");
  const [submitting, setSubmitting] = React.useState(false);
  // 2026-09-29 — buy: offer to link a recent pause on this ticker.
  const reflectionLink = useReflectionLink(action === "buy" ? position?.symbol : null);

  const copy = COPY[action];

  // Reset the form whenever the modal opens or position/action changes.
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

  // Escape / backdrop / back are owned by <Sheet /> (desktop and phone).

  if (!position) return null;

  // Validate the form, then commit (edit → PATCH, buy/sell → POST trade).
  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!position || submitting) return;

    if (action === "edit") {
      const parsedCost = Number(avgCost);
      if (!Number.isFinite(parsedCost) || parsedCost <= 0) {
        toast.error("평균가는 0보다 커야 합니다.");
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
        close();
      } catch (err) {
        if (err instanceof ApiError && err.status === 401) {
          if (typeof window !== "undefined") window.location.href = loginHref(currentLocationPath());
          return;
        }
        const message =
          err instanceof Error ? err.message : "기록하지 못했습니다.";
        toast.error(message);
      } finally {
        setSubmitting(false);
      }
      return;
    }

    // buy / sell — quantity/price/over-trim guards, then record the fill.
    const parsedQty = Number(shares);
    const parsedPrice = Number(price);
    if (!Number.isFinite(parsedQty) || parsedQty <= 0) {
      toast.error("수량은 0보다 커야 합니다.");
      return;
    }
    if (!Number.isFinite(parsedPrice) || parsedPrice <= 0) {
      toast.error("가격은 0보다 커야 합니다.");
      return;
    }
    if (action === "sell" && parsedQty > position.shares) {
      toast.error(`보유 수량(${position.shares}주)보다 많이 정리할 수 없습니다.`);
      return;
    }

    void commitTrade();
  }

  // Commit the buy/sell trade the user already filled at their broker.
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
          // Buy → the link line's choice (id, or an explicit decline when the
          // shown pause was unchecked); `{}` when no pause was offered.
          ...reflectionLinkBody(reflectionLink),
        }),
      });
      toast.success(copy.toast);
      onSuccess?.();
      close();
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        if (typeof window !== "undefined") window.location.href = loginHref(currentLocationPath());
        return;
      }
      const message =
        err instanceof Error ? err.message : "기록하지 못했습니다.";
      toast.error(message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Sheet
      ref={sheetRef}
      open={open}
      onClose={onClose}
      ariaLabelledBy={headlineId}
      showClose
      desktopOverlayClassName="pq-modal-v2"
      desktopOverlayStyle={{
        position: "fixed",
        inset: 0,
        zIndex: 1000,
        background: "rgba(5,5,5,0.78)",
        backdropFilter: "blur(8px)",
        WebkitBackdropFilter: "blur(8px)",
        display: "flex",
        alignItems: "flex-start",
        justifyContent: "center",
        padding: "10vh 24px calc(24px + env(safe-area-inset-bottom, 0px))",
        overflowY: "auto",
      }}
      desktopPanelStyle={{
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
            className="font-mono"
            style={{
              fontSize: "var(--pq-text-eyebrow)",
              letterSpacing: "0.02em",
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
              fontSize: "clamp(24px, 4vw + 8px, 32px)" /* 24px in a phone sheet, 32px from ~600px */,
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
              color: "var(--pq-ivory-mid)",
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
                color: "var(--pq-ivory-dim)",
                letterSpacing: "0.01em",
              }}
            >
              {normalizeTicker(position.symbol)}
            </span>{" "}
            · {copy.helper}
          </p>
        </div>

        {/* Not bought yet → the pause lives on /pre-trade (never writes here). */}
        {action === "buy" && <PreTradeFirstLink style={{ marginBottom: 28 }} />}

        <form
          onSubmit={handleSubmit}
          style={{ display: "flex", flexDirection: "column", gap: 20 }}
        >
          {action === "edit" ? (
            <>
              <FormField label="평균가 (주당)">
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
              <FormField label="메모">
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
                  label={action === "sell" ? `수량 (최대 ${position.shares})` : "수량"}
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
                  label={`주당 가격 ${
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
              <FormField label="날짜">
                <input
                  required
                  type="date"
                  value={date}
                  onChange={(e) => setDate(e.target.value)}
                  style={{ ...fieldInputStyle, colorScheme: "dark" }}
                />
              </FormField>
              {/* 매도 순간의 거울 (2026-10-15): once shares and price are
                  known, what the user wrote about this stock before + the
                  hold of the lots this sell closes. Read-only. */}
              {action === "sell" && (
                <TypedSellMoment
                  ticker={position.symbol}
                  shares={Number(shares)}
                  price={Number(price)}
                  date={date}
                  currency={position.currency}
                />
              )}
              <FormField label="메모 · 언제·왜 거래했나 (선택)">
                <textarea
                  value={note}
                  onChange={(e) => setNote(e.target.value)}
                  rows={3}
                  placeholder="언제, 왜 체결했는지 한 줄로 — 비워도 됩니다."
                  style={{ ...fieldInputStyle, resize: "vertical", minHeight: 56 }}
                />
              </FormField>
              <ReflectionLinkLine link={reflectionLink} />
            </>
          )}

          {/* Footer */}
          <SheetFooter
            desktopStyle={{
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
              className="font-mono"
              style={{
                fontSize: "var(--pq-text-eyebrow)",
                letterSpacing: "0.02em",
                color: "var(--pq-ivory-dim)",
              }}
            >
              내 장부에만 저장 · 증권사로 전송되지 않음
            </span>
            <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
              <button
                type="button"
                onClick={close}
                className="font-mono"
                style={{
                  background: "transparent",
                  border: "none",
                  color: "var(--pq-ivory-dim)",
                  fontSize: "var(--pq-text-eyebrow)",
                  letterSpacing: "0.02em",
                  cursor: "pointer",
                  padding: 4,
                }}
              >
                취소
              </button>
              <button
                type="submit"
                disabled={submitting}
                className="font-mono"
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
                  letterSpacing: "0.02em",
                  cursor: submitting ? "not-allowed" : "pointer",
                }}
              >
                {submitting ? "저장 중…" : copy.cta}
              </button>
            </div>
          </SheetFooter>
        </form>
    </Sheet>
  );
}

// font-size intentionally NOT set inline — every consumer pairs this style
// with `className="pq-input-noom"` so desktop renders 14px (the class
// default) and mobile is pinned to 16px. The previous inline 14px defeated
// the global mobile guard and caused iOS Safari to zoom on focus for every
// trade-modal field (shares / cost / date / memo).
const fieldInputStyle: React.CSSProperties = {
  width: "100%",
  padding: "8px 0",
  background: "transparent",
  border: "none",
  borderBottom: "1px solid var(--pq-hairline-ink, rgba(245,240,232,0.16))",
  outline: "none",
  color: "var(--pq-ivory)",
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
        className="font-mono"
        style={{
          fontSize: "var(--pq-text-eyebrow)",
          letterSpacing: "0.02em",
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
