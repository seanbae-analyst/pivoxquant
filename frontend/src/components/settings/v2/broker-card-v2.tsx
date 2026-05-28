"use client";

/**
 * <BrokerCardV2 />
 *
 * Section B (Brokers) shell for /settings v2.
 * Mirror of settings-v2 mockup §615 ("B · Brokers · Read-only stream").
 *
 * Renders:
 *   - Section header (eyebrow + Playfair H2 + "2 of 2 supported" pill)
 *   - BYOK editorial deck — "PivoxQuant operates brokers on a Bring-Your-Own-Key model"
 *   - Broker card slot (children) — host wires the KIS v1 component verbatim
 *     (KisCard) per CEO 2026-04-28 (current prod model: BYOK + read-only).
 *
 * Pure presentational shell. Host renders the live broker cards inside.
 *
 * Legal: read-only stance reinforced. No order routing language.
 */

import * as React from "react";

interface Props {
  /** Slot for the live KIS card. */
  kisSlot?: React.ReactNode;
  /** Optional override for the supported-count pill in the header. */
  supportedLabel?: string;
}

export function BrokerCardV2({
  kisSlot,
  supportedLabel = "1 of 1 supported",
}: Props) {
  return (
    <section
      style={{ scrollMarginTop: 96 }}
      aria-label="Brokers"
    >
      <div
        style={{
          display: "flex",
          alignItems: "flex-end",
          justifyContent: "space-between",
          marginBottom: 16,
          flexWrap: "wrap",
          gap: 12,
        }}
      >
        <div>
          <div
            className="font-mono uppercase"
            style={{
              fontSize: "var(--pq-text-eyebrow)",
              letterSpacing: "0.22em",
              color: "var(--pq-bronze)",
              marginBottom: 8,
            }}
          >
            B · Brokers · Read-only stream
          </div>
          <div
            className="font-display"
            style={{
              fontWeight: 500,
              fontSize: "var(--pq-text-h3)",
              lineHeight: 1.15,
              letterSpacing: "-0.02em",
              color: "var(--pq-ivory)",
            }}
          >
            Where your{" "}
            <span style={{ color: "var(--pq-bronze)" }}>
              book lives.
            </span>
          </div>
        </div>
        <span
          className="font-mono uppercase"
          style={{
            fontSize: "var(--pq-text-eyebrow)",
            letterSpacing: "0.22em",
            color: "rgba(245,240,232,0.55)",
          }}
        >
          {supportedLabel}
        </span>
      </div>

      <p
        className="font-serif"
        style={{
          fontSize: "var(--pq-text-body)",
          lineHeight: 1.55,
          color: "rgba(245,240,232,0.82)",
          maxWidth: 720,
          marginBottom: 20,
        }}
      >
        PivoxQuant operates brokers on a{" "}
        <span style={{ color: "var(--pq-bronze)" }}>
          Bring-Your-Own-Key
        </span>{" "}
        model. We forward read-only requests under your own license — we never
        place orders, never store live trading credentials.
      </p>

      <div
        style={{
          display: "flex",
          flexDirection: "column",
          gap: 12,
        }}
      >
        {/* B1 · KIS */}
        <div
          style={{
            background: "rgba(255,255,255,0.02)",
            border: "1px solid var(--pq-ivory-line)",
            borderRadius: 4,
            padding: 24,
            position: "relative",
          }}
        >
          <span
            className="font-mono uppercase"
            style={{
              position: "absolute",
              top: 14,
              right: 14,
              fontSize: "var(--pq-text-eyebrow)",
              letterSpacing: "0.2em",
              color: "rgba(245,240,232,0.55)",
            }}
          >
            B1 · KIS · BYOK
          </span>
          {kisSlot ?? (
            <p
              className="font-serif"
              style={{
                fontSize: "var(--pq-text-body)",
                color: "rgba(245,240,232,0.55)",
              }}
            >
              KIS surface unavailable in this environment.
            </p>
          )}

          <p
            className="font-serif"
            style={{
              fontSize: "var(--pq-text-body)",
              color: "rgba(245,240,232,0.55)",
              marginTop: 16,
            }}
          >
            KIS read-only · 국내 + 해외주식 (NASDAQ / NYSE / AMEX). Order
            routing is permanently disabled. You enter your{" "}
            <span
              className="font-mono"
              style={{
                fontVariantNumeric: "tabular-nums",
              }}
            >
              App Key
            </span>
            ,{" "}
            <span
              className="font-mono"
              style={{
                fontVariantNumeric: "tabular-nums",
              }}
            >
              App Secret
            </span>
            , and{" "}
            <span
              className="font-mono"
              style={{
                fontVariantNumeric: "tabular-nums",
              }}
            >
              계좌번호
            </span>{" "}
            in the connect modal; we encrypt at rest.
          </p>
        </div>
      </div>
    </section>
  );
}

export default BrokerCardV2;
