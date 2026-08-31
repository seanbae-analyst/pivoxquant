"use client";

import { useState, useCallback, useEffect } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { toast } from "sonner";
import { apiFetch, ApiError } from "@/lib/api";
import { API } from "@/lib/endpoints";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";
import { ErrorBoundary } from "@/components/ui/error-boundary";
import { ModalShell } from "@/components/ui/modal-shell";
import { Check, ChevronDown, ArrowLeft, Info, X as IconClose } from "lucide-react";

/* ── PriceCountUp ──────────────────────────────────────────────────────────
   STATIC price display — NEVER animate currency.

   Audit FINDING-007: this used to scroll-trigger a 0 → target count-up over
   ~1.4s. A user landing on the page mid-animation saw an inaccurate price
   for the same product — a contractual misrepresentation, not a decoration
   (§6 forbids decorative motion; 표시광고법 §3 forbids misleading price
   representation). The "premium reveal" feel now lives on the CARD
   (opacity / translate), not the digit content.

   The component name is kept so callsites don't churn; it now simply
   renders the locale-formatted value. SSR renders the raw `value` (already
   thousand-separated in TIERS) so server + client markup agree; an effect
   normalizes to the locale string post-hydration without ever animating.
   ─────────────────────────────────────────────────────────────────────── */
function PriceCountUp({
  value,
  locale = "ko-KR",
}: {
  value: string; // e.g. "0" | "9,900" | "19,900"
  locale?: string;
}) {
  const target = Number(value.replace(/[^0-9.-]/g, ""));
  // SSR-safe: start with the raw prop, normalize to locale string after mount.
  const [display, setDisplay] = useState<string>(value);

  useEffect(() => {
    setDisplay(Number.isFinite(target) ? target.toLocaleString(locale) : value);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value]);

  return <span>{display}</span>;
}

/* ── Tier data (3 tiers — matched to landing Pricing section) ── */

type TierKey = "free" | "pro" | "premium";

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

