"use client";

/**
 * <SubscriptionCardV2 />
 *
 * Section D of /settings v2 — Subscription tier comparison + receipt strip.
 * Mirror of settings-v2 mockup §810 ("D · Subscription · Stripe").
 *
 * Renders a 3-tier comparison (Free / Pro / Premium):
 *   - current tier card has a bronze border + bronze-04 wash.
 *   - other tiers carry the standard hairline border.
 *
 * Plus a D1 · Receipt 4-col footer card (last invoice / amount / method /
 * receipts → Stripe portal).
 *
 * Pure presentational. Host wires `useSWR(API.billing.subscription)` and the
 * `API.billing.portal` POST → window.location.href = url.
 *
 * Legal: persona vocabulary only. No advice strings.
 */

import * as React from "react";
import Link from "next/link";

interface Tier {
  id: "free" | "pro" | "premium";
  eyebrow: string;
  name: string;
  price: string;
  bullets: string[];
}

const TIERS: Tier[] = [
  {
    id: "free",
    eyebrow: "Tier 1",
    name: "Free",
    price: "KRW 0 / month",
    bullets: [
      "Watchlist · 5 symbols",
      "Weekly memo · read-only",
      "Risk dashboard · 30-day window",
    ],
  },
  {
    id: "pro",
    eyebrow: "Tier 2",
    name: "Pro",
    price: "KRW 9,900 / month",
    bullets: [
      "Unlimited watchlist + alerts",
      "Earnings pre-brief · all holdings",
      "Brag card · monthly · email + PDF",
      "Broker sync · KIS read-only",
      "Persona v3 classifier · 90D window",
    ],
  },
  {
    id: "premium",
    eyebrow: "Tier 3",
    name: "Premium",
    price: "KRW 19,900 / month",
    bullets: [
      "Everything in Pro",
      "Companion · reflective journal agent",
      "Persona v3 · 365D rolling window",
      "Peer benchmark · all cohorts",
      "Priority queue · same-day briefs",
    ],
  },
];

interface Props {
  /** Active tier id. */
  currentTier: "free" | "pro" | "premium";
  /** Render-able renewal copy, e.g. "renews 14 May 2026". */
  renewalLine?: string | null;
  /** Last invoice receipt details. */
  receipt?: {
    date?: string;
    amount?: string;
    method?: string;
  };
  onManageBilling?: () => void;
  onCancel?: () => void;
  /** Pricing page href used by upgrade CTAs. */
  pricingHref?: string;
}

