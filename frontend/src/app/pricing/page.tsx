"use client";

import { useState, useCallback } from "react";
import Link from "next/link";
import { apiFetch } from "@/lib/api";
import { API } from "@/lib/endpoints";
import { cn } from "@/lib/utils";
import { ErrorBoundary } from "@/components/ui/error-boundary";
import { ModalShell } from "@/components/ui/modal-shell";
import { Check, ChevronDown, ArrowLeft, Info, X as IconClose } from "lucide-react";

/* ── Tier data (3 tiers — matched to landing Pricing section) ── */

type TierKey = "observer" | "operator" | "partner";

interface Tier {
  key: TierKey;
  name: string;
  price: string; // numeric string with thousands separator, no symbol
  unit: string; // "KRW"
  period: string; // "forever" or "per month"
  tagline: string;
  features: string[];
  cta: string;
  dark: boolean;
  recommended: boolean;
  href?: string; // free tier goes straight to /signup
}

const TIERS: Tier[] = [
  {
    key: "observer",
    name: "Observer",
    price: "0",
    unit: "KRW",
    period: "forever",
    tagline: "Read-only observation. 1 artifact per week.",
    features: [
      "Weekly Memo (abridged)",
      "Portfolio observation dashboard",
      "1 broker connection",
    ],
    cta: "Create free account",
    dark: false,
    recommended: false,
    href: "/signup",
  },
  {
    key: "operator",
    name: "Operator",
    price: "9,900",
    unit: "KRW",
    period: "per month",
    tagline: "Full desk access. 17 artifacts. Weekly ship.",
    features: [
      "Everything in Observer",
      "7 Operator artifacts — Morning Brief Plus, Earnings Pre-Brief, DD Checklist, Burn Rate, Credit Rating, AI Suite, Weekly Memo (full)",
      "2 broker connections",
      "Risk Board — 7-layer observation",
    ],
    cta: "Start 7-day trial",
    dark: true,
    recommended: true,
  },
  {
    key: "partner",
    name: "Partner",
    price: "19,900",
    unit: "KRW",
    period: "per month",
    tagline: "Concierge research. Priority renders. Quarterly 1:1 notes.",
    features: [
      "Everything in Operator",
      "10 Partner artifacts — Risk Board Deck, Year-End Letter, Quarterly Self-Report, Capital Allocation, Insider Mirror, Portfolio Segment, Dividend Income, Monthly Finance, Self-Audit, Brag Card",
      "Priority render queue",
      "Quarterly 1:1 desk notes",
    ],
    cta: "Start 7-day trial",
    dark: false,
    recommended: false,
  },
];

/* ── FAQ ── */

interface FaqItem {
  q: string;
  a: string;
}

const FAQ_ITEMS: FaqItem[] = [
  {
    q: "What does a PivoxQuant subscription include?",
    a: "A research desk that writes for you. Observer receives an abridged Weekly Memo. Operator adds the full seventeen-artifact desk — Morning Brief Plus, Earnings Pre-Brief, DD Checklist, Credit Rating, and more, shipped on a weekly cadence. Partner adds ten additional artifacts and priority render queue.",
  },
  {
    q: "Can I cancel at any time?",
    a: "Yes. Cancel from Settings › Subscription at any time. Your plan remains active until the next billing date, then converts automatically to Observer.",
  },
  {
    q: "Is this investment advice?",
    a: "No. PivoxQuant is an informational research tool. Artifacts organize market data, financials, and observation points. We do not solicit or recommend the purchase or sale of any security. All decisions are the user's own.",
  },
  {
    q: "Is VAT included in the price shown?",
    a: "Yes. Prices are displayed in KRW with VAT included. No hidden fees.",
  },
];

/* ── FAQ Accordion ── */

function FaqAccordion({ item }: { item: FaqItem }) {
  const [open, setOpen] = useState(false);
  return (
    <div
      className="border-b"
      style={{ borderColor: "rgba(245,240,232,0.10)" }}
    >
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between py-5 text-left"
        aria-expanded={open}
      >
        <span
          className="font-serif pr-4"
          style={{
            fontSize: "15px",
            color: "var(--pq-ivory)",
            letterSpacing: "-0.005em",
          }}
        >
          {item.q}
        </span>
        <ChevronDown
          className={cn(
            "h-4 w-4 shrink-0 transition-transform duration-200",
            open && "rotate-180",
          )}
          style={{ color: "rgba(245,240,232,0.55)" }}
        />
      </button>
      {open && (
        <p
          className="font-serif pb-5 leading-relaxed"
          style={{
            fontSize: "14px",
            color: "rgba(245,240,232,0.72)",
            lineHeight: 1.7,
          }}
        >
          {item.a}
        </p>
      )}
    </div>
  );
}

