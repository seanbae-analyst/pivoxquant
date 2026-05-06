"use client";

/**
 * <NotificationsMatrix />
 *
 * Section C of /settings v2 — 7-event × 3-channel matrix.
 * Mirror of settings-v2 mockup §693 ("C · Notifications · Channels × Events").
 *
 * GAP-E: backend per-event-type matrix endpoint absent. UI surfaces all 7×3
 *        toggles; only push (global) is wired live via the C1 sub-card. The
 *        matrix toggles read+write a `localStorage` shadow-state until the
 *        backend `notification_pref` table lands. See settings-v2/MIGRATION §2.
 *
 * Pure presentational. Host wires push toggle (subscribeToPush /
 * unsubscribeFromPush from `lib/push`) and email-toggle localStorage flag.
 *
 * Legal: persona vocabulary only. POSITIVE / NEGATIVE / NEUTRAL — never BUY/SELL.
 */

import * as React from "react";

interface EventRow {
  id: string;
  name: string;
  help: string;
  defaults: { email: boolean; push: boolean; inapp: boolean };
}

const EVENTS: EventRow[] = [
  {
    id: "weekly_memo",
    name: "Weekly memo · Mon 07:00 KST",
    help: "Drafted weekly editorial brief.",
    defaults: { email: true, push: true, inapp: true },
  },
  {
    id: "earnings_pre_brief",
    name: "Earnings pre-brief",
    help: "Drafted 4 days before any holding's print.",
    defaults: { email: true, push: true, inapp: true },
  },
  {
    id: "signal_state",
    name: "Signal state change",
    help: "POSITIVE / NEGATIVE / NEUTRAL transitions on watchlist.",
    defaults: { email: false, push: true, inapp: true },
  },
  {
    id: "risk_breach",
    name: "Risk layer breach",
    help: "VaR, concentration, correlation, tail, drawdown thresholds.",
    defaults: { email: true, push: true, inapp: true },
  },
  {
    id: "pulse_prompt",
    name: "Pulse prompt · Weekly",
    help: "One reflective question for the Companion.",
    defaults: { email: true, push: false, inapp: true },
  },
  {
    id: "brag_card",
    name: "Brag card · Monthly",
    help: "Shareable performance artifact.",
    defaults: { email: true, push: false, inapp: true },
  },
  {
    id: "broker_sync_error",
    name: "Broker sync error",
    help: "Token refresh, rate-limit, or auth failures.",
    defaults: { email: true, push: true, inapp: true },
  },
];

const LS_KEY = "pq_notif_matrix_v1";

type Channel = "email" | "push" | "inapp";
type MatrixState = Record<string, Record<Channel, boolean>>;

function readMatrix(): MatrixState | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(LS_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as MatrixState;
    return parsed;
  } catch {
    return null;
  }
}

function writeMatrix(state: MatrixState) {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(LS_KEY, JSON.stringify(state));
  } catch {
    /* quota/disabled — silently degrade */
  }
}

function defaultMatrix(): MatrixState {
  const out: MatrixState = {};
  for (const e of EVENTS) {
    out[e.id] = { ...e.defaults };
  }
  return out;
}

function MatrixToggle({
  on,
  onChange,
  ariaLabel,
}: {
  on: boolean;
  onChange: (next: boolean) => void;
  ariaLabel: string;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={on}
      aria-label={ariaLabel}
      onClick={() => onChange(!on)}
      style={{
        position: "relative",
        display: "inline-block",
        width: 36,
        height: 20,
        background: on ? "var(--pq-bronze)" : "rgba(245,240,232,0.10)",
        borderRadius: 999,
        transition: "background 200ms",
        flexShrink: 0,
        border: "none",
        cursor: "pointer",
      }}
    >
      <span
        style={{
          position: "absolute",
          top: 3,
          left: 3,
          width: 14,
          height: 14,
          background: "var(--pq-ivory)",
          borderRadius: 999,
          transition: "transform 200ms",
          transform: on ? "translateX(16px)" : "translateX(0)",
        }}
      />
    </button>
  );
}

