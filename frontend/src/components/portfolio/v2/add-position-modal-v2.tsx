"use client";

/**
 * <AddPositionModalV2 /> — CRITICAL bug fix half of /portfolio v2.
 *
 * Mockup §BLOCK 4 / SPEC §5. Editorial dialog with:
 *   - Eyebrow + Playfair display-h2 headline
 *   - Form fields with mono labels + hairline-bottom inputs
 *   - "Save observation" CTA (legal-safe vocabulary)
 *
 * Two modes (2026-05-22, CEO decision) — a toggle at the top of the form:
 *   - "이미 보유 중 · 기록만" (HOLDING, default): most users are journaling a
 *     position they ALREADY own. The 7-question Deposition is inappropriate
 *     and friction-abandonment was dropping data. This mode SKIPS the
 *     reflection and calls commitPosition() directly on submit. Thesis (memo)
 *     is OPTIONAL — empty is allowed.
 *   - "신규 진입 검토 · 7문항" (NEW_ENTRY): the original flow. Submitting hands
 *     off to <PreTradeFrictionModal /> (ENTRY) — 7-question reflection. The
 *     real POST fires only on its onProceed. Thesis REQUIRED at
 *     ≥MIN_RATIONALE_CHARS (matches the reflection's constant) and prefills
 *     it. The
 *     backend cooldown is now 0, so the friction core auto-proceeds after the
 *     7 questions (no 2-minute countdown).
 *
 * Backend contract (updated 2026-05-22 against routes/portfolio.py
 * ::create_position_alias):
 *   POST PORTFOLIO_POSITIONS = `/api/portfolio/positions`
 *   payload: {symbol, quantity, price, note, purchase_date?}
 *   `purchase_date` ("YYYY-MM-DD", optional) sets the position open date
 *   (opened_at); omitted → today. This is the core HOLDING-mode use case:
 *   backdating a position you already own. side / sector / currency still
 *   have no Position-model column and are intentionally not sent.
 *
 * A11y: role=dialog, aria-modal, focus trap via useFocusTrap, Escape closes.
 */

import * as React from "react";
import { toast } from "sonner";
import { PORTFOLIO_POSITIONS, SEARCH } from "@/lib/endpoints";
import { apiFetch, ApiError } from "@/lib/api";
import { useFocusTrap } from "@/lib/useFocusTrap";
import { displayName, isKrTicker, normalizeTicker } from "@/lib/format";
import { PreTradeFrictionModal } from "@/components/pre-trade/pre-trade-friction-modal";
import { MIN_RATIONALE_CHARS } from "@/components/pre-trade/pre-trade-friction-core";

interface AddPositionModalV2Props {
  open: boolean;
  onClose: () => void;
  onSuccess?: () => void;
}

/** Entry mode — journaling an existing holding vs. reflecting on a new entry. */
type EntryMode = "holding" | "new";

/** Symbol autocomplete result — mirrors the /api/search shape used by
 *  <AddSymbolModal /> (watchlist). { ticker, name, exchange?, is_korean? }. */
interface Suggestion {
  ticker: string;
  name: string;
  exchange?: string;
  is_korean?: boolean;
}