/* ── Consent modal (legal — 금소법 §19 + 전자상거래법 §22의2) ── */

const PRICE_LABEL: Record<TierKey, string> = {
  observer: "0 KRW",
  operator: "9,900 KRW",
  partner: "19,900 KRW",
};

function CheckboxBtn({
  checked,
  onChange,
}: {
  checked: boolean;
  onChange: () => void;
}) {
  return (
    <button
      type="button"
      role="checkbox"
      aria-checked={checked}
      onClick={onChange}
      className="mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-sm border transition-all duration-200"
      style={{
        borderColor: checked ? "var(--pq-bronze)" : "rgba(245,240,232,0.30)",
        backgroundColor: checked ? "var(--pq-bronze)" : "transparent",
      }}
    >
      {checked && (
        <svg
          width="10"
          height="10"
          viewBox="0 0 12 12"
          fill="none"
          stroke="#0A0A0A"
          strokeWidth="2.2"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <polyline points="2 6 5 9 10 3" />
        </svg>
      )}
    </button>
  );
}

function ConsentModal({
  tier,
  onClose,
  onConfirm,
  submitting,
}: {
  tier: TierKey;
  onClose: () => void;
  onConfirm: () => void;
  submitting: boolean;
}) {
  const [agreeKey, setAgreeKey] = useState(false);
  const [agreeRecurring, setAgreeRecurring] = useState(false);
  const [agreeStripe, setAgreeStripe] = useState(false);
  const allAgreed = agreeKey && agreeRecurring && agreeStripe;
  const name = TIERS.find((t) => t.key === tier)?.name ?? "";
  const price = PRICE_LABEL[tier];

  return (
    <ModalShell onClose={onClose} ariaLabel="Subscription consent">
      <div
        className="w-full max-w-md overflow-hidden rounded-sm"
        style={{
          backgroundColor: "#0A0A0A",
          border: "1px solid rgba(245,240,232,0.14)",
        }}
      >
        <div
          className="flex items-start justify-between px-6 py-5"
          style={{ borderBottom: "0.5pt solid rgba(245,240,232,0.10)" }}
        >
          <div>
            <h2
              className="font-serif"
              style={{
                fontSize: "16px",
                color: "var(--pq-ivory)",
                letterSpacing: "-0.01em",
              }}
            >
              {name} — confirm subscription
            </h2>
            <p
              className="font-mono tabular-nums mt-1"
              style={{
                fontSize: "11px",
                color: "var(--pq-bronze)",
                letterSpacing: "0.08em",
              }}
            >
              {price} · PER MONTH · VAT INCLUDED
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="rounded-sm p-1 transition-colors"
            style={{ color: "rgba(245,240,232,0.55)" }}
          >
            <IconClose className="h-4 w-4" />
          </button>
        </div>

        <div className="space-y-4 px-6 py-5">
          <label className="flex cursor-pointer items-start gap-3">
            <CheckboxBtn
              checked={agreeKey}
              onChange={() => setAgreeKey((v) => !v)}
            />
            <span
              className="font-serif leading-relaxed"
              style={{ fontSize: "12.5px", color: "rgba(245,240,232,0.80)" }}
            >
              <strong style={{ color: "var(--pq-ivory)" }}>[Required]</strong>{" "}
              I have reviewed the key terms — price, billing period, features,
              refund policy, and cancellation method — and agree to subscribe.
            </span>
          </label>

          <label className="flex cursor-pointer items-start gap-3">
            <CheckboxBtn
              checked={agreeRecurring}
              onChange={() => setAgreeRecurring((v) => !v)}
            />
            <span
              className="font-serif leading-relaxed"
              style={{ fontSize: "12.5px", color: "rgba(245,240,232,0.80)" }}
            >
              <strong style={{ color: "var(--pq-ivory)" }}>[Required]</strong>{" "}
              I agree to automatic monthly billing of {price} until I cancel in
              Settings.
            </span>
          </label>

          <label className="flex cursor-pointer items-start gap-3">
            <CheckboxBtn
              checked={agreeStripe}
              onChange={() => setAgreeStripe((v) => !v)}
            />
            <span
              className="font-serif leading-relaxed"
              style={{ fontSize: "12.5px", color: "rgba(245,240,232,0.80)" }}
            >
              <strong style={{ color: "var(--pq-ivory)" }}>[Required]</strong>{" "}
              I understand that payment is processed by Stripe, Inc. (United
              States), and that card information is transferred and stored
              abroad.
            </span>
          </label>

          <div
            className="mt-2 rounded-sm p-3"
            style={{
              backgroundColor: "rgba(139,111,71,0.08)",
              border: "0.5pt solid rgba(139,111,71,0.25)",
            }}
          >
            <p
              className="font-serif leading-relaxed"
              style={{
                fontSize: "11.5px",
                color: "rgba(245,240,232,0.70)",
              }}
            >
              <Info
                className="inline h-3 w-3 mr-1 -mt-0.5"
                style={{ color: "var(--pq-bronze)" }}
              />
              <strong style={{ color: "var(--pq-ivory)" }}>
                Refund window
              </strong>{" "}
              — Full refund available within 14 days of first payment, regardless of usage. After 14 days the current period is non-refundable and service stops at the next billing date.
            </p>
          </div>
        </div>

        <div
          className="px-6 py-5"
          style={{ borderTop: "0.5pt solid rgba(245,240,232,0.10)" }}
        >
          <button
            type="button"
            disabled={!allAgreed || submitting}
            onClick={onConfirm}
            className="w-full py-3 font-serif transition-all"
            style={{
              fontSize: "13.5px",
              letterSpacing: "0.02em",
              borderRadius: "2px",
              backgroundColor: allAgreed && !submitting
                ? "var(--pq-bronze)"
                : "rgba(245,240,232,0.10)",
              color: allAgreed && !submitting
                ? "var(--pq-ink)"
                : "rgba(245,240,232,0.40)",
              cursor: allAgreed && !submitting ? "pointer" : "not-allowed",
            }}
          >
            {submitting ? "Redirecting…" : "Agree and continue to checkout"}
          </button>
          <p
            className="mt-3 text-center font-mono tabular-nums"
            style={{
              fontSize: "10px",
              letterSpacing: "0.16em",
              color: "rgba(245,240,232,0.40)",
            }}
          >
            PROCESSED BY STRIPE, INC. (UNITED STATES)
          </p>
        </div>
      </div>
    </ModalShell>
  );
}

