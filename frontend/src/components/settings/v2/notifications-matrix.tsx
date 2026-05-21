"use client";

/**
 * <NotificationsMatrix />
 *
 * Section C of /settings v2 — 7-event × 3-channel matrix.
 * Mirror of settings-v2 mockup §693 ("C · Notifications · Channels × Events").
 *
 * 2026-05-21 (GAP-E resolved): the backend per-event-type matrix endpoint
 * (`/api/notifications/preferences`) is live. The matrix now loads from the
 * server on mount (SWR), renders the local defaults first to avoid a flash,
 * then swaps in the server map. Toggles update optimistically and persist via
 * a debounced PUT; success/failure surface as a toast and a failed save rolls
 * the row back. The old `localStorage` shadow-state is gone — server is the
 * single source of truth.
 *
 * Legal: persona vocabulary only. POSITIVE / NEGATIVE / NEUTRAL — never BUY/SELL.
 */

import * as React from "react";
import { toast } from "sonner";
import { WEEKLY_MEMO_WHEN_SHORT } from "@/lib/cfo/memo-schedule";
import {
  useNotificationPreferences,
  saveNotificationPreferences,
  type NotificationPrefsMap,
} from "@/lib/hooks";

interface EventRow {
  id: string;
  name: string;
  help: string;
  defaults: { email: boolean; push: boolean; inapp: boolean };
}

const EVENTS: EventRow[] = [
  {
    id: "weekly_memo",
    name: `Weekly memo · ${WEEKLY_MEMO_WHEN_SHORT}`,
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

type Channel = "email" | "push" | "inapp";
type MatrixState = NotificationPrefsMap;

/** Debounce window before a toggle batch is flushed to the server. */
const SAVE_DEBOUNCE_MS = 600;

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
  /** Optional initial state override (e.g. for SSR / testing). When set,
   *  server hydration is skipped — used by tests and any controlled host. */
  initial?: MatrixState;
  onChange?: (state: MatrixState) => void;
}

export function NotificationsMatrix({ initial, onChange }: Props) {
  // Render the defaults first (no flash); the server map swaps in on load.
  const [state, setState] = React.useState<MatrixState>(
    () => initial ?? defaultMatrix(),
  );

  // Server is the source of truth. Skip when an explicit `initial` is given.
  const { data, mutate } = useNotificationPreferences();

  // Hydrate from the server map once it arrives. Merge over the local
  // defaults so a newly-added event still renders if the server hasn't been
  // taught about it yet (defensive — backend contract returns all 7).
  React.useEffect(() => {
    if (initial) return;
    const serverPrefs = data?.prefs;
    if (!serverPrefs) return;
    setState((prev) => {
      const merged: MatrixState = { ...prev };
      for (const e of EVENTS) {
        merged[e.id] = serverPrefs[e.id] ?? prev[e.id] ?? { ...e.defaults };
      }
      return merged;
    });
  }, [data, initial]);

  // Debounced save: collect rapid toggles into one PUT (~600ms). The pending
  // snapshot + the pre-edit snapshot (for rollback) live in refs so the
  // timer closure always flushes the latest state.
  const pendingRef = React.useRef<MatrixState | null>(null);
  const rollbackRef = React.useRef<MatrixState | null>(null);
  const timerRef = React.useRef<ReturnType<typeof setTimeout> | null>(null);

  const flush = React.useCallback(() => {
    const next = pendingRef.current;
    const rollback = rollbackRef.current;
    pendingRef.current = null;
    rollbackRef.current = null;
    if (!next) return;
    saveNotificationPreferences(next)
      .then((res) => {
        // Adopt the server-committed map (defaults merged) without a refetch.
        if (res?.prefs) {
          mutate(res, { revalidate: false });
        }
        toast.success("알림 설정 저장됨");
      })
      .catch((err) => {
        // Roll back to the pre-edit snapshot and surface the failure.
        if (rollback) setState(rollback);
        toast.error(
          err instanceof Error ? err.message : "알림 설정 저장에 실패했습니다.",
        );
      });
  }, [mutate]);

  // Flush any pending save on unmount so a quick navigation doesn't drop it.
  React.useEffect(() => {
    return () => {
      if (timerRef.current) {
        clearTimeout(timerRef.current);
        flush();
      }
    };
  }, [flush]);

  const toggle = React.useCallback(
    (eventId: string, channel: Channel, next: boolean) => {
      setState((prev) => {
        // Capture the snapshot to roll back to only at the start of a batch.
        if (rollbackRef.current === null) rollbackRef.current = prev;
        const eventRow =
          prev[eventId] ?? { email: false, push: false, inapp: false };
        const updated: MatrixState = {
          ...prev,
          [eventId]: { ...eventRow, [channel]: next },
        };
        pendingRef.current = updated;
        onChange?.(updated);
        return updated;
      });
      // (Re)arm the debounce timer.
      if (timerRef.current) clearTimeout(timerRef.current);
      timerRef.current = setTimeout(() => {
        timerRef.current = null;
        flush();
      }, SAVE_DEBOUNCE_MS);
    },
    [onChange, flush],
  );

  return (
    <div
      style={{
        background: "rgba(255,255,255,0.02)",
        border: "1px solid var(--pq-ivory-line)",
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
        <caption className="sr-only">알림 설정</caption>
        <thead>
          <tr>
            <th
              scope="col"
              className="font-mono uppercase"
              style={{
                padding: "14px 12px 14px 24px",
                textAlign: "left",
                borderBottom: "1px solid var(--pq-ivory-line)",
                fontSize: "var(--pq-text-eyebrow)",
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
                scope="col"
                className="font-mono uppercase"
                style={{
                  padding: "14px 12px",
                  textAlign: "center",
                  borderBottom: "1px solid var(--pq-ivory-line)",
                  fontSize: "var(--pq-text-eyebrow)",
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
                      : "1px solid var(--pq-ivory-line)",
                  }}
                >
                  <div
                    className="font-serif"
                    style={{
                      fontSize: "var(--pq-text-body)",
                      color: "var(--pq-ivory)",
                    }}
                  >
                    {e.name}
                  </div>
                  <div
                    className="font-serif"
                    style={{
                      fontSize: "var(--pq-text-eyebrow)",
                      color: "rgba(245,240,232,0.55)",
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
                        : "1px solid var(--pq-ivory-line)",
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