/** Local-date "YYYY-MM-DD" (no UTC shift — matches the date input value). */
function todayStr(): string {
  const d = new Date();
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
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

  const [mode, setMode] = React.useState<EntryMode>("holding");
  const [symbol, setSymbol] = React.useState("");
  const [shares, setShares] = React.useState("");
  const [avgCost, setAvgCost] = React.useState("");
  const [purchaseDate, setPurchaseDate] = React.useState(todayStr());
  const [memo, setMemo] = React.useState("");
  const [submitting, setSubmitting] = React.useState(false);
  // Inline Pre-Trade Friction (ENTRY) — opened after the form validates in
  // NEW_ENTRY mode; the real POST fires only on its onProceed.
  const [frictionOpen, setFrictionOpen] = React.useState(false);

  // Symbol autocomplete (mirrors watchlist <AddSymbolModal />): debounced
  // /api/search, AbortController to pre-empt stale requests, and a `picked`
  // flag to suppress the popover after the user selects a suggestion.
  const [suggestions, setSuggestions] = React.useState<Suggestion[]>([]);
  const [searchLoading, setSearchLoading] = React.useState(false);
  const [picked, setPicked] = React.useState(false);
  const [selectedName, setSelectedName] = React.useState("");
  const abortRef = React.useRef<AbortController | null>(null);

  const today = todayStr();
  // Thesis is required only in NEW_ENTRY mode (the reflection needs
  // ≥MIN_RATIONALE_CHARS).
  // In HOLDING mode it's an optional memo — empty allowed.
  const memoOk = memo.trim().length >= MIN_RATIONALE_CHARS;
  const memoRemaining = Math.max(0, MIN_RATIONALE_CHARS - memo.trim().length);

  // Reset on close
  React.useEffect(() => {
    if (!open) {
      setMode("holding");
      setSymbol("");
      setShares("");
      setAvgCost("");
      setPurchaseDate(todayStr());
      setMemo("");
      setSubmitting(false);
      setFrictionOpen(false);
      // Autocomplete state too.
      setSuggestions([]);
      setSearchLoading(false);
      setPicked(false);
      setSelectedName("");
      abortRef.current?.abort();
    }
  }, [open]);

  // Debounced symbol autocomplete. Pre-empts stale requests; skips while a
  // suggestion is already picked (re-armed when the user edits the field).
  React.useEffect(() => {
    if (!open) return;
    const q = symbol.trim();
    if (picked || q.length < 1) {
      setSuggestions([]);
      setSearchLoading(false);
      abortRef.current?.abort();
      return;
    }
    setSearchLoading(true);
    const ctrl = new AbortController();
    abortRef.current?.abort();
    abortRef.current = ctrl;
    const t = window.setTimeout(async () => {
      try {
        // regression-guards: allow-raw-fetch (debounced /api/search autocomplete —
        // mirrors the watchlist add-symbol modal; needs the AbortController signal
        // to pre-empt stale keystrokes, which apiFetch does not expose).
        const res = await fetch(`${SEARCH}?q=${encodeURIComponent(q)}&limit=6`, {
          credentials: "include",
          signal: ctrl.signal,
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const body: { results?: Suggestion[] } = await res.json();
        setSuggestions(body.results ?? []);
      } catch (err) {
        if ((err as { name?: string })?.name === "AbortError") return;
        setSuggestions([]);
      } finally {
        if (abortRef.current === ctrl) setSearchLoading(false);
      }
    }, 300);
    return () => {
      window.clearTimeout(t);
      ctrl.abort();
    };
  }, [symbol, picked, open]);

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
    if (purchaseDate && purchaseDate > today) {
      toast.error("매수일은 미래일 수 없습니다.");
      return;
    }

    if (mode === "new") {
      // NEW_ENTRY: thesis required ≥MIN_RATIONALE_CHARS; hand off to the 7-question
      // reflection. Nothing is written until the modal calls onProceed.
      if (!memoOk) {
        toast.error(`Thesis는 ${MIN_RATIONALE_CHARS}자 이상 적어주세요 (현재 ${memo.trim().length}자).`);
        return;
      }
      setFrictionOpen(true);
      return;
    }

    // HOLDING: skip the reflection — record the existing position directly.
    void commitPosition();
  }

  // Commit the real position. Two callers:
  //   - HOLDING mode: directly from handleSubmit (no friction).
  //   - NEW_ENTRY mode: from the friction modal's onProceed.
  // Backend `routes/portfolio.py::create_position_alias` reads
  // {symbol, quantity, price, note, purchase_date?}. `purchase_date`
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
      await apiFetch(PORTFOLIO_POSITIONS, {
        method: "POST",
        body: JSON.stringify(body),
      });
      toast.success("Position recorded · informational only, not advice.");
      onSuccess?.();
      // HOLDING mode owns its own close (no friction modal to do it).
      if (mode === "holding") {
        onClose();
      }
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        if (typeof window !== "undefined") window.location.href = "/login";
        return;
      }
      const message =
        err instanceof Error ? err.message : "Failed to record position.";
      if (mode === "holding") {
        // No friction modal to surface the error — toast here.
        toast.error(message);
        return;
      }
      // NEW_ENTRY: re-throw so the friction modal surfaces it (the reflection
      // is already stamped; the journal write is what failed).
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
        {/* Hero block — copy keys off mode */}
        <div style={{ marginBottom: 24 }}>
          <div
            className="font-mono uppercase"
            style={{
              fontSize: "var(--pq-text-eyebrow)",
              letterSpacing: "0.22em",
              color: "var(--pq-bronze)",
              marginBottom: 14,
            }}
          >
            {mode === "holding" ? "Observation · Existing holding" : "Observation · New entry"}
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
            {mode === "holding" ? (
              <>
                Log a{" "}
                <span style={{ color: "var(--pq-bronze)" }}>position you hold.</span>
              </>
            ) : (
              <>
                Record a{" "}
                <span style={{ color: "var(--pq-bronze)" }}>new position.</span>
              </>
            )}
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
            {mode === "holding"
              ? "이미 보유한 종목을 책에 기록합니다. 질문 없이 바로 저장 — 매수일은 과거로 자유롭게 적어도 됩니다."
              : "Saved to your book · not sent to broker. Journaling only — 7개 질문을 거친 뒤 기록됩니다."}
          </p>
        </div>

        {/* Mode toggle */}
        <div
          role="radiogroup"
          aria-label="기록 방식"
          style={{ display: "flex", gap: 8, marginBottom: 28 }}
        >
          <ModeToggleButton
            active={mode === "holding"}
            label="이미 보유 중 · 기록만"
            onClick={() => setMode("holding")}
          />
          <ModeToggleButton
            active={mode === "new"}
            label="신규 진입 검토 · 7문항"
            onClick={() => setMode("new")}
          />
        </div>

        <form
          onSubmit={handleSubmit}
          style={{ display: "flex", flexDirection: "column", gap: 20 }}
        >
          {/* Symbol — full row, with debounced autocomplete dropdown */}
          <FormField label="Symbol">
            <div style={{ position: "relative" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <input
                  required
                  value={symbol}
                  onChange={(e) => {
                    setSymbol(e.target.value.toUpperCase());
                    setPicked(false);
                    setSelectedName("");
                  }}
                  placeholder="AAPL · 005930.KS"
                  autoComplete="off"
                  aria-label="Symbol"
                  style={{ ...fieldInputStyle, flex: 1 }}
                />
                {searchLoading && (
                  <span
                    className="font-mono uppercase"
                    aria-label="Searching"
                    style={{
                      fontSize: "var(--pq-text-eyebrow)",
                      letterSpacing: "0.14em",
                      color: "rgba(245,240,232,0.45)",
                    }}
                  >
                    …
                  </span>
                )}
              </div>

              {/* Picked-symbol confirmation — shows the resolved company name. */}
              {picked && selectedName && (
                <span
                  className="font-serif"
                  style={{
                    display: "block",
                    marginTop: 6,
                    fontSize: "var(--pq-text-body)",
                    color: "var(--pq-bronze)",
                  }}
                >
                  {selectedName}
                </span>
              )}

              {/* Autocomplete popover */}
              {!picked && symbol.trim().length > 0 && suggestions.length > 0 && (
                <div
                  role="listbox"
                  aria-label="종목 검색 결과"
                  style={{
                    position: "absolute",
                    left: 0,
                    right: 0,
                    top: "100%",
                    zIndex: 20,
                    marginTop: 4,
                    maxHeight: 224,
                    overflowY: "auto",
                    background: "var(--pq-ink, #050505)",
                    border:
                      "1px solid var(--pq-hairline-ink, rgba(245,240,232,0.16))",
                    borderRadius: "var(--pq-radius-card, 4px)",
                    boxShadow: "0 18px 44px -20px rgba(0,0,0,0.7)",
                  }}
                >
                  {suggestions.map((s) => (
                    <button
                      key={s.ticker}
                      type="button"
                      role="option"
                      aria-selected={false}
                      onClick={() => {
                        // Canonical exchange ticker (e.g. "005930.KS") — the
                        // backend resolves this on submit; do NOT strip suffix.
                        setSymbol(s.ticker.trim().toUpperCase());
                        setSelectedName(displayName(s.ticker, s.name));
                        setPicked(true);
                        setSuggestions([]);
                      }}
                      style={{
                        display: "flex",
                        width: "100%",
                        alignItems: "center",
                        gap: 12,
                        padding: "10px 12px",
                        background: "transparent",
                        border: "none",
                        borderBottom:
                          "1px solid var(--pq-hairline-ink, rgba(245,240,232,0.08))",
                        textAlign: "left",
                        cursor: "pointer",
                      }}
                      onMouseEnter={(e) => {
                        e.currentTarget.style.background =
                          "rgba(184,149,106,0.12)";
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.background = "transparent";
                      }}
                    >
                      <span
                        className="font-serif"
                        style={{
                          flex: 1,
                          minWidth: 0,
                          overflow: "hidden",
                          textOverflow: "ellipsis",
                          whiteSpace: "nowrap",
                          fontSize: "var(--pq-text-body)",
                          fontWeight: 600,
                          color: "var(--pq-ivory)",
                        }}
                      >
                        {displayName(s.ticker, s.name)}
                      </span>
                      <span
                        className="font-mono uppercase"
                        style={{
                          fontSize: "var(--pq-text-eyebrow)",
                          letterSpacing: "0.12em",
                          color: "var(--pq-bronze)",
                          whiteSpace: "nowrap",
                        }}
                      >
                        {normalizeTicker(s.ticker)}
                        {s.exchange ? ` · ${s.exchange}` : ""}
                      </span>
                    </button>
                  ))}
                </div>
              )}
            </div>
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
            <FormField label={`Avg cost${sym ? (isKrTicker(sym) ? " (KRW)" : " (USD)") : ""}`}>
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

          {/* Purchase date — when you opened the position. HOLDING mode's core
              use is backdating; NEW_ENTRY defaults to today. max=today blocks
              future dates client-side (also re-checked in handleSubmit). */}
          <FormField label="매수일 · Purchase date">
            <input
              type="date"
              value={purchaseDate}
              max={today}
              onChange={(e) => setPurchaseDate(e.target.value)}
              style={{ ...fieldInputStyle, colorScheme: "dark" }}
            />
          </FormField>

          {/* Thesis — required ≥MIN_RATIONALE_CHARS in NEW_ENTRY (prefills the
              reflection); optional memo in HOLDING mode. */}
          {mode === "new" ? (
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
          ) : (
            <FormField label="메모 · 언제·왜 샀나 (선택)">
              <textarea
                value={memo}
                onChange={(e) => setMemo(e.target.value)}
                rows={3}
                placeholder="언제, 왜 들어갔는지 한 줄로 — 비워도 됩니다."
                style={{ ...fieldInputStyle, resize: "vertical", minHeight: 56 }}
              />
            </FormField>
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
                {submitting
                  ? "Saving…"
                  : mode === "holding"
                    ? "Record · 기록"
                    : "Continue · 7 questions →"}
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

export default AddPositionModalV2;
