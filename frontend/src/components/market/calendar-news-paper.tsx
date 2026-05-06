"use client";

/**
 * <CalendarNewsPaper /> — Paper 3 for /market (back sheet).
 *
 * A smaller, tilted side-paper carrying three short sections:
 *   - FX observation (USD/KRW) with staleness marker
 *   - Earnings calendar (upcoming — links to /detail/[ticker])
 *   - Market Pulse (recent observations — placeholder copy retained)
 *
 * Pure presentation. All data comes from the parent page's existing
 * SWR subscriptions. Observational language only. No BUY/SELL/HOLD.
 */

import * as React from "react";

interface EarningsEvent {
  ticker: string;
  name?: string;
  date: string;
}

interface FxStatus {
  label: string;
  rate: number;
  stale: boolean;
  hh: string;
}

interface PulseRow {
  time: string;
  text: string;
}

interface Props {
  fxStatus: FxStatus | null;
  upcomingEarnings: EarningsEvent[];
  pulse: PulseRow[];
  onEarningsClick?: (ticker: string) => void;
}

export function CalendarNewsPaper({
  fxStatus,
  upcomingEarnings,
  pulse,
  onEarningsClick,
}: Props) {
  return (
    <div
      style={{
        padding: "clamp(24px, 3vw, 40px)",
        minHeight: 360,
        display: "flex",
        flexDirection: "column",
        gap: 20,
      }}
    >
      {/* Masthead — dossier side column */}
      <div
        style={{
          borderBottom: "0.5px solid rgba(184,149,106,0.3)",
          paddingBottom: 8,
        }}
      >
        <div className="pq-paper-kicker">The Sidebar</div>
        <h2
          style={{
            fontWeight: 400,
            fontSize: "clamp(1.3rem, 2.2vw, 1.7rem)",
            letterSpacing: "-0.01em",
            color: "#141414",
            margin: "4px 0 2px",
          }}
        className="font-serif" >
          FX, Calendar &amp; Pulse
        </h2>
      </div>

      {/* FX */}
      <section>
        <div className="pq-paper-kicker" style={{ marginBottom: 4 }}>
          FX &middot; USD / KRW
        </div>
        {fxStatus ? (
          <div
            style={{
              display: "flex",
              alignItems: "baseline",
              gap: 10,
              flexWrap: "wrap",
            }}
          >
            <span
              style={{
                fontWeight: 500,
                fontSize: "clamp(1.6rem, 3vw, 2.1rem)",
                color: "#141414",
                fontVariantNumeric: "tabular-nums",
                letterSpacing: "-0.015em",
              }}
            className="font-serif" >
              {fxStatus.rate.toLocaleString("ko-KR", {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2,
              })}
            </span>
            <span
              style={{
                fontSize: 10.5,
                color: "rgba(20,20,20,0.55)",
                textTransform: "uppercase",
                letterSpacing: "0.18em",
                display: "inline-flex",
                alignItems: "center",
                gap: 6,
              }}
            className="font-mono" >
              {fxStatus.stale ? (
                <span
                  aria-label="Stale"
                  title="Rate has not refreshed in over 5 minutes"
                  style={{
                    display: "inline-block",
                    width: 5,
                    height: 5,
                    borderRadius: "50%",
                    background: "#c9a555",
                  }}
                />
              ) : null}
              <span>{fxStatus.label}</span>
              {fxStatus.stale ? <span>&middot; stale</span> : null}
            </span>
          </div>
        ) : (
          <p
            className="pq-paper-body"
            style={{ fontSize: 13 }}
          >
            No FX observation available.
          </p>
        )}
      </section>

      {/* Earnings calendar */}
      <section
        style={{
          borderTop: "0.5px solid rgba(184,149,106,0.22)",
          paddingTop: 14,
        }}
      >
        <div className="pq-paper-kicker" style={{ marginBottom: 8 }}>
          This Week &middot; Earnings Calendar
        </div>
        {upcomingEarnings.length === 0 ? (
          <p
            className="pq-paper-body"
            style={{ fontSize: 12.5 }}
          >
            No scheduled events in the window.
          </p>
        ) : (
          <div>
            {upcomingEarnings.map((e, i) => (
              <button
                key={`${e.ticker}-${i}`}
                type="button"
                onClick={() => onEarningsClick?.(e.ticker)}
                style={{
                  display: "grid",
                  gridTemplateColumns: "auto auto 1fr auto",
                  alignItems: "baseline",
                  gap: 10,
                  width: "100%",
                  padding: "10px 2px",
                  borderBottom: "0.5px solid rgba(184,149,106,0.22)",
                  background: "transparent",
                  border: 0,
                  borderBottomWidth: 0.5,
                  borderBottomStyle: "solid",
                  borderBottomColor: "rgba(184,149,106,0.22)",
                  cursor: onEarningsClick ? "pointer" : "default",
                  textAlign: "left",
                  transition: "background-color 220ms ease",
                }}
                onMouseEnter={(ev) =>
                  (ev.currentTarget.style.backgroundColor =
                    "rgba(184,149,106,0.08)")
                }
                onMouseLeave={(ev) =>
                  (ev.currentTarget.style.backgroundColor = "transparent")
                }
              >
                <span
                  aria-hidden
                  style={{
                    display: "inline-block",
                    width: 4,
                    height: 4,
                    borderRadius: "50%",
                    background: "var(--pq-bronze, #B8956A)",
                    opacity: 0.75,
                    transform: "translateY(-2px)",
                  }}
                />
                <span
                  style={{
                    fontVariantNumeric: "tabular-nums",
                    fontSize: 10.5,
                    color: "var(--pq-bronze, #B8956A)",
                    letterSpacing: "0.1em",
                    textTransform: "uppercase",
                  }}
                className="font-mono" >
                  {new Date(e.date).toLocaleDateString(undefined, {
                    month: "short",
                    day: "numeric",
                  })}
                </span>
                <span
                  style={{
                    fontSize: 12.5,
                    color: "#1a1a1a",
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    whiteSpace: "nowrap",
                  }}
                className="font-serif" >
                  {e.name || e.ticker}
                </span>
                <span
                  style={{
                    fontSize: 9.5,
                    textTransform: "uppercase",
                    letterSpacing: "0.18em",
                    color: "rgba(20,20,20,0.55)",
                  }}
                className="font-mono" >
                  {e.ticker}
                </span>
              </button>
            ))}
          </div>
        )}
      </section>

      {/* Market Pulse */}
      <section
        style={{
          borderTop: "0.5px solid rgba(184,149,106,0.22)",
          paddingTop: 14,
        }}
      >
        <div className="pq-paper-kicker" style={{ marginBottom: 8 }}>
          Market Pulse &middot; Recent Observations
        </div>
        <div>
          {pulse.length > 0 ? (
            pulse.map((row) => (
              <div
                key={row.time}
                style={{
                  display: "grid",
                  gridTemplateColumns: "auto 1fr",
                  alignItems: "baseline",
                  gap: 10,
                  padding: "9px 0",
                  borderBottom: "0.5px solid rgba(184,149,106,0.18)",
                }}
              >
                <span
                  style={{
                    fontVariantNumeric: "tabular-nums",
                    fontSize: 10.5,
                    color: "var(--pq-bronze, #B8956A)",
                    letterSpacing: "0.08em",
                  }}
                className="font-mono" >
                  {row.time}
                </span>
                <p
                  style={{
                    fontSize: 12.5,
                    lineHeight: 1.5,
                    color: "rgba(20,20,20,0.78)",
                    margin: 0,
                  }}
                className="font-serif" >
                  {row.text}
                </p>
              </div>
            ))
          ) : (
            <p
              style={{
                fontSize: 12,
                fontStyle: "italic",
                color: "rgba(20,20,20,0.5)",
                margin: "8px 0 0",
              }}
            className="font-serif" >
              No recent pulse observations available.
            </p>
          )}
        </div>
      </section>
    </div>
  );
}

export default CalendarNewsPaper;
