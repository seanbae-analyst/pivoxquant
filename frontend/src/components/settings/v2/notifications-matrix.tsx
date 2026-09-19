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
import { useT } from "@/lib/locale";
import {
  useNotificationPreferences,
  saveNotificationPreferences,
  type NotificationPrefsMap,
} from "@/lib/hooks";
import {
  isMarketDataDisplayEnabled,
  MARKET_DATA_NOTIFICATION_EVENTS,
} from "@/lib/market-display";

// 2026-09-19: `name` / `help` used to be English literals here. This table
// is the one the founder reads every day, so the copy moved to
// settingsV2.notifications.<id>.{name,help} and is resolved through useT at
// render time. The row keeps only what is NOT copy: the event id (which must
// stay aligned with models.user.NOTIFICATION_EVENT_IDS) and the defaults.
interface EventRow {
  id: string;
  defaults: { email: boolean; push: boolean; inapp: boolean };
}

// Must stay aligned with models.user.NOTIFICATION_EVENT_IDS.
//
// 2026-09-01: was seven rows — weekly memo, earnings pre-brief, signal state,
// risk breach, pulse prompt, brag card, broker sync error. Every one of them
// had lost its producer, so Settings let you toggle notifications that could
// never arrive. The two alerts this product does send — the 52-week range
// sweep and the sector-concentration sweep, both scheduled in app.py — mapped
// to no event id at all, so their rows did not exist and their toggles could
// not have worked. These two are what actually fires.
const EVENTS: EventRow[] = [
  {
    id: "price_52w",
    defaults: { email: false, push: true, inapp: true },
  },
  {
    id: "concentration",
    defaults: { email: true, push: true, inapp: true },
  },
  // 2026-09-17: the monthly mirror report. Its only producer is the email
  // cron (services/reports_delivery.py, 매월 1일 08:30 KST), so push and
  // in-app default off and stay off — a channel with nothing behind it is
  // the dead toggle the 2026-09-01 prune removed. Email defaults off too:
  // the report is an INFORMATION-category send under 정통망법 §50, so it
  // is opt-in here as well as consent-gated in the sender.
  {
    id: "monthly_mirror",
    defaults: { email: false, push: false, inapp: false },
  },
];

type Channel = "email" | "push" | "inapp";
type MatrixState = NotificationPrefsMap;

/** Debounce window before a toggle batch is flushed to the server. */
const SAVE_DEBOUNCE_MS = 600;

/**
 * Which rows to render.
 *
 * 2026-09-19: `EVENTS` above is a hardcoded catalog, so a row survived here
 * even after its producer went away on the server — the exact dead-toggle
 * wart the 2026-09-01 prune removed by hand. Two filters replace the hand
 * pruning:
 *
 *   1. The server's own map is the list. Once `prefs` has arrived, an id the
 *      server does not return is not offered. `EVENTS` keeps only what is not
 *      copy and not the server's business: display order and the defaults to
 *      render before the server answers.
 *   2. `price_52w` needs a vendor quote, so it also disappears whenever the
 *      frontend's market-data display flag is off — without waiting for the
 *      server round trip, and so the row never flashes in on first paint.
 */
function visibleEvents(serverPrefs: NotificationPrefsMap | undefined): EventRow[] {
  const marketOk = isMarketDataDisplayEnabled();
  return EVENTS.filter((e) => {
    if (!marketOk && MARKET_DATA_NOTIFICATION_EVENTS.includes(e.id)) {
      return false;
    }
    if (serverPrefs && !(e.id in serverPrefs)) return false;
    return true;
  });
}

function defaultMatrix(): MatrixState {
  const out: MatrixState = {};
  for (const e of visibleEvents(undefined)) {
    out[e.id] = { ...e.defaults };
  }
  return out;
}

