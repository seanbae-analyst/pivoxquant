"use client";

/**
 * <AddPositionModalV2 /> — CRITICAL bug fix half of /portfolio v2.
 *
 * Mockup §BLOCK 4 / SPEC §5. Editorial dialog with:
 *   - Eyebrow + Playfair display-h2 headline
 *   - Form fields with mono labels + hairline-bottom inputs
 *   - "Save observation" CTA (legal-safe vocabulary)
 *
 * Record-only (2026-10-13, CEO): this modal records a position the user
 * already holds — after the fill. No questions; submit calls commitPosition()
 * directly. Thesis (memo) is OPTIONAL — empty is allowed. The 7-question
 * pause lives only on /pre-trade (before buying), which never writes to the
 * ledger; a quiet <PreTradeFirstLink /> points there. The former in-modal
 * reflection mode wrote the position the moment the user finished thinking —
 * before any real fill — so the ledger could disagree with the broker.
 *
 * Pause link (2026-10-13): when a recent unlinked pause exists for the typed
 * ticker, <ReflectionLinkLine /> offers to link it (default ON) and the POST
 * carries `reflection_id` — the backend then writes a recorded buy linked to
 * that pause instead of a holding seed. Not offered when `holdingOnly`, and
 * not offered when the purchase date is earlier than the pause's day (both
 * local calendar days): a holding bought before the pause cannot be its
 * outcome.
 *
 * Backend contract (updated 2026-05-22 against routes/portfolio.py
 * ::create_position_alias):
 *   POST PORTFOLIO_POSITIONS = `/api/portfolio/positions`
 *   payload: {symbol, quantity, price, note, purchase_date?}
 *   `purchase_date` ("YYYY-MM-DD", optional) sets the position open date
 *   (opened_at); omitted → today. This is the core use case:
 *   backdating a position you already own. side / sector / currency still
 *   have no Position-model column and are intentionally not sent.
 *
 * A11y: role=dialog, aria-modal, focus trap, Escape closes — all via <Sheet />
 * (components/ui/sheet.tsx), which is also the phone bottom sheet (drag to
 * dismiss, back button closes, pinned footer). Desktop markup unchanged.
 */

import * as React from "react";
import { toast } from "sonner";
import { PORTFOLIO_POSITIONS } from "@/lib/endpoints";
import { apiFetch, ApiError } from "@/lib/api";
import { Sheet, SheetFooter, type SheetHandle } from "@/components/ui/sheet";
import { isKrTicker } from "@/lib/format";
import { TickerSearch } from "@/components/shared/ticker-search";
import { HoldingsImportPanel } from "@/components/portfolio/v2/holdings-import-panel";
import { PreTradeFirstLink } from "@/components/portfolio/v2/pre-trade-first-link";
import {
  ReflectionLinkLine,
  useReflectionLink,
} from "@/components/pre-trade/reflection-link-line";
import { parseUtcSafe } from "@/lib/relative-time";
import { useT } from "@/lib/locale";
import { currentLocationPath, loginHref } from "@/lib/login-redirect";
import { localDayStr } from "@/lib/local-day";

interface AddPositionModalV2Props {
  open: boolean;
  onClose: () => void;
  onSuccess?: () => void;
  /** Open straight on the holdings-capture import (/portfolio?import=holdings). */
  startWithImport?: boolean;
  /** Onboarding: no capture entry (the onboarding page shows the capture
   *  itself), no /pre-trade pointer and no pause link. */
  holdingOnly?: boolean;
}

/** Typing settles before the linkable-pause lookup (one fetch per ticker,
 *  not per keystroke). Matches <TickerSearch />'s search debounce. */
const LINK_LOOKUP_DEBOUNCE_MS = 300;


// SECTOR_OPTIONS removed 2026-05-01 — sector is resolved server-side via
// SignalCache (kr_stock_registry / FMP profile) and is NOT a Position
// model column. User-picked sector was being dropped by the backend.