/* ── Page ── */

export default function PricingPage() {
  const [loadingCheckout, setLoadingCheckout] = useState<TierKey | null>(null);
  const [consentTier, setConsentTier] = useState<TierKey | null>(null);

  const handleCheckout = useCallback((plan: TierKey) => {
    setConsentTier(plan);
  }, []);

  const proceedToCheckout = useCallback(async () => {
    if (!consentTier) return;
    const plan = consentTier;
    setLoadingCheckout(plan);
    try {
      const result = await apiFetch<{ url: string }>(
        API.billing.createCheckout,
        {
          method: "POST",
          body: JSON.stringify({
            plan,
            consent: {
              key_info: true,
              recurring: true,
              stripe_overseas: true,
              consented_at: new Date().toISOString(),
            },
          }),
        },
      );
      if (result.url) {
        window.location.href = result.url;
      }
    } catch {
      window.location.href = "/signup";
    } finally {
      setLoadingCheckout(null);
      setConsentTier(null);
    }
  }, [consentTier]);

  return (
    <ErrorBoundary>
      <div
        className="min-h-screen"
        style={{ backgroundColor: "#0A0A0A", color: "var(--pq-ivory)" }}
      >
        {/* ── Top nav ── */}
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-6">
          <Link
            href="/"
            className="inline-flex items-center gap-2 font-serif transition-opacity hover:opacity-70"
            style={{
              fontSize: "12px",
              letterSpacing: "0.08em",
              color: "rgba(245,240,232,0.55)",
            }}
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            Back to home
          </Link>
        </div>

        {/* ── Hero eyebrow + title ── */}
        <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-12 md:pt-20 pb-16 md:pb-24">
          <div className="max-w-3xl">
            <div className="mb-6 inline-flex items-center gap-2.5">
              <span
                aria-hidden
                className="h-px w-7"
                style={{ backgroundColor: "rgba(139,111,71,0.7)" }}
              />
              <span
                className="font-serif text-[11px] uppercase"
                style={{
                  letterSpacing: "0.22em",
                  color: "var(--pq-bronze)",
                }}
              >
                Membership
              </span>
            </div>

            <h1
              className="font-serif italic mb-6"
              style={{
                fontSize: "clamp(2rem, 4.2vw, 3.25rem)",
                lineHeight: 1.08,
                letterSpacing: "-0.02em",
                fontWeight: 400,
                color: "var(--pq-ivory)",
              }}
            >
              Pick the tier that matches your cadence.
            </h1>

            <p
              className="font-serif"
              style={{
                fontSize: "clamp(15px, 1.3vw, 17px)",
                lineHeight: 1.65,
                color: "rgba(245,240,232,0.65)",
                maxWidth: "56ch",
              }}
            >
              Flat monthly fee. No trading commissions. No performance cut. We
              are never paid when you trade. We are paid when you stay
              subscribed.
            </p>
          </div>
        </section>

        {/* ── Tier Cards (matches landing Pricing section) ── */}
        <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pb-20 md:pb-28">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 md:gap-8 items-stretch">
            {TIERS.map((p) => {
              const isDark = p.dark;
              return (
                <div
                  key={p.key}
                  className="relative rounded-sm p-8 md:p-9 flex flex-col"
                  style={{
                    backgroundColor: isDark ? "#111111" : "var(--pq-ivory)",
                    border: p.recommended
                      ? "1px solid var(--pq-bronze)"
                      : isDark
                        ? "0.5pt solid rgba(245,240,232,0.10)"
                        : "0.5pt solid rgba(10,10,10,0.10)",
                    boxShadow: p.recommended
                      ? "0 40px 80px -40px rgba(139,111,71,0.35)"
                      : "none",
                  }}
                >
                  {p.recommended && (
                    <span
                      className="absolute -top-2.5 left-8 px-2.5 py-[3px] font-serif text-[9.5px] uppercase"
                      style={{
                        backgroundColor: "#0A0A0A",
                        color: "var(--pq-bronze)",
                        letterSpacing: "0.3em",
                        border: "1px solid var(--pq-bronze)",
                        borderRadius: "2px",
                      }}
                    >
                      Most chosen
                    </span>
                  )}

                  {/* Tier name + bronze hairline */}
                  <div className="mb-6 flex items-center gap-3">
                    <span
                      className="font-serif text-[11px] uppercase"
                      style={{
                        letterSpacing: "0.26em",
                        color: "var(--pq-bronze)",
                      }}
                    >
                      {p.name}
                    </span>
                    <span
                      aria-hidden
                      className="h-px flex-1"
                      style={{
                        backgroundColor: p.recommended
                          ? "var(--pq-bronze)"
                          : isDark
                            ? "rgba(245,240,232,0.14)"
                            : "rgba(10,10,10,0.12)",
                        opacity: p.recommended ? 0.9 : 0.6,
                      }}
                    />
                  </div>

                  {/* Price — KRW suffix, no symbol, tabular nums */}
                  <div className="flex items-baseline gap-2 mb-3">
                    <span
                      className="font-mono tabular-nums"
                      style={{
                        fontSize: "clamp(44px, 4.6vw, 56px)",
                        lineHeight: 1,
                        letterSpacing: "-0.03em",
                        fontWeight: 400,
                        color: isDark ? "var(--pq-ivory)" : "var(--pq-ink)",
                      }}
                    >
                      {p.price}
                    </span>
                    <span
                      className="font-serif text-[11px] uppercase"
                      style={{
                        letterSpacing: "0.2em",
                        color: isDark ? "rgba(245,240,232,0.55)" : "#6B6B6B",
                      }}
                    >
                      {p.unit}
                    </span>
                  </div>
                  <p
                    className="font-serif text-[12px] mb-7"
                    style={{
                      color: isDark ? "rgba(245,240,232,0.48)" : "#6B6B6B",
                      letterSpacing: "0.02em",
                    }}
                  >
                    {p.period}
                  </p>

                  {/* Tagline */}
                  <p
                    className="font-serif text-[13px] leading-snug mb-7 pb-6"
                    style={{
                      color: isDark ? "rgba(245,240,232,0.72)" : "#2A2A2A",
                      borderBottom: isDark
                        ? "0.5pt solid rgba(245,240,232,0.10)"
                        : "0.5pt solid rgba(10,10,10,0.08)",
                    }}
                  >
                    {p.tagline}
                  </p>

                  <ul className="space-y-3 mb-10 flex-1">
                    {p.features.map((f) => (
                      <li key={f} className="flex items-start gap-2.5">
                        <Check
                          className="w-3.5 h-3.5 mt-[3px] shrink-0"
                          strokeWidth={2}
                          style={{
                            color: p.recommended
                              ? "var(--pq-bronze)"
                              : isDark
                                ? "var(--pq-ivory)"
                                : "var(--pq-ink)",
                          }}
                        />
                        <span
                          className="font-serif text-[13.5px] leading-snug"
                          style={{
                            color: isDark
                              ? "rgba(245,240,232,0.78)"
                              : "#2A2A2A",
                          }}
                        >
                          {f}
                        </span>
                      </li>
                    ))}
                  </ul>

                  {p.href ? (
                    <Link
                      href={p.href}
                      className="block text-center w-full py-3 px-4 font-serif text-[13.5px] transition-colors"
                      style={{
                        backgroundColor: p.recommended
                          ? "var(--pq-bronze)"
                          : isDark
                            ? "var(--pq-ivory)"
                            : "var(--pq-ink)",
                        color: p.recommended
                          ? "var(--pq-ink)"
                          : isDark
                            ? "var(--pq-ink)"
                            : "var(--pq-ivory)",
                        letterSpacing: "0.02em",
                        borderRadius: "2px",
                      }}
                    >
                      {p.cta}
                    </Link>
                  ) : (
                    <button
                      type="button"
                      onClick={() => handleCheckout(p.key)}
                      className="block text-center w-full py-3 px-4 font-serif text-[13.5px] transition-colors"
                      style={{
                        backgroundColor: p.recommended
                          ? "var(--pq-bronze)"
                          : isDark
                            ? "var(--pq-ivory)"
                            : "var(--pq-ink)",
                        color: p.recommended
                          ? "var(--pq-ink)"
                          : isDark
                            ? "var(--pq-ink)"
                            : "var(--pq-ivory)",
                        letterSpacing: "0.02em",
                        borderRadius: "2px",
                      }}
                    >
                      {loadingCheckout === p.key ? "Loading…" : p.cta}
                    </button>
                  )}
                </div>
              );
            })}
          </div>

          {/* Billing footnote */}
          <p
            className="mt-12 font-serif text-[11px] leading-relaxed"
            style={{ color: "rgba(245,240,232,0.45)" }}
          >
            Billed in KRW. VAT included. Cancel anytime. Informational research
            tool — no trade instructions issued.
          </p>
        </section>

        {/* ── FAQ ── */}
        <section className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 pb-20 md:pb-28">
          <div className="mb-10 inline-flex items-center gap-2.5">
            <span
              aria-hidden
              className="h-px w-7"
              style={{ backgroundColor: "rgba(139,111,71,0.7)" }}
            />
            <span
              className="font-serif text-[11px] uppercase"
              style={{
                letterSpacing: "0.22em",
                color: "var(--pq-bronze)",
              }}
            >
              Frequently asked
            </span>
          </div>

          <h2
            className="font-serif mb-10"
            style={{
              fontSize: "clamp(1.5rem, 2.6vw, 2rem)",
              lineHeight: 1.1,
              letterSpacing: "-0.015em",
              color: "var(--pq-ivory)",
              fontWeight: 400,
            }}
          >
            Questions, answered plainly.
          </h2>

          <div
            className="rounded-sm"
            style={{
              backgroundColor: "#111111",
              border: "0.5pt solid rgba(245,240,232,0.10)",
              padding: "0 24px",
            }}
          >
            {FAQ_ITEMS.map((item) => (
              <FaqAccordion key={item.q} item={item} />
            ))}
          </div>
        </section>

        {/* ── Disclaimer ── */}
        <section className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 pb-24">
          <div
            className="rounded-sm p-5"
            style={{
              backgroundColor: "rgba(139,111,71,0.06)",
              border: "0.5pt solid rgba(139,111,71,0.20)",
            }}
          >
            <p
              className="font-serif leading-relaxed"
              style={{
                fontSize: "11.5px",
                color: "rgba(245,240,232,0.60)",
                lineHeight: 1.7,
              }}
            >
              Past performance does not guarantee future results. PivoxQuant is
              an informational research tool, not an investment adviser.
              Artifacts organize market data and observation points; they do
              not solicit or recommend the purchase or sale of any security.
              All investment decisions are the sole responsibility of the
              user.
            </p>
          </div>
          <p
            className="mt-4 text-center font-mono tabular-nums"
            style={{
              fontSize: "10px",
              letterSpacing: "0.18em",
              color: "rgba(245,240,232,0.35)",
            }}
          >
            PAYMENT PROCESSED BY STRIPE, INC. (UNITED STATES)
          </p>
        </section>

        {consentTier && (
          <ConsentModal
            tier={consentTier}
            onClose={() => setConsentTier(null)}
            onConfirm={proceedToCheckout}
            submitting={loadingCheckout === consentTier}
          />
        )}
      </div>
    </ErrorBoundary>
  );
}
