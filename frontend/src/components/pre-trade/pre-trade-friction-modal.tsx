"use client";

/**
 * <PreTradeFrictionModal /> — inline Pre-Trade Friction at the moment of action.
 *
 * Mounts the SHARED reflection cycle (questions → cooldown → proceed/cancel →
 * terminal) from `pre-trade-friction-core`. The Setup step is skipped — the
 * host prefills ticker / side / shares / rationale. Used by Portfolio v2:
 *   - Add (ENTRY): AddPositionModalV2 collects fields → this modal → onProceed
 *     commits the real `POST /api/portfolio/positions`.
 *   - Trim·Close (EXIT): TradeModalV2 → this modal → onProceed commits the
 *     real `POST /api/portfolio/trades`.
 *
 * Compliance: journaling only. `/proceed` stamps "user finished thinking";
 * onProceed() commits the journal record — no broker order is placed.
 * Cooldown is intentional friction (the whole point of moving it inline).
 *
 * v3 tone: Vantablack + Bronze + Playfair UPRIGHT. POSITIVE/NEGATIVE/NEUTRAL.
 *
 * A11y: role=dialog, aria-modal, focus trap, Escape closes (when not mid-cycle).
 */

import * as React from "react";
import { X } from "lucide-react";
import { useFocusTrap } from "@/lib/useFocusTrap";
import { sideLabel, type Side } from "@/lib/pre-trade";
import {
  usePreTradeCycle,
  QuestionsStep,
  CooldownStep,
  TerminalStep,
  QUESTIONS,
} from "./pre-trade-friction-core";

export interface PreTradeFrictionModalProps {
  open: boolean;
  /** Internal Side — ENTRY (add) or EXIT (trim/close). */
  side: Side;
  ticker: string;
  /** Company name for display (falls back to ticker). */
  tickerName?: string | null;
  shares?: string;
  /** Pre-filled thesis (≥50 chars expected — host validated before opening). */
  rationale: string;
  /**
   * Called once /proceed succeeds. Host commits the real journal record here
   * (add / trim / close). May be async; thrown errors surface a toast but the
   * reflection stays stamped.
   */
  onProceed: () => Promise<void> | void;
  /** Called when the user cancels the reflection (host keeps its modal open). */
  onCancel?: () => void;
  /** Close the modal entirely (X / backdrop / terminal Close). */
  onClose: () => void;
}

export function PreTradeFrictionModal({
  open,
  side,
  ticker,
  tickerName,
  shares,
  rationale,
  onProceed,
  onCancel,
  onClose,
}: PreTradeFrictionModalProps) {
  const headlineId = "pre-trade-modal-headline";
  const trapRef = useFocusTrap<HTMLDivElement>(open);

  // Question acks/answers live here; reset whenever the modal (re)opens.
  const [acks, setAcks] = React.useState<Record<number, boolean>>({});
  const [answers, setAnswers] = React.useState<Record<number, string>>({});

  const cycle = usePreTradeCycle({
    side,
    ticker,
    sharesText: shares,
    rationale,
    acks,
    answers,
    onProceeded: onProceed,
    onCancelled: onCancel,
  });

  // On open: reset acks/answers and jump straight to the questions step
  // (Setup is owned by the host modal that prefilled us).
  React.useEffect(() => {
    if (open) {
      setAcks({});
      setAnswers({});
      cycle.setPhase("questions");
    }
    // cycle.setPhase is stable (useState setter via useCallback)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  // Escape closes — but only when NOT mid-cooldown (don't let users bail the
  // friction with a keystroke; they must Cancel explicitly during cooldown).
  React.useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && cycle.phase !== "cooldown") onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, onClose, cycle.phase]);

  if (!open) return null;

  const allAcked = QUESTIONS.every((q) => acks[q.n]);
  const displayName = tickerName || ticker;

  // Header copy keys off side + phase.
  const eyebrow =
    side === "ENTRY" ? "Reflection · Before you add" : "Reflection · Before you trim";

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby={headlineId}
      className="pq-modal-v2"
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 1100,
        background: "rgba(5,5,5,0.82)",
        backdropFilter: "blur(8px)",
        WebkitBackdropFilter: "blur(8px)",
        display: "flex",
        alignItems: "flex-start",
        justifyContent: "center",
        padding: "8vh 20px 24px",
        overflowY: "auto",
      }}
      onClick={(e) => {
        // Backdrop click closes only outside the active cooldown.
        if (e.target === e.currentTarget && cycle.phase !== "cooldown") onClose();
      }}
    >
      <div
        ref={trapRef}
        style={{
          width: "100%",
          maxWidth: 620,
          background: "rgba(184,149,106,0.025)",
          border: "1px solid var(--pq-hairline-ink, var(--pq-ivory-line))",
          borderRadius: "var(--pq-radius-card, 4px)",
          padding: "32px 32px 36px",
          color: "var(--pq-ivory)",
        }}
      >
        {/* Header */}
        <div
          style={{
            display: "flex",
            alignItems: "flex-start",
            justifyContent: "space-between",
            gap: 16,
            marginBottom: 24,
          }}
        >
          <div>
            <div
              className="font-mono uppercase"
              style={{
                fontSize: "var(--pq-text-eyebrow)",
                letterSpacing: "0.22em",
                color: "var(--pq-bronze)",
                marginBottom: 12,
              }}
            >
              {eyebrow}
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
                margin: 0,
              }}
            >
              Seven questions first.
            </h2>
            <p
              className="font-serif"
              style={{
                fontSize: "var(--pq-text-body)",
                lineHeight: 1.5,
                color: "var(--pq-ivory-mid)",
                margin: "10px 0 0 0",
              }}
            >
              <span style={{ color: "var(--pq-ivory)", fontWeight: 500 }}>
                {displayName}
              </span>{" "}
              <span
                className="font-mono"
                style={{
                  fontSize: "var(--pq-text-eyebrow)",
                  letterSpacing: "0.16em",
                  color: "var(--pq-ivory-dim)",
                }}
              >
                {sideLabel(side)}
              </span>{" "}
              · 조언이 아니라 규율입니다. 기록 전용 — 주문은 넣지 않습니다.
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            disabled={cycle.phase === "cooldown"}
            className="font-mono"
            style={{
              background: "transparent",
              border: "none",
              color:
                cycle.phase === "cooldown"
                  ? "rgba(245,240,232,0.25)"
                  : "rgba(245,240,232,0.55)",
              cursor: cycle.phase === "cooldown" ? "not-allowed" : "pointer",
              padding: 4,
              lineHeight: 0,
            }}
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Body — bare (no numbered SectionLabel) since the modal header
            already frames the step. */}
        {cycle.phase === "questions" && (
          <QuestionsStep
            bare
            acks={acks}
            setAcks={setAcks}
            answers={answers}
            setAnswers={setAnswers}
            allAcked={allAcked}
            submitting={cycle.submitting}
            onStart={cycle.startCooldown}
          />
        )}

        {cycle.phase === "cooldown" && cycle.reflection && (
          <CooldownStep
            bare
            reflection={cycle.reflection}
            submitting={cycle.submitting}
            onProceed={cycle.proceed}
            onCancel={cycle.cancel}
          />
        )}

        {cycle.phase === "terminal" && cycle.reflection && (
          <TerminalStep
            commit={cycle.commit}
            bare
            reflection={cycle.reflection}
            onReset={onClose}
            resetLabel="Close · 닫기"
          />
        )}
      </div>
    </div>
  );
}

export default PreTradeFrictionModal;