export function AddPositionModalV2({
  open,
  onClose,
  onSuccess,
  startWithImport = false,
  holdingOnly = false,
}: AddPositionModalV2Props) {
  const headlineId = "add-pos-v2-headline";
  const sheetRef = React.useRef<SheetHandle>(null);
  // Cancel / success close through the sheet so the phone exit animates.
  const close = React.useCallback(() => {
    if (sheetRef.current) sheetRef.current.dismiss();
    else onClose();
  }, [onClose]);
  const t = useT();
  // Holdings-screen capture import (HOLDINGS_IMPORT_DESIGN.md) replaces the
  // form inside the same dialog shell.
  const [importing, setImporting] = React.useState(false);

  const [symbol, setSymbol] = React.useState("");
  const [shares, setShares] = React.useState("");
  const [avgCost, setAvgCost] = React.useState("");
  const [purchaseDate, setPurchaseDate] = React.useState(localDayStr());
  const [memo, setMemo] = React.useState("");
  const [submitting, setSubmitting] = React.useState(false);

  // Symbol autocomplete lives in <TickerSearch /> (components/shared) since
  // 2026-09-22 — debounce, AbortController and the `picked` flag are all
  // owned there, and it unmounts with this modal so nothing needs resetting.

  const today = localDayStr();

  // Reset on close
  React.useEffect(() => {
    if (!open) {
      setSymbol("");
      setShares("");
      setAvgCost("");
      setPurchaseDate(localDayStr());
      setMemo("");
      setSubmitting(false);
      setImporting(false);
    }
  }, [open]);
  React.useEffect(() => {
    if (open && startWithImport) setImporting(true);
  }, [open, startWithImport]);

  // Escape / backdrop / back are owned by <Sheet />.

  const sym = symbol.trim().toUpperCase();
  const sharesN = Number(shares);
  const costN = Number(avgCost);

  // Linkable pause for this ticker — looked up once typing settles.
  const [linkTicker, setLinkTicker] = React.useState("");
  React.useEffect(() => {
    const id = setTimeout(
      () => setLinkTicker(holdingOnly ? "" : sym),
      LINK_LOOKUP_DEBOUNCE_MS,
    );
    return () => clearTimeout(id);
  }, [sym, holdingOnly]);
  const reflectionLink = useReflectionLink(linkTicker || null);
  // Guard: a holding bought before the pause cannot be its outcome. An empty
  // purchase date means today (backend default); an unreadable pause date is
  // never offered.
  const pauseAt = parseUtcSafe(reflectionLink.candidate?.cooldown_started_at ?? null);
  const pauseDay = Number.isNaN(pauseAt) ? "" : localDayStr(new Date(pauseAt));
  const linkOffered =
    reflectionLink.candidate != null &&
    linkTicker === sym &&
    pauseDay !== "" &&
    (purchaseDate || today) >= pauseDay;

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (submitting) return;

    if (!sym) {
      toast.error("종목 코드를 입력하세요.");
      return;
    }
    if (!Number.isFinite(sharesN) || sharesN <= 0) {
      toast.error("수량은 0보다 커야 합니다.");
      return;
    }
    if (!Number.isFinite(costN) || costN <= 0) {
      toast.error("평균가는 0보다 커야 합니다.");
      return;
    }
    if (purchaseDate && purchaseDate > today) {
      toast.error("매수일은 미래일 수 없습니다.");
      return;
    }

    void commitPosition();
  }

  // Commit the position. Backend `routes/portfolio.py::create_position_alias`
  // reads {symbol, quantity, price, note, purchase_date?, reflection_id?}. `purchase_date`
  // ("YYYY-MM-DD") sets opened_at; omitted → today. side / sector /
  // currency still have no Position-model column.
  async function commitPosition() {
    setSubmitting(true);
    try {
      const body: Record<string, unknown> = {
        symbol: sym,
        quantity: sharesN,
        price: costN,
        note: memo.trim(),
      };
      if (purchaseDate) body.purchase_date = purchaseDate;
      // Checked link → the pause this buy came from. Unchecked / not offered
      // → nothing (the positions route takes no explicit decline).
      if (linkOffered && reflectionLink.reflectionId != null) {
        body.reflection_id = reflectionLink.reflectionId;
      }
      await apiFetch(PORTFOLIO_POSITIONS, {
        method: "POST",
        body: JSON.stringify(body),
      });
      toast.success("종목을 기록했습니다 · 정보 기록용입니다.");
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
        {importing ? (
          <>
            <h2
              id={headlineId}
              className="font-display"
              style={{ fontWeight: 500, fontSize: "var(--pq-text-h3)", lineHeight: 1.15, letterSpacing: "-0.02em", color: "var(--pq-ivory)", margin: "0 0 16px 0" }}
            >
              {t("dashboard.portfolio.holdingsImport.title")}
            </h2>
            <HoldingsImportPanel
              onCancel={() => setImporting(false)}
              onDone={() => {
                onSuccess?.();
                close();
              }}
            />
          </>
        ) : (
        <>
        {/* Hero block */}
        <div style={{ marginBottom: 24 }}>
          <div
            className="font-mono"
            style={{
              fontSize: "var(--pq-text-eyebrow)",
              letterSpacing: "0.02em",
              color: "var(--pq-bronze)",
              marginBottom: 14,
            }}
          >
            기록 · 보유 중인 종목
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
            지금 들고 있는{" "}
            <span style={{ color: "var(--pq-bronze)" }}>종목을 기록합니다.</span>
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
            이미 보유한 종목을 책에 기록합니다. 질문 없이 바로 저장 — 매수일은 과거로 자유롭게 적어도 됩니다.
          </p>
        </div>

        {/* Not bought yet → the pause lives on /pre-trade (never writes here). */}
        {!holdingOnly && <PreTradeFirstLink style={{ marginBottom: 20 }} />}

        {/* Secondary entry: many positions at once from a holdings capture. */}
        {!holdingOnly && (
          <button
            type="button"
            onClick={() => setImporting(true)}
            className="font-mono"
            data-testid="open-holdings-import"
            style={{
              display: "block",
              width: "100%",
              textAlign: "left",
              margin: "0 0 24px",
              padding: "10px 12px",
              background: "transparent",
              border: "1px dashed rgba(184,149,106,0.45)",
              borderRadius: "var(--pq-radius-cta, 2px)",
              color: "var(--pq-bronze)",
              fontSize: "var(--pq-text-mono-sm)",
              letterSpacing: "0.04em",
              cursor: "pointer",
            }}
          >
            {t("dashboard.portfolio.holdingsImport.entry")} →
            <span style={{ display: "block", marginTop: 4, color: "var(--pq-ivory-dim)", letterSpacing: 0 }}>
              {t("dashboard.portfolio.holdingsImport.entryHint")}
            </span>
          </button>
        )}

        <form
          onSubmit={handleSubmit}
          style={{ display: "flex", flexDirection: "column", gap: 20 }}
        >
          {/* Symbol — full row, with debounced autocomplete dropdown */}
          <FormField label="종목 코드">
            <TickerSearch
              required
              value={symbol}
              onChange={setSymbol}
              onPick={(s) => setSymbol(s.ticker.trim().toUpperCase())}
              placeholder="AAPL · 005930.KS"
              limit={6}
              inputStyle={fieldInputStyle}
            />
          </FormField>

          {/* Row 1: Shares + Avg cost */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20 }}>
            <FormField label="수량">
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
            <FormField label={`평균가${sym ? (isKrTicker(sym) ? " (KRW)" : " (USD)") : ""}`}>
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

          {/* Purchase date — when you opened the position. The core use is
              backdating; defaults to today. max=today blocks future dates
              client-side (also re-checked in handleSubmit). */}
          <FormField label="매수일">
            <input
              type="date"
              value={purchaseDate}
              max={today}
              onChange={(e) => setPurchaseDate(e.target.value)}
              style={{ ...fieldInputStyle, colorScheme: "dark" }}
            />
          </FormField>

          {/* Memo — optional. */}
          <FormField label="메모 · 언제·왜 샀나 (선택)">
            <textarea
              value={memo}
              onChange={(e) => setMemo(e.target.value)}
              rows={3}
              placeholder="언제, 왜 들어갔는지 한 줄로 — 비워도 됩니다."
              style={{ ...fieldInputStyle, resize: "vertical", minHeight: 56 }}
            />
          </FormField>

          {linkOffered && <ReflectionLinkLine link={reflectionLink} />}

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
                {submitting ? "저장 중…" : "기록하기"}
              </button>
            </div>
          </SheetFooter>
        </form>
        </>
        )}
    </Sheet>
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

export default AddPositionModalV2;