// Tier SoT: frontend/src/content/terms-ko.md §8.1 (Free / Pro / Premium).
// 2026-04-27: tier names consolidated from Observer/Operator/Partner to
// Free/Pro/Premium per legal review (4-way mismatch with terms-ko.md fixed).
const TIERS: Tier[] = [
  {
    key: "free",
    name: "Free",
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
    key: "pro",
    name: "Pro",
    price: "9,900",
    unit: "KRW",
    period: "per month",
    tagline: "Full desk access. 11 artifacts. Weekly ship.",
    features: [
      "Everything in Free",
      // 표시광고 정직성 (2026-06-11 B2 후속): 전 티어 무료인 것(S&P 500
      // Backtest, Brag Card)은 유료 카드의 perk 로 표기하지 않는다 —
      // tests/test_artifact_tier_alignment.py 의 SoT 와 동기.
      "Pro artifacts — Morning Brief Plus, Earnings Pre-Brief, DD Checklist, Insider Mirror, Risk Board, Dividend Income, Quarterly Self-Report, Self-Audit, Portfolio Segment, AI Assistant, Weekly Memo (full)",
      "2 broker connections",
      "Risk Board — 7-layer observation",
    ],
    cta: "Pre-register · Stripe 활성화 시 결제",
    dark: true,
    recommended: true,
  },
  {
    key: "premium",
    name: "Premium",
    price: "19,900",
    unit: "KRW",
    period: "per month",
    tagline: "Concierge research. Priority renders. Year-end letter.",
    features: [
      "Everything in Pro",
      "Premium artifacts — Capital Allocation, Credit Rating, Burn Rate, Monthly Finance, KPI Dashboard, Year-End Letter",
      "Priority render queue",
      "Unlimited broker connections",
    ],
    cta: "Pre-register · Stripe 활성화 시 결제",
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
    a: "A research desk that writes for you. Free receives an abridged Weekly Memo. Pro adds the full eleven Pro artifacts — Morning Brief Plus, Earnings Pre-Brief, DD Checklist, Insider Mirror, Risk Board, and more, shipped on a weekly cadence. Premium adds six additional Premium artifacts including Year-End Letter and priority render queue.",
  },
  {
    q: "Can I cancel at any time?",
    a: "Yes. Cancel from Settings › Subscription at any time. Your plan remains active until the next billing date, then converts automatically to Free.",
  },
  {
    q: "Is this investment advice? (Disclaimer: it is not.)",
    a: "No. PivoxQuant is an informational research tool. Artifacts organize market data, financials, and observation points. We do not solicit or suggest the purchase or sale of any security. All decisions are the user's own.",
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
            fontSize: "var(--pq-text-lead)",
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
            fontSize: "var(--pq-text-body)",
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
  free: "0 KRW",
  pro: "9,900 KRW",
  premium: "19,900 KRW",
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
        borderColor: checked ? "var(--pq-bronze)" : "rgba(245,240,232,0.55)",
        backgroundColor: checked ? "var(--pq-bronze)" : "transparent",
      }}
    >
      {checked && (
        <svg
          width="10"
          height="10"
          viewBox="0 0 12 12"
          fill="none"
          stroke="#050505"
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
          backgroundColor: "#050505",
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
                fontSize: "var(--pq-text-h6)",
                color: "var(--pq-ivory)",
                letterSpacing: "-0.01em",
              }}
            >
              {name} — confirm subscription
            </h2>
            <p
              className="font-mono tabular-nums mt-1"
              style={{
                fontSize: "var(--pq-text-eyebrow)",
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
              style={{ fontSize: "var(--pq-text-body)", color: "rgba(245,240,232,0.80)" }}
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
              style={{ fontSize: "var(--pq-text-body)", color: "rgba(245,240,232,0.80)" }}
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
              style={{ fontSize: "var(--pq-text-body)", color: "rgba(245,240,232,0.80)" }}
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
              backgroundColor: "rgba(var(--pq-bronze-wash-rgb),0.08)",
              border: "0.5pt solid rgba(var(--pq-bronze-wash-rgb),0.25)",
            }}
          >
            <p
              className="font-serif leading-relaxed"
              style={{
                fontSize: "var(--pq-text-eyebrow)",
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
              — 14-day refund period from first payment for the unused portion of your subscription. Per terms §17 and 전자상거래법 §17 ②⑤, refund may be restricted once digital content (artifacts, reports) has been delivered or accessed. After 14 days the current period is non-refundable and service stops at the next billing date.
            </p>
          </div>
        </div>

        <div
          className="px-6 py-5"
          style={{ borderTop: "0.5pt solid rgba(245,240,232,0.10)" }}
        >
          {/* Bug #10 (P2): the CTA used to sit `disabled` with no inline
              copy explaining why a click did nothing — users tried it,
              got silence, and assumed the page was broken. Tally the
              outstanding required checkboxes and surface the count via
              aria-live so screen readers + sighted users both learn the
              exact gate condition. */}
          {!allAgreed && (
            <p
              aria-live="polite"
              role="status"
              className="mb-3 text-center font-serif"
              style={{
                fontSize: "var(--pq-text-eyebrow)",
                color: "rgba(245,240,232,0.55)",
                letterSpacing: "0.04em",
              }}
            >
              {`결제 진행 전 필수 체크박스 3개에 모두 동의해야 합니다 (${
                [agreeKey, agreeRecurring, agreeStripe].filter(Boolean).length
              }/3).`}
            </p>
          )}
          <button
            type="button"
            disabled={!allAgreed || submitting}
            aria-disabled={!allAgreed || submitting}
            onClick={onConfirm}
            className="w-full py-3 font-serif transition-all"
            style={{
              fontSize: "var(--pq-text-body)",
              letterSpacing: "0.02em",
              borderRadius: "2px",
              backgroundColor: allAgreed && !submitting
                ? "var(--pq-bronze)"
                : "rgba(245,240,232,0.10)",
              color: allAgreed && !submitting
                ? "var(--pq-ink)"
                : "rgba(245,240,232,0.55)",
              cursor: allAgreed && !submitting ? "pointer" : "not-allowed",
            }}
          >
            {submitting ? "Redirecting…" : "Agree and continue to checkout"}
          </button>
          <p
            className="mt-3 text-center font-mono tabular-nums"
            style={{
              fontSize: "var(--pq-text-eyebrow)",
              letterSpacing: "0.16em",
              color: "rgba(245,240,232,0.55)",
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
  // 2026-05-15 (bug-hunter Wave 5 P2 #6): the Free plan CTA hard-coded
  // `href="/signup"`; logged-in users who clicked it bounced through
  // /signup → /home with no indication of where they went or why.
  // Use the auth state to route logged-in users to /home directly.
  const { user } = useAuth();
  const searchParams = useSearchParams();
  const [loadingCheckout, setLoadingCheckout] = useState<TierKey | null>(null);
  const [consentTier, setConsentTier] = useState<TierKey | null>(null);

  const handleCheckout = useCallback((plan: TierKey) => {
    setConsentTier(plan);
  }, []);

  // Wave G-1 Bug #5 (2026-05-18): /pricing?plan=pro 또는 /pricing?plan=premium
  // deeplink 진입 시 해당 카드로 스크롤 + (로그인 상태면) consent modal 자동 오픈.
  // 마케팅 이메일·in-app CTA 에서 plan 별 deeplink 를 보내고 있는데 기존엔
  // 무시되어 사용자가 다시 카드를 찾아야 했다.
  useEffect(() => {
    const planFromUrl = searchParams?.get("plan");
    if (planFromUrl === "pro" || planFromUrl === "premium") {
      const el = document.getElementById(`tier-${planFromUrl}`);
      if (el) {
        el.scrollIntoView({ behavior: "smooth", block: "center" });
      }
      // 로그인 유저만 consent modal 열기 — 비로그인은 /signup 으로 가야 함.
      if (user) {
        setConsentTier(planFromUrl);
      }
    }
    // searchParams + user 둘 다 의존 — user 가 늦게 hydrate 되면 재시도.
  }, [searchParams, user]);

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
    } catch (err: unknown) {
      // 2026-05-15 (bug-hunter Wave 5 P1/SHIP-BLOCKER #1): the previous
      // `catch { window.location.href = "/signup"; }` swallowed the
      // 503 BUSINESS_REGISTRATION_PENDING response silently — logged-in
      // users bounced to /home (because /signup auto-redirects when
      // already authed) with NO indication that checkout was blocked.
      // Surface a clear inline error so the user knows why the
      // checkout didn't proceed.
      if (
        err instanceof ApiError &&
        err.status === 503 &&
        /BUSINESS_REGISTRATION_PENDING|Subscription not yet available/i.test(
          err.message,
        )
      ) {
        toast.error(
          "구독 가입 준비 중입니다. 사업자등록·결제 시스템 활성화 후 이용 가능합니다.",
          {
            description: "support@pivoxquant.com 으로 문의해 주세요.",
            duration: 7000,
          },
        );
      } else if (err instanceof ApiError && err.status === 429) {
        toast.error("요청이 너무 많습니다. 잠시 후 다시 시도해 주세요.");
      } else if (err instanceof ApiError && err.status === 401) {
        // Genuinely unauthed → existing /signup redirect is correct.
        window.location.href = "/signup";
      } else {
        toast.error(
          "결제 페이지 연결 실패. 잠시 후 다시 시도해 주세요.",
          {
            description: err instanceof Error ? err.message : undefined,
          },
        );
      }
    } finally {
      setLoadingCheckout(null);
      setConsentTier(null);
    }
  }, [consentTier]);

  return (
    <ErrorBoundary>
      <div
        className="min-h-screen"
        style={{ backgroundColor: "#050505", color: "var(--pq-ivory)" }}
      >
        {/* ── Top nav ── */}
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-6">
          <Link
            href="/"
            className="inline-flex items-center gap-2 font-serif transition-opacity hover:opacity-70"
            style={{
              fontSize: "var(--pq-text-eyebrow)",
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
                style={{ backgroundColor: "rgba(var(--pq-bronze-wash-rgb),0.7)" }}
              />
              <span
                className="font-serif text-pq-mono-sm uppercase"
                style={{
                  letterSpacing: "0.22em",
                  color: "var(--pq-bronze)",
                }}
              >
                Membership
              </span>
            </div>

            {/* FINDING-028: italic-emphasis is the signature pattern — only
                the emphasis word is italic, not the whole phrase (cf. /risk
                "Risk *board*.", /portfolio "Your *book*."). */}
            <h1
              className="font-serif mb-6"
              style={{
                fontSize: "clamp(2rem, 4.2vw, 3.25rem)",
                lineHeight: 1.08,
                letterSpacing: "-0.02em",
                fontWeight: 400,
                color: "var(--pq-ivory)",
              }}
            >
              Pick the tier that matches your{" "}
              <span>cadence</span>.
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

        {/* ── Coming Soon banner — Wave 2 (2026-04-29) ──
            Stripe API key + product IDs are unallocated until the user's
            사업자등록증 + Stripe onboarding completes. The CTA still fires
            against `/api/billing/checkout`, which currently returns 502;
            the consent-modal flow has been retained so we can flip the
            switch the moment Stripe goes live. */}
        <section
          className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pb-8"
          aria-label="Subscription availability"
        >
          <div
            role="status"
            className="rounded-sm p-5 flex items-start gap-3"
            style={{
              backgroundColor: "rgba(var(--pq-bronze-wash-rgb),0.08)",
              border: "0.5pt solid rgba(var(--pq-bronze-wash-rgb),0.32)",
            }}
          >
            <Info
              className="h-4 w-4 mt-[2px] shrink-0"
              style={{ color: "var(--pq-bronze)" }}
            />
            <div>
              {/* FINDING-029: no mid-eyebrow EN↔KR language switch — the
                  banner body below is Korean, so the eyebrow is fully Korean. */}
              <p
                className="font-mono uppercase mb-1"
                style={{
                  fontSize: "var(--pq-text-eyebrow)",
                  letterSpacing: "0.22em",
                  color: "var(--pq-bronze)",
                }}
              >
                출시 임박 · 정식 출시 후 결제 활성화
              </p>
              <p
                className="font-serif leading-relaxed"
                style={{
                  fontSize: "var(--pq-text-body)",
                  color: "rgba(245,240,232,0.72)",
                  lineHeight: 1.65,
                  maxWidth: "62ch",
                }}
              >
                결제 시스템(Stripe)은 사업자등록 절차 완료 후 활성화됩니다. 그
                전까지는 Free 플랜으로 모든 베타 기능을 사용할 수 있어요.
                구독 확정은 Stripe 연동 시점에 이메일로 안내드립니다.
              </p>
            </div>
          </div>
        </section>

        {/* ── Tier Cards (matches landing Pricing section) ── */}
        <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pb-20 md:pb-28">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 md:gap-8 items-stretch">
            {TIERS.map((p) => {
              // v3 lock-in 2026-04-29: all pricing cards on Vantablack —
              // bug-hunter Wave 2 Bug #7 found Free/Premium cards rendering
              // ivory backgrounds while the rest of the site is dark, which
              // visually fractures the page. The legacy `p.dark` flag is
              // honored for tone signaling (e.g. recommended highlight) but
              // the panel ground is uniformly dark.
              const isDark = true;
              void p.dark;
              return (
                <div
                  key={p.key}
                  id={`tier-${p.key}`}
                  className="relative rounded-sm p-8 md:p-9 flex flex-col"
                  style={{
                    backgroundColor: isDark ? "var(--pq-onyx)" : "var(--pq-ivory)",
                    border: p.recommended
                      ? "1px solid var(--pq-bronze)"
                      : isDark
                        ? "0.5pt solid rgba(245,240,232,0.10)"
                        : "0.5pt solid rgba(10,10,10,0.10)",
                    boxShadow: p.recommended
                      ? "0 40px 80px -40px rgba(var(--pq-bronze-wash-rgb),0.35)"
                      : "none",
                  }}
                >
                  {/* Tier name + bronze hairline */}
                  <div className="mb-6 flex items-center gap-3">
                    <span
                      className="font-serif text-pq-mono-sm uppercase"
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
                      <PriceCountUp value={p.price} />
                    </span>
                    <span
                      className="font-serif text-pq-mono-sm uppercase"
                      style={{
                        letterSpacing: "0.2em",
                        color: isDark ? "rgba(245,240,232,0.55)" : "#6B6B6B",
                      }}
                    >
                      {p.unit}
                    </span>
                  </div>
                  <p
                    className="font-serif text-pq-caption mb-7"
                    style={{
                      color: isDark ? "rgba(245,240,232,0.48)" : "#6B6B6B",
                      letterSpacing: "0.02em",
                    }}
                  >
                    {p.period}
                  </p>

                  {/* Tagline */}
                  <p
                    className="font-serif text-pq-body-sm leading-snug mb-7 pb-6"
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
                          className="font-serif text-pq-body leading-snug"
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
                      // Wave 5 #6: logged-in users go straight to /home
                      // (the Free tier landing) rather than bouncing
                      // through /signup → auto-redirect.
                      href={user ? "/mirror" : p.href}
                      className="block text-center w-full py-3 px-4 font-serif text-pq-body transition-colors"
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
                      className="block text-center w-full py-3 px-4 font-serif text-pq-body transition-colors"
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
            className="mt-12 font-serif text-pq-mono-sm leading-relaxed"
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
              style={{ backgroundColor: "rgba(var(--pq-bronze-wash-rgb),0.7)" }}
            />
            <span
              className="font-serif text-pq-mono-sm uppercase"
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
              backgroundColor: "var(--pq-onyx)",
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
              backgroundColor: "rgba(var(--pq-bronze-wash-rgb),0.06)",
              border: "0.5pt solid rgba(var(--pq-bronze-wash-rgb),0.20)",
            }}
          >
            <p
              className="font-serif leading-relaxed"
              style={{
                fontSize: "var(--pq-text-eyebrow)",
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
              fontSize: "var(--pq-text-eyebrow)",
              letterSpacing: "0.18em",
              color: "rgba(245,240,232,0.55)",
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
