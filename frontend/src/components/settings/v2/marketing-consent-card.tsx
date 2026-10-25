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
 * - Toggle ON  → POST   /api/consents/marketing
 * - Toggle OFF → DELETE /api/consents/marketing
 * Both calls land in `routes/consents.py` from PR #73. Optimistic UI;
 * on backend failure we revert and toast. 2026-09-29: neither call touches
 * `email_opt_out` any more — that is the B2 email-delivery toggle's switch.
 * `onConsentChange` reports the effective opt-in (after hydration and after
 * every committed toggle) so the notifications matrix can say when this
 * card is what keeps the monthly report from being sent.
 *
 * Visual layer matches sibling C1/C2 cards (push, email-delivery) verbatim:
 * Vantablack ink, Bronze hairline header, ivory body type — no new tokens.
 */

import * as React from "react";
import { toast } from "sonner";

import {
  INFORMATION_CONSENT_ANCHOR,
  MARKETING_CONSENT_ANCHOR,
} from "@/components/settings/v2/notifications-matrix";
import {
  fetchInformationConsent,
  fetchMarketingConsent,
  recordMarketingConsent,
  revokeMarketingConsent,
  setInformationConsent,
  type MarketingConsentState,
} from "@/lib/consents";

function formatTimestamp(iso: string | null): string | null {
  if (!iso) return null;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return null;
  // Korean date-time (2026-10-07 — was en-US "07 Oct 2026, 03:12 PM").
  return d.toLocaleString("ko-KR", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

/** One consent record, normalised so both §50 categories share the card. */
interface ConsentRecord {
  opted_in: boolean;
  consent_at: string | null;
  revoked_at: string | null;
}

interface ConsentCopy {
  anchor: string;
  tag: string;
  eyebrow: string;
  title: string;
  help: string;
  ariaLabel: string;
  toastOn: string;
  toastOff: string;
  toastFail: string;
}

function ConsentToggleCard({
  copy,
  load,
  save,
  onConsentChange,
}: {
  copy: ConsentCopy;
  load: () => Promise<ConsentRecord | null>;
  save: (next: boolean) => Promise<ConsentRecord>;
  onConsentChange?: (optedIn: boolean) => void;
}) {
  const [state, setState] = React.useState<ConsentRecord | null>(null);
  const [loaded, setLoaded] = React.useState(false);
  const [busy, setBusy] = React.useState(false);

  // Hydrate initial state once. We deliberately do NOT use SWR here —
  // the dataset is single-row, single-user, and the toggle drives its
  // own optimistic updates; SWR's revalidate-on-focus would race with
  // the optimistic flip and visibly snap the switch.
  React.useEffect(() => {
    let cancelled = false;
    (async () => {
      const fetched = await load();
      if (cancelled) return;
      setState(fetched ?? { opted_in: false, consent_at: null, revoked_at: null });
      setLoaded(true);
    })();
    return () => {
      cancelled = true;
    };
    // `load` is a module-level function per card — hydrate once.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const optedIn = state?.opted_in ?? false;

  // Report the committed state (not the optimistic flip) to the host.
  React.useEffect(() => {
    if (loaded && !busy) onConsentChange?.(optedIn);
  }, [loaded, busy, optedIn, onConsentChange]);
  const stampedAt = formatTimestamp(state?.consent_at ?? null);
  const revokedAt = formatTimestamp(state?.revoked_at ?? null);

  const handleToggle = async (next: boolean) => {
    if (busy) return;
    // Optimistic flip — preserves the perceived snappiness of the other
    // C-section toggles. On failure we restore the prior state and
    // surface a toast so the user knows the server didn't take it.
    const prev = state;
    setBusy(true);
    setState((s) => (s ? { ...s, opted_in: next } : s));
    try {
      const updated = await save(next);
      setState(updated);
      toast.success(next ? copy.toastOn : copy.toastOff);
    } catch (err) {
      setState(prev);
      const message =
        err instanceof Error && err.message
          ? err.message
          : copy.toastFail;
      toast.error(message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div
      id={copy.anchor}
      style={{
        background: "rgba(255,255,255,0.02)",
        border: "1px solid var(--pq-ivory-line)",
        borderRadius: "var(--pq-radius-card)",
        padding: 24,
        position: "relative",
        scrollMarginTop: 96,
      }}
    >
      <span
        className="font-mono"
        style={{
          position: "absolute",
          top: 14,
          right: 14,
          fontSize: "var(--pq-text-eyebrow)",
          color: "var(--pq-ivory-dim)",
        }}
      >
        {copy.tag}
      </span>
      <div
        className="font-mono"
        style={{
          fontSize: "var(--pq-text-eyebrow)",
          color: "var(--pq-bronze)",
          marginBottom: 12,
        }}
      >
        {copy.eyebrow}
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
              fontSize: "var(--pq-text-body)",
              color: "var(--pq-ivory)",
            }}
          >
            {copy.title}
          </div>
          <div
            className="font-serif"
            style={{
              fontSize: "var(--pq-text-body)",
              color: "var(--pq-ivory-dim)",
              marginTop: 2,
            }}
          >
            {copy.help}
          </div>
          {loaded && optedIn && stampedAt ? (
            <div
              className="font-mono"
              style={{
                fontVariantNumeric: "tabular-nums",
                fontSize: "var(--pq-text-eyebrow)",
                letterSpacing: "0.04em",
                color: "var(--pq-ivory-dim)",
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
                fontSize: "var(--pq-text-eyebrow)",
                letterSpacing: "0.04em",
                color: "var(--pq-ivory-dim)",
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
          aria-label={copy.ariaLabel}
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

const fromMarketing = (s: MarketingConsentState): ConsentRecord => ({
  opted_in: s.opted_in,
  consent_at: s.marketing_consent_at,
  revoked_at: s.marketing_consent_revoked_at,
});

const MARKETING_COPY: ConsentCopy = {
  anchor: MARKETING_CONSENT_ANCHOR,
  tag: "마케팅",
  eyebrow: "마케팅 메일 · 정통망법 §50 ①",
  title: "마케팅 정보 수신 동의",
  help: "이벤트 · 신기능 · 프로모션 안내. 언제든 해제할 수 있습니다.",
  ariaLabel: "마케팅 메일 수신 동의",
  toastOn: "마케팅 메일 수신에 동의했습니다.",
  toastOff: "마케팅 메일 수신 동의를 철회했습니다.",
  toastFail: "마케팅 수신 동의를 바꾸지 못했습니다.",
};

async function loadMarketing(): Promise<ConsentRecord | null> {
  const fetched = await fetchMarketingConsent();
  return fetched ? fromMarketing(fetched) : null;
}

async function saveMarketing(next: boolean): Promise<ConsentRecord> {
  return fromMarketing(next ? await recordMarketingConsent() : await revokeMarketingConsent());
}

export function MarketingConsentCardV2({
  onConsentChange,
}: {
  /** Effective opt-in, reported after hydration and after each committed toggle. */
  onConsentChange?: (optedIn: boolean) => void;
} = {}) {
  return (
    <ConsentToggleCard
      copy={MARKETING_COPY}
      load={loadMarketing}
      save={saveMarketing}
      onConsentChange={onConsentChange}
    />
  );
}

/**
 * 정보성 메일 (정통망법 §50 ① 분리 동의, 2026-10-22). The monthly mirror
 * report answers to this record alone (services/email/sender.py); before it
 * existed nothing ever wrote the record, so the report reached nobody while
 * the settings page said when it would arrive.
 */
const INFORMATION_COPY: ConsentCopy = {
  anchor: INFORMATION_CONSENT_ANCHOR,
  tag: "정보성",
  eyebrow: "정보성 메일 · 정통망법 §50 ①",
  title: "정보성 메일 수신 동의",
  help: "월간 거울 리포트처럼 내 기록을 정리해 보내는 메일입니다. 광고성 메일과 따로 받으며, 언제든 해제할 수 있습니다.",
  ariaLabel: "정보성 메일 수신 동의",
  toastOn: "정보성 메일 수신에 동의했습니다.",
  toastOff: "정보성 메일 수신 동의를 철회했습니다.",
  toastFail: "정보성 수신 동의를 바꾸지 못했습니다.",
};

export function InformationConsentCardV2({
  onConsentChange,
}: {
  onConsentChange?: (optedIn: boolean) => void;
} = {}) {
  return (
    <ConsentToggleCard
      copy={INFORMATION_COPY}
      load={fetchInformationConsent}
      save={setInformationConsent}
      onConsentChange={onConsentChange}
    />
  );
}

export default MarketingConsentCardV2;