interface Props {
  /** Optional initial state override (e.g. for SSR / testing). */
  initial?: MatrixState;
  onChange?: (state: MatrixState) => void;
}

export function NotificationsMatrix({ initial, onChange }: Props) {
  const [state, setState] = React.useState<MatrixState>(
    () => initial ?? defaultMatrix(),
  );

  // Hydrate from localStorage once mounted (GAP-E shadow state).
  React.useEffect(() => {
    if (initial) return;
    const saved = readMatrix();
    if (saved) {
      // Merge to make sure new events get defaults if added later.
      setState((prev) => {
        const merged: MatrixState = { ...prev };
        for (const e of EVENTS) {
          merged[e.id] = saved[e.id] ?? prev[e.id] ?? { ...e.defaults };
        }
        return merged;
      });
    }
  }, [initial]);

  const toggle = React.useCallback(
    (eventId: string, channel: Channel, next: boolean) => {
      setState((prev) => {
        const eventRow = prev[eventId] ?? { email: false, push: false, inapp: false };
        const updated: MatrixState = {
          ...prev,
          [eventId]: {
            ...eventRow,
            [channel]: next,
          },
        };
        writeMatrix(updated);
        onChange?.(updated);
        return updated;
      });
    },
    [onChange],
  );

  return (
    <div
      style={{
        background: "rgba(255,255,255,0.02)",
        border: "1px solid rgba(245,240,232,0.08)",
        borderRadius: 4,
        padding: 0,
        overflowX: "auto",
      }}
    >
      <table
        style={{
          width: "100%",
          borderCollapse: "collapse",
        }}
      >
        <thead>
          <tr>
            <th
              className="font-mono uppercase"
              style={{
                padding: "14px 12px 14px 24px",
                textAlign: "left",
                borderBottom: "1px solid rgba(245,240,232,0.08)",
                fontSize: 9.5,
                letterSpacing: "0.22em",
                color: "var(--pq-bronze)",
                fontWeight: 500,
              }}
            >
              Event
            </th>
            {(["Email", "Push", "In-app"] as const).map((c) => (
              <th
                key={c}
                className="font-mono uppercase"
                style={{
                  padding: "14px 12px",
                  textAlign: "center",
                  borderBottom: "1px solid rgba(245,240,232,0.08)",
                  fontSize: 9.5,
                  letterSpacing: "0.22em",
                  color: "var(--pq-bronze)",
                  fontWeight: 500,
                }}
              >
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {EVENTS.map((e, i) => {
            const row = state[e.id] ?? { email: false, push: false, inapp: false };
            const isLast = i === EVENTS.length - 1;
            return (
              <tr key={e.id}>
                <td
                  style={{
                    padding: "14px 12px 14px 24px",
                    borderBottom: isLast
                      ? "none"
                      : "1px solid rgba(245,240,232,0.08)",
                  }}
                >
                  <div
                    className="font-serif"
                    style={{
                      fontSize: 14,
                      color: "var(--pq-ivory)",
                    }}
                  >
                    {e.name}
                  </div>
                  <div
                    className="font-serif"
                    style={{
                      fontSize: 12,
                      color: "rgba(245,240,232,0.40)",
                      marginTop: 2,
                    }}
                  >
                    {e.help}
                  </div>
                </td>
                {(["email", "push", "inapp"] as const).map((ch) => (
                  <td
                    key={ch}
                    style={{
                      padding: "14px 12px",
                      textAlign: "center",
                      borderBottom: isLast
                        ? "none"
                        : "1px solid rgba(245,240,232,0.08)",
                    }}
                  >
                    <MatrixToggle
                      on={row[ch]}
                      onChange={(next) => toggle(e.id, ch, next)}
                      ariaLabel={`${e.name} · ${ch}`}
                    />
                  </td>
                ))}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export default NotificationsMatrix;