function MatrixToggle({
  on,
  onChange,
  ariaLabel,
  disabled = false,
}: {
  on: boolean;
  onChange: (next: boolean) => void;
  ariaLabel: string;
  /** While the server map is still loading, toggles are blocked so a
   *  pre-hydration click can't PUT the hardcoded defaults and wipe the
   *  user's saved custom prefs (backend does a full replace, not a merge). */
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={on}
      aria-label={ariaLabel}
      aria-disabled={disabled}
      disabled={disabled}
      onClick={() => {
        if (disabled) return;
        onChange(!on);
      }}
      style={{
        position: "relative",
        display: "inline-block",
        width: 36,
        height: 20,
        background: on ? "var(--pq-bronze)" : "rgba(245,240,232,0.10)",
        borderRadius: 999,
        transition: "background 200ms, opacity 200ms",
        flexShrink: 0,
        border: "none",
        cursor: disabled ? "not-allowed" : "pointer",
        opacity: disabled ? 0.4 : 1,
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
  const t = useT();
  /** Event copy lives in settingsV2.notifications.<id>.{name,help}. */
  const evName = (id: string) => t(`settingsV2.notifications.${id}.name`);
  const evHelp = (id: string) => t(`settingsV2.notifications.${id}.help`);
  // Render the defaults first (no flash); the server map swaps in on load.
  const [state, setState] = React.useState<MatrixState>(
    () => initial ?? defaultMatrix(),
  );

  // Server is the source of truth. Skip when an explicit `initial` is given.
  const { data, isLoading, mutate } = useNotificationPreferences();

  /** Rows to render — see visibleEvents(). */
  const rows = React.useMemo(() => visibleEvents(data?.prefs), [data]);
  /** Ids the PUT body is allowed to carry (the backend does a full replace,
   *  so an id it no longer knows must not be re-asserted from here). */
  const visibleIds = React.useMemo(
    () => new Set(rows.map((e) => e.id)),
    [rows],
  );

  // Whether we've reflected real server state yet. Until then the rendered
  // matrix is just the hardcoded defaults — a toggle now would PUT those
  // defaults and the backend's full-replace would wipe saved custom prefs.
  // An explicit `initial` (tests / controlled host) counts as hydrated.
  const [hydrated, setHydrated] = React.useState<boolean>(() => !!initial);

  // Hydrate from the server map once it arrives. Merge over the local
  // defaults so a newly-added event still renders if the server hasn't been
  // taught about it yet (defensive — backend contract returns all 7).
  React.useEffect(() => {
    if (initial) return;
    const serverPrefs = data?.prefs;
    if (!serverPrefs) return;
    setState(() => {
      // Rebuild rather than spread over `prev`: an id that has left the
      // server's map must leave the state too, or the next PUT would put it
      // back. `rows` is already server-filtered.
      const merged: MatrixState = {};
      for (const e of rows) {
        merged[e.id] = serverPrefs[e.id] ?? { ...e.defaults };
      }
      return merged;
    });
    setHydrated(true);
  }, [data, initial, rows]);

  // Block toggles until the server map has been applied. `isLoading && !hydrated`
  // covers the initial fetch; `!data && !hydrated` covers the case where SWR
  // resolves to undefined without a loading flag.
  const togglesDisabled = !hydrated && (isLoading || !data);

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
    const body: MatrixState = {};
    for (const [id, channels] of Object.entries(next)) {
      if (visibleIds.has(id)) body[id] = channels;
    }
    saveNotificationPreferences(body)
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
  }, [mutate, visibleIds]);

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
          {rows.map((e, i) => {
            const row = state[e.id] ?? { email: false, push: false, inapp: false };
            const isLast = i === rows.length - 1;
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
                    {evName(e.id)}
                  </div>
                  <div
                    className="font-serif"
                    style={{
                      fontSize: "var(--pq-text-eyebrow)",
                      color: "var(--pq-ivory-dim)",
                      marginTop: 2,
                    }}
                  >
                    {evHelp(e.id)}
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
                      ariaLabel={`${evName(e.id)} · ${ch}`}
                      disabled={togglesDisabled}
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
