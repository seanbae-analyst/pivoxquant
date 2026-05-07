"use client";

/**
 * <MarketingConsentCardV2 />
 *
 * Section C3 of /settings v2 — explicit marketing-consent toggle backed
 * by the server record (정통망법 §50 ①).
 *
 * Why this is a dedicated card
 * ----------------------------
 * The §50 ① audit trail must distinguish three states the existing
 * `email_opt_out` boolean cannot:
 *   - never consented      (marketing_consent_at IS NULL)
 *   - currently consented  (consent_at NOT NULL, revoked_at NULL or earlier)
 *   - revoked              (revoked_at >= consent_at)
 * The settings UI surfaces these as a single optimistic toggle, but the
 * card also renders the timestamp so the user can see the legal record
 * we are retaining on their behalf.
 *
 * Wiring
 * ------
 * - Initial state hydrated via `fetchMarketingConsent()` (GET).
 * - Toggle ON  → POST   /api/consents/marketing  (also clears email_opt_out)
 * - Toggle OFF → DELETE /api/consents/marketing  (also sets   email_opt_out)
 * Both calls land in `routes/consents.py` from PR #73. Optimistic UI;
 * on backend failure we revert and toast.
 *
 * Visual layer matches sibling C1/C2 cards (push, email-delivery) verbatim:
 * Vantablack ink, Bronze hairline header, ivory body type — no new tokens.
 */

import * as React from "react";
import { toast } from "sonner";

import {
  fetchMarketingConsent,
  recordMarketingConsent,
  revokeMarketingConsent,
  type MarketingConsentState,
} from "@/lib/consents";

function formatTimestamp(iso: string | null): string | null {
  if (!iso) return null;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return null;
  // Keep the format compatible with the rest of the v2 settings deck:
  // mono digits, lowercase month — see SubscriptionCardV2 / NotificationsMatrix.
  return d.toLocaleString("en-US", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function MarketingConsentCardV2() {
  const [state, setState] = React.useState<MarketingConsentState | null>(null);
  const [loaded, setLoaded] = React.useState(false);
  const [busy, setBusy] = React.useState(false);

  // Hydrate initial state once. We deliberately do NOT use SWR here —
  // the dataset is single-row, single-user, and the toggle drives its
  // own optimistic updates; SWR's revalidate-on-focus would race with
  // the optimistic flip and visibly snap the switch.
  React.useEffect(() => {
    let cancelled = false;
    (async () => {
      const fetched = await fetchMarketingConsent();
      if (cancelled) return;
      setState(
        fetched ?? {
          opted_in: false,
          marketing_consent_at: null,
          marketing_consent_revoked_at: null,
        },
      );
      setLoaded(true);
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const optedIn = state?.opted_in ?? false;
  const stampedAt = formatTimestamp(state?.marketing_consent_at ?? null);
  const revokedAt = formatTimestamp(state?.marketing_consent_revoked_at ?? null);

  const handleToggle = async (next: boolean) => {
    if (busy) return;
    // Optimistic flip — preserves the perceived snappiness of the other
    // C-section toggles. On failure we restore the prior state and
    // surface a toast so the user knows the server didn't take it.
    const prev = state;
    setBusy(true);
    setState((s) => (s ? { ...s, opted_in: next } : s));
    try {
      const updated = next
        ? await recordMarketingConsent()
        : await revokeMarketingConsent();
      setState(updated);
      toast.success(
        next ? "Marketing emails enabled." : "Marketing emails disabled.",
      );
    } catch (err) {
      setState(prev);
      const message =
        err instanceof Error && err.message
          ? err.message
          : "Could not update marketing consent.";
      toast.error(message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div
      style={{
        background: "rgba(255,255,255,0.02)",
        border: "1px solid rgba(245,240,232,0.08)",
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
          fontSize: 12,
          letterSpacing: "0.2em",
          color: "rgba(245,240,232,0.40)",
        }}
      >
        C3 · Marketing
      </span>
      <div
        className="font-mono uppercase"
        style={{
          fontSize: 12,
          letterSpacing: "0.22em",
          color: "var(--pq-bronze)",
          marginBottom: 12,
        }}
      >
        Marketing emails · 정통망법 §50 ①
      </div>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 14,
        }}
      >
        <div style={{ minWidth: 0 }}>
          <div
            className="font-serif"
            style={{
              fontSize: 14,
              color: "var(--pq-ivory)",
            }}
          >
            마케팅 정보 수신 동의
          </div>
          <div
            className="font-serif"
            style={{
              fontSize: 14,
              color: "rgba(245,240,232,0.40)",
              marginTop: 2,
            }}
          >
            이벤트 · 신기능 · 프로모션 안내. 언제든 해제할 수 있습니다.
          </div>
          {loaded && optedIn && stampedAt ? (
            <div
              className="font-mono"
              style={{
                fontVariantNumeric: "tabular-nums",
                fontSize: 12,
                letterSpacing: "0.04em",
                color: "rgba(245,240,232,0.55)",
                marginTop: 8,
              }}
            >
              동의 시각 · {stampedAt}
            </div>
          ) : null}
          {loaded && !optedIn && revokedAt ? (
            <div
              className="font-mono"
              style={{
                fontVariantNumeric: "tabular-nums",
                fontSize: 12,
                letterSpacing: "0.04em",
                color: "rgba(245,240,232,0.55)",
                marginTop: 8,
              }}
            >
              해제 시각 · {revokedAt}
            </div>
          ) : null}
        </div>
        <button
          type="button"
          role="switch"
          aria-checked={optedIn}
          aria-label="Marketing email consent"
          onClick={() => handleToggle(!optedIn)}
          disabled={!loaded || busy}
          style={{
            position: "relative",
            display: "inline-block",
            width: 36,
            height: 20,
            background: optedIn
              ? "var(--pq-bronze)"
              : "rgba(245,240,232,0.10)",
            borderRadius: 999,
            transition: "background 200ms",
            flexShrink: 0,
            border: "none",
            cursor: !loaded || busy ? "not-allowed" : "pointer",
            opacity: !loaded || busy ? 0.5 : 1,
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
              transform: optedIn ? "translateX(16px)" : "translateX(0)",
            }}
          />
        </button>
      </div>
    </div>
  );
}

export default MarketingConsentCardV2;
