"use client";

/**
 * <ObservationNoteModalV2 /> — write a 관찰 노트 about one holding.
 *
 * docs/design/observation-notes_2026-09-22.md §5 진입점: the second of the
 * two v1 entry points (the first is the /journal composer). Opened from a
 * holdings row, so the symbol is already known and pre-filled.
 *
 * This is a plain record surface. It does not read a quote, it does not
 * touch the position, and it is NOT the pre-trade flow: adding to or
 * trimming a position still goes through Add / Trim, which own the seven
 * questions. Writing something down about a holding is not a trade
 * decision, which is exactly why it is allowed to be this cheap.
 *
 * Shell: <Sheet /> with the same desktop chrome as <AddPositionModalV2 />
 * (focus trap, Escape, backdrop) so /portfolio has one modal language. On a
 * phone it is a bottom sheet with a header close button, drag-to-dismiss and
 * back-button close; the composer's textarea is not autofocused on touch
 * (the keyboard would cover the sheet before the user asked for it).
 */

import * as React from "react";
import { toast } from "sonner";
import { Sheet, type SheetHandle } from "@/components/ui/sheet";
import { displayTicker } from "@/lib/format";
import { ObservationNoteComposer } from "@/components/journal/observation-note-composer";

export interface ObservationNoteModalV2Props {
  open: boolean;
  /** The holding this note is about. Null renders nothing. */
  symbol: string | null;
  /** Resolved company name for the headline (falls back to the symbol). */
  name?: string | null;
  onClose: () => void;
}

export function ObservationNoteModalV2({
  open,
  symbol,
  name,
  onClose,
}: ObservationNoteModalV2Props) {
  const headlineId = "obs-note-v2-headline";
  const sheetRef = React.useRef<SheetHandle>(null);
  const close = React.useCallback(() => {
    if (sheetRef.current) sheetRef.current.dismiss();
    else onClose();
  }, [onClose]);

  if (!symbol) return null;

  const heading = displayTicker(symbol, name ?? "");

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
        // 16px side gutter holds the dialog off the bezel on a 375px phone.
        padding: "10vh 16px calc(24px + env(safe-area-inset-bottom, 0px))",
        overflowY: "auto",
      }}
      desktopPanelStyle={{
        width: "100%",
        maxWidth: 560,
        background: "rgba(184,149,106,0.025)",
        border: "1px solid var(--pq-hairline-ink, var(--pq-ivory-line))",
        borderRadius: "var(--pq-radius-card, 4px)",
        padding: "32px 24px",
        color: "var(--pq-ivory)",
      }}
    >
        <div style={{ marginBottom: 20 }}>
          <div
            className="font-mono"
            style={{
              fontSize: "var(--pq-text-eyebrow)",
              letterSpacing: "0.02em",
              color: "var(--pq-bronze)",
              marginBottom: 8,
            }}
          >
            관찰 노트
          </div>
          <h2
            id={headlineId}
            className="font-display"
            style={{
              fontSize: "var(--pq-text-h3)",
              lineHeight: 1.15,
              fontWeight: 500,
              letterSpacing: "-0.015em",
              margin: 0,
            }}
          >
            {heading}
          </h2>
        </div>

        <ObservationNoteComposer
          compact
          source="portfolio"
          defaultTickers={[symbol]}
          onCreated={() => {
            // Same confirmation channel the Add / Trim modals use.
            toast.success("관찰 노트를 기록했습니다.");
            close();
          }}
        />

        {/* Phone has the header close + drag; this stays for desktop. */}
        <div className="max-md:hidden" style={{ marginTop: 16, textAlign: "right" }}>
          <button
            type="button"
            onClick={close}
            className="font-mono"
            style={{
              background: "transparent",
              border: "1px solid var(--pq-ivory-line)",
              borderRadius: "var(--pq-radius-cta, 2px)",
              color: "var(--pq-ivory-dim)",
              fontSize: "var(--pq-text-eyebrow)",
              letterSpacing: "0.02em",
              padding: "8px 18px",
              cursor: "pointer",
            }}
          >
            닫기
          </button>
        </div>
    </Sheet>
  );
}

export default ObservationNoteModalV2;