export function SubscriptionCardV2({
  currentTier,
  renewalLine,
  receipt,
  onManageBilling,
  onCancel,
  pricingHref = "/pricing",
}: Props) {
  return (
    // 2026-05-15 (bug-hunter Wave 4 P2 #4): the `id="section-d"` anchor
    // ALSO lives on the outer wrapper in (dashboard)/settings/_v2/
    // page-v2.tsx — emitting it here too produced duplicate IDs in
    // production DOM (HTML standard violation + AnchorRail's
    // getElementById ambiguity that broke "C NOTIFICATIONS" sidebar
    // scroll). The outer page-v2.tsx wrapper retains the id (it's the
    // anchor target); this inner card drops it. aria-label is fine to
    // keep — multiple aria-labels are valid.
    <section
      style={{ scrollMarginTop: 96 }}
      aria-label="Subscription"
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
            D · Subscription · Stripe
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
            The plan you&rsquo;re{" "}
            <span style={{ color: "var(--pq-bronze)", fontStyle: "italic" }}>
              on.
            </span>
          </div>
        </div>
        {/* Free tier has no Stripe subscription to manage — the portal POST
            would 400 (no billing account) or 503 (billing not yet enabled
            pre-launch). Hide the entry point entirely; Free users upgrade via
            the pricing CTAs below instead. */}
        {currentTier !== "free" && (
          <button
            type="button"
            onClick={onManageBilling}
            className="font-mono uppercase"
            style={{
              fontSize: "var(--pq-text-eyebrow)",
              letterSpacing: "0.18em",
              color: "var(--pq-bronze)",
              borderBottom: "1px solid rgba(184,149,106,0.15)",
              paddingBottom: 2,
              background: "transparent",
              border: "none",
              borderBottomStyle: "solid",
              cursor: "pointer",
            }}
          >
            Billing portal ›
          </button>
        )}
      </div>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(3, minmax(0, 1fr))",
          gap: 12,
          marginBottom: 12,
        }}
        className="pq-tier-grid"
      >
        {TIERS.map((t) => {
          const isCurrent = t.id === currentTier;
          const isUpgrade =
            (currentTier === "free" && (t.id === "pro" || t.id === "premium")) ||
            (currentTier === "pro" && t.id === "premium");

          return (
            <div
              key={t.id}
              style={{
                padding: 22,
                border: `1px solid ${
                  isCurrent
                    ? "var(--pq-bronze)"
                    : "var(--pq-ivory-line)"
                }`,
                borderRadius: 2,
                background: isCurrent
                  ? "rgba(184,149,106,0.04)"
                  : "rgba(255,255,255,0.015)",
                position: "relative",
                transition: "border-color 240ms",
                display: "flex",
                flexDirection: "column",
              }}
            >
              <div
                className="font-mono uppercase"
                style={{
                  fontSize: "var(--pq-text-eyebrow)",
                  letterSpacing: "0.22em",
                  color: isCurrent
                    ? "var(--pq-bronze)"
                    : "rgba(245,240,232,0.55)",
                }}
              >
                {isCurrent ? "Current · " : ""}
                {t.eyebrow}
              </div>
              <div
                className="font-display"
                style={{
                  fontWeight: 500,
                  fontSize: "var(--pq-text-avatar)",
                  color: "var(--pq-ivory)",
                  marginTop: 6,
                  letterSpacing: "-0.02em",
                  lineHeight: 1.1,
                }}
              >
                {t.name}
              </div>
              <div
                className="font-mono"
                style={{
                  fontVariantNumeric: "tabular-nums",
                  fontSize: "var(--pq-text-body)",
                  color: "rgba(245,240,232,0.82)",
                  marginTop: 4,
                }}
              >
                {t.price}
                {isCurrent && renewalLine ? <> · {renewalLine}</> : null}
              </div>

              <ul
                style={{
                  marginTop: 14,
                  fontSize: "var(--pq-text-body)",
                  color: "rgba(245,240,232,0.82)",
                  lineHeight: 1.7,
                  listStyle: "none",
                  padding: 0,
                  flex: 1,
                }}
              className="font-serif" >
                {t.bullets.map((b) => (
                  <li
                    key={b}
                    style={{ paddingLeft: 14, position: "relative" }}
                  >
                    <span
                      aria-hidden
                      style={{
                        position: "absolute",
                        left: 0,
                        color: "var(--pq-bronze)",
                        fontWeight: 700,
                      }}
                    >
                      ·
                    </span>
                    {b}
                  </li>
                ))}
              </ul>

              {isCurrent ? (
                currentTier === "free" ? (
                  // Free has no Stripe subscription to manage — a portal CTA
                  // would 400 (no billing account) / 503 (billing disabled).
                  // Show a static "current plan" label instead.
                  <div style={{ marginTop: 20 }}>
                    <span
                      className="font-mono uppercase"
                      style={{
                        fontSize: "var(--pq-text-eyebrow)",
                        letterSpacing: "0.2em",
                        color: "rgba(245,240,232,0.45)",
                      }}
                    >
                      현재 플랜 · Current plan
                    </span>
                  </div>
                ) : (
                <div
                  style={{
                    marginTop: 20,
                    display: "flex",
                    flexWrap: "wrap",
                    gap: 8,
                  }}
                >
                  <button
                    type="button"
                    onClick={onManageBilling}
                    className="font-mono uppercase"
                    style={{
                      display: "inline-flex",
                      alignItems: "center",
                      gap: 10,
                      padding: "11px 20px",
                      background: "transparent",
                      color: "var(--pq-bronze)",
                      border: "1px solid var(--pq-bronze)",
                      fontSize: "var(--pq-text-eyebrow)",
                      letterSpacing: "0.2em",
                      borderRadius: 2,
                      cursor: "pointer",
                    }}
                  >
                    Manage billing
                  </button>
                  {onCancel ? (
                    <button
                      type="button"
                      onClick={onCancel}
                      className="font-mono uppercase"
                      style={{
                        fontSize: "var(--pq-text-eyebrow)",
                        letterSpacing: "0.18em",
                        color: "var(--pq-error, #d18888)",
                        borderBottom: "1px solid rgba(209,136,136,0.30)",
                        paddingBottom: 2,
                        background: "transparent",
                        border: "none",
                        borderBottomStyle: "solid",
                        cursor: "pointer",
                      }}
                    >
                      Cancel plan
                    </button>
                  ) : null}
                </div>
                )
              ) : isUpgrade ? (
                <div style={{ marginTop: 20 }}>
                  <Link
                    href={`${pricingHref}?plan=${t.id}`}
                    className="font-mono uppercase"
                    style={{
                      display: "inline-flex",
                      alignItems: "center",
                      gap: 10,
                      padding: "12px 22px",
                      background: "var(--pq-bronze)",
                      color: "var(--pq-ink, #050505)",
                      fontSize: "var(--pq-text-eyebrow)",
                      letterSpacing: "0.2em",
                      borderRadius: 2,
                      textDecoration: "none",
                    }}
                  >
                    Upgrade to {t.name} →
                  </Link>
                </div>
              ) : null}
            </div>
          );
        })}
      </div>

      {/* D1 · Receipt strip — paid tiers only. A Free user has no invoices
          and the "Open in Stripe" link would hit the portal → 400/503. */}
      {currentTier !== "free" && (
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
          D1 · Receipt
        </span>
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(4, minmax(0, 1fr))",
            gap: 24,
          }}
          className="pq-receipt-grid"
        >
          {[
            { label: "Last invoice", value: receipt?.date ?? "—" },
            { label: "Amount", value: receipt?.amount ?? "—" },
            { label: "Method", value: receipt?.method ?? "—" },
          ].map((cell) => (
            <div key={cell.label}>
              <div
                className="font-mono uppercase"
                style={{
                  fontSize: "var(--pq-text-eyebrow)",
                  letterSpacing: "0.18em",
                  color: "rgba(245,240,232,0.55)",
                }}
              >
                {cell.label}
              </div>
              <div
                className="font-mono"
                style={{
                  fontVariantNumeric: "tabular-nums",
                  fontSize: "var(--pq-text-body)",
                  color: "rgba(245,240,232,0.82)",
                  marginTop: 6,
                }}
              >
                {cell.value}
              </div>
            </div>
          ))}
          <div>
            <div
              className="font-mono uppercase"
              style={{
                fontSize: "var(--pq-text-eyebrow)",
                letterSpacing: "0.18em",
                color: "rgba(245,240,232,0.55)",
              }}
            >
              Receipts
            </div>
            <button
              type="button"
              onClick={onManageBilling}
              className="font-mono uppercase"
              style={{
                marginTop: 6,
                fontSize: "var(--pq-text-eyebrow)",
                letterSpacing: "0.18em",
                color: "var(--pq-bronze)",
                borderBottom: "1px solid rgba(184,149,106,0.15)",
                paddingBottom: 2,
                background: "transparent",
                border: "none",
                borderBottomStyle: "solid",
                cursor: "pointer",
              }}
            >
              Open in Stripe ›
            </button>
          </div>
        </div>
      </div>
      )}

      <style jsx>{`
        @media (max-width: 1023px) {
          :global(.pq-tier-grid) {
            grid-template-columns: 1fr !important;
          }
          :global(.pq-receipt-grid) {
            grid-template-columns: repeat(2, minmax(0, 1fr)) !important;
          }
        }
      `}</style>
    </section>
  );
}

export default SubscriptionCardV2;
