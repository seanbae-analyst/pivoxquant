"use client";

/**
 * LandingV2 — PivoxQuant slim landing (7 sections, 21st.dev polish).
 * ---------------------------------------------------------------------
 * Structure (per 2026-04-23 CEO directive):
 *   1. SplashPage          (existing)
 *   2. Hero                (existing, v4)
 *   3. MarqueeLogos        (new — benchmark wordmark marquee)
 *   4. ThreeLayers         (existing, acts as 3-Layer + Loop preview)
 *   5. PersonasPreview     (new — 4 of 8)
 *   6. PricingPreview      (local — condensed 4-tier summary)
 *   7. Faq                 (local — 7 accordion items from legacy)
 *   8. CtaFooter           (local — "Give your portfolio someone to report to")
 *   9. Footer              (local)
 *
 * Everything removed from the legacy monolith (FeatureExplorer, Engine,
 * Sample Reports, Archetype, Dashboard Preview, Pre-Trade Checklist,
 * Korea×US Desk, Journal Companion, Living CFO Loop, Pull-Quote) is
 * reachable via TopNav mega-dropdowns → /features/* routes which load
 * the legacy LandingPage component scrolled to a hash anchor.
 *
 * Palette: Vantablack #050505 + Bronze #B8956A + Ivory #F5F0E8.
 * Type:    Playfair Display + Source Serif 4 + JetBrains Mono.
 * Motion:  cubic-bezier(0.16, 1, 0.3, 1) universally.
 * Banned:  purple/violet, BUY/SELL/HOLD/recommend/advice.
 */

import Link from "next/link";
import { motion, useReducedMotion } from "motion/react";
import { ArrowRight, Check } from "lucide-react";

import TopNav from "./top-nav";
import SplashPage from "./splash-page";
import { Hero } from "./hero";
import MarqueeLogos from "./marquee-logos";
import PersonasPreview from "./personas-preview";
import ReportsGallery from "./reports-gallery";
import { FilmGrain } from "./film-grain";
import { SectionCurtain } from "./section-curtain";
import { Eyebrow } from "./eyebrow";
import { MainLandingViewTracker } from "@/components/growth/main-landing-view-tracker";
import { fadeUp, stagger } from "@/lib/motion";
import {
  businessInfoRaw,
  ftcBizInfoUrl,
  SUPPORT_EMAIL_DEFAULT,
} from "@/lib/business-info";

/* ───────────────────────── pricing data ───────────────────────── */

type TierSlim = {
  name: string;
  numeral: string;
  price: string;
  period: string;
  tagline: string;
  features: string[];
  cta: string;
  href: string;
  dark?: boolean;
  recommended?: boolean;
};

// Tier SoT: frontend/src/content/terms-ko.md §8.1 (Free / Pro / Premium).
// 2026-04-27: 4-tier (incl. Elite + Founding Lifetime) consolidated to 3-tier
// per legal review — see REPORT_LEGAL_AUDIT_2026-04-27.md.
const TIERS: readonly TierSlim[] = [
  {
    name: "Free",
    numeral: "I",
    price: "0",
    period: "forever",
    tagline: "Read-only observation. 1 artifact per week.",
    features: [
      "Weekly Memo (abridged)",
      "Portfolio observation dashboard",
      "1 broker connection",
    ],
    cta: "Create free account",
    href: "/signup",
  },
  {
    name: "Pro",
    numeral: "II",
    price: "9,900",
    period: "per month",
    tagline: "Full desk. 12 artifacts. AI Assistant.",
    dark: true,
    recommended: true,
    features: [
      "Everything in Free",
      "Morning Brief Plus · Earnings Pre-Brief",
      "DD Checklist · Risk Board · Insider Mirror",
      "2 broker connections · AI Assistant",
    ],
    cta: "Subscribe to Pro",
    href: "/signup",
  },
  {
    name: "Premium",
    numeral: "III",
    price: "19,900",
    period: "per month",
    tagline: "Board-grade decks. Quarterly self-audit. Year-end letter.",
    features: [
      "Everything in Pro",
      "Capital Allocation · Credit Rating · Burn Rate",
      "Monthly Finance · KPI Dashboard",
      "Year-End Letter · Unlimited brokers",
    ],
    cta: "Upgrade to Premium",
    href: "/signup",
  },
] as const;

/* ───────────────────────── FAQ data ───────────────────────── */

const FAQ_ITEMS = [
  {
    q: "Is a personal CFO the same as investment advisory?",
    a: "No. 자본시장법 제6조상 개인 투자자문업과 무관합니다. PivoxQuant는 당신 자신의 포트폴리오를 관측하고 기록하는 informational research tool입니다. 모든 artifact는 관측치 (concentration, drawdown, factor tilts, earnings posture)이며 매수/매도 지시가 아닙니다. Labels are POSITIVE / NEGATIVE / NEUTRAL — never buy, sell, or hold. 결정은 전적으로 당신의 몫입니다.",
  },
  {
    q: "How is my trade data used — what does the CFO “learn”?",
    a: "당신의 온보딩 20문항과 포트폴리오 이력을 바탕으로 Layer 1 Identity를 구성합니다. Layer 2 Learning은 롤링 윈도우로 drift를 감지해 페르소나를 재조정하고, Layer 3 Artifact는 그 결과로 당신에게 맞는 리포트를 발행합니다. 원본 거래 데이터는 암호화 저장되며 광고·외부 판매에 사용되지 않습니다. 탈퇴 시 30일 내 완전 삭제됩니다.",
  },
  {
    q: "How does my persona change over time?",
    a: "Drift detection이 매주 동작합니다. 최근 90일의 거래·반응 패턴이 현재 페르소나와 유의미하게 달라지면 CFO가 “당신이 다르게 움직이기 시작했다”는 Pulse 리포트를 발행합니다. 재분류는 자동이 아니라 제안입니다 — 수락해야 다음 사이클부터 새 페르소나 기준으로 리포트가 나옵니다.",
  },
  {
    q: "What happens after I subscribe?",
    a: "Pro 티어 풀액세스. 첫 weekly memo · earnings pre-brief · Risk Board가 24시간 내 당신의 실제 보유에서 렌더됩니다. 전자상거래법상 첫 결제 14일 이내 미사용 시 전액 환불 대상. 이후 월 KRW 9,900.",
  },
  {
    q: "Do you have access to my brokerage account?",
    a: "Read-only. KIS (KR) read-only scope로 연결됩니다. 주문 · 출금 · 수정 불가. 연결 해제 시 artifact 렌더링 중단, 데이터는 30일 보관 후 파기.",
  },
  {
    q: "Can I cancel? How do refunds work?",
    a: "Settings에서 언제든 취소 — 이메일·전화 없이. 전자상거래법상 첫 결제 14일 이내 미사용 시 전액 환불 대상. 이후에는 현재 주기 종료 시 청구가 멈춥니다.",
  },
];

/* ═══════════════════════════════════════════════════════════════
   PRICING PREVIEW
   ═══════════════════════════════════════════════════════════════ */

function PricingPreview() {
  const reduce = useReducedMotion();
  return (
    <section
      id="pricing"
      className="relative py-24 md:py-36 lg:py-48"
      style={{ backgroundColor: "#050505" }}
    >
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <motion.div
          initial={reduce ? undefined : "hidden"}
          whileInView={reduce ? undefined : "visible"}
          viewport={{ once: true, margin: "-80px" }}
          variants={fadeUp}
          className="mb-16 max-w-2xl md:mb-24"
        >
          <Eyebrow className="mb-6">Membership</Eyebrow>
          <p className="pq-deck mb-4">
            Three tiers. We are never paid when you trade.
          </p>
          <h2
            className="pq-silver-matte font-serif"
            style={{
              fontSize: "clamp(1.875rem, 3.6vw, 2.75rem)",
              lineHeight: 1.08,
              letterSpacing: "-0.02em",
              fontWeight: 500,
              marginBottom: 28,
            }}
          >
            We are paid
            <br />
            when you stay subscribed.
          </h2>
          <p
            className="font-serif"
            style={{
              fontSize: "clamp(15px, 1.3vw, 17px)",
              lineHeight: 1.65,
              color: "rgba(245,240,232,0.65)",
              maxWidth: 560,
            }}
          >
            The incentive is your quiet compounding. No trade commissions, no
            payment for order flow, no sponsored artifacts.
          </p>
        </motion.div>

        <motion.div
          initial={reduce ? undefined : "hidden"}
          whileInView={reduce ? undefined : "visible"}
          viewport={{ once: true, margin: "-60px" }}
          variants={stagger}
          className="grid grid-cols-1 items-stretch gap-6 md:grid-cols-3 md:gap-7"
        >
          {TIERS.map((t) => (
            <motion.article
              key={t.name}
              variants={fadeUp}
              className="pq-tier-card-v2 group relative flex flex-col overflow-hidden rounded-sm p-7"
              style={{
                backgroundColor: t.dark ? "var(--pq-card-veil)" : "#050505",
                border: t.recommended
                  ? "0.5px solid rgba(184,149,106,0.55)"
                  : "0.5px solid rgba(184,149,106,0.22)",
                boxShadow: t.recommended
                  ? "0 1px 0 rgba(184,149,106,0.12) inset, 0 24px 48px -32px rgba(184,149,106,0.25)"
                  : "none",
                transition:
                  "border-color 240ms cubic-bezier(0.16,1,0.3,1), background-color 240ms cubic-bezier(0.16,1,0.3,1)",
              }}
            >
              <div className="mb-6 flex items-baseline gap-2">
                <span
                  className="font-serif"
                  style={{
                    color: "var(--pq-bronze)",
                    fontSize: "var(--pq-text-caption)",
                    letterSpacing: "0.22em",
                  }}
                >
                  {t.numeral}
                </span>
                <h3
                  className="font-serif"
                  style={{
                    color: "var(--pq-ivory)",
                    fontSize: "var(--pq-text-quote)",
                    fontWeight: 500,
                    letterSpacing: "-0.01em",
                  }}
                >
                  {t.name}
                </h3>
              </div>

              <div className="mb-5">
                <span
                  className="font-serif"
                  style={{
                    color: "var(--pq-ivory)",
                    fontSize: "var(--pq-text-h3)",
                    fontWeight: 500,
                    letterSpacing: "-0.02em",
                  }}
                >
                  KRW {t.price}
                </span>
                <span
                  className="font-serif"
                  style={{
                    color: "rgba(245,240,232,0.45)",
                    fontSize: "var(--pq-text-caption)",
                    marginLeft: 6,
                  }}
                >
                  / {t.period}
                </span>
              </div>

              <p
                className="font-serif italic"
                style={{
                  color: "rgba(245,240,232,0.6)",
                  fontSize: "var(--pq-text-body-sm)",
                  lineHeight: 1.5,
                  marginBottom: 20,
                }}
              >
                {t.tagline}
              </p>

              <ul className="mb-8 flex-1 space-y-2.5">
                {t.features.map((f) => (
                  <li
                    key={f}
                    className="flex items-start gap-2.5 font-serif"
                    style={{
                      color: "rgba(245,240,232,0.78)",
                      fontSize: "var(--pq-text-body-sm)",
                      lineHeight: 1.5,
                    }}
                  >
                    <Check
                      className="mt-0.5 h-3.5 w-3.5 flex-none"
                      style={{ color: "var(--pq-bronze)" }}
                      aria-hidden
                    />
                    <span>{f}</span>
                  </li>
                ))}
              </ul>

              <Link
                href={t.href}
                className="group/cta inline-flex items-center justify-center gap-2 rounded-sm px-5 py-3 font-serif transition-transform active:scale-[0.98]"
                style={{
                  backgroundColor: t.recommended
                    ? "var(--pq-bronze)"
                    : "transparent",
                  color: t.recommended ? "var(--pq-ink)" : "var(--pq-ivory)",
                  border: t.recommended
                    ? "none"
                    : "0.5pt solid rgba(184,149,106,0.5)",
                  fontSize: "var(--pq-text-body-sm)",
                  letterSpacing: "0.02em",
                  fontWeight: 500,
                }}
              >
                {t.cta}
                <ArrowRight
                  className="h-3.5 w-3.5 transition-transform duration-300 group-hover/cta:translate-x-0.5"
                  aria-hidden
                />
              </Link>
            </motion.article>
          ))}
        </motion.div>

        {/* Founding Lifetime panel removed 2026-04-27 per legal review:
            "평생 사용권" 약속은 1인 시드 단계에서 영업 지속성 의존 채무.
            전자상거래법 §21 기만적 광고 가능성. 향후 안정 단계 진입 후 재검토. */}
      </div>

      {/* C — hover consistency: bronze border + bronze-08 fill on hover.
          Mirrors home-card.tsx pq-home-card-v2 pattern. */}
      <style jsx global>{`
        .pq-tier-card-v2:hover {
          border-color: var(--pq-bronze) !important;
          background-color: rgba(184, 149, 106, 0.025) !important;
        }
        @media (prefers-reduced-motion: reduce) {
          .pq-tier-card-v2 {
            transition: none !important;
          }
        }
      `}</style>
    </section>
  );
}

/* ═══════════════════════════════════════════════════════════════
   FAQ
   ═══════════════════════════════════════════════════════════════ */

function Faq() {
  const reduce = useReducedMotion();
  return (
    <section
      id="faq"
      className="pt-16 pb-28 md:pt-24 md:pb-36 lg:pt-32 lg:pb-48"
      style={{ backgroundColor: "#050505" }}
    >
      <div className="mx-auto max-w-3xl px-4 sm:px-6 lg:px-8">
        <motion.div
          initial={reduce ? undefined : "hidden"}
          whileInView={reduce ? undefined : "visible"}
          viewport={{ once: true, margin: "-80px" }}
          variants={fadeUp}
          className="mb-12 md:mb-16"
        >
          <Eyebrow className="mb-6">Desk Notes</Eyebrow>
          <p className="pq-deck mb-4">
            Questions members ask before they subscribe.
          </p>
          <h2
            className="pq-silver-matte font-serif"
            style={{
              fontSize: "clamp(1.75rem, 3.4vw, 2.5rem)",
              lineHeight: 1.1,
              letterSpacing: "-0.02em",
              fontWeight: 500,
            }}
          >
            Before you open the desk.
          </h2>
        </motion.div>

        <motion.div
          initial={reduce ? undefined : "hidden"}
          whileInView={reduce ? undefined : "visible"}
          viewport={{ once: true, margin: "-60px" }}
          variants={stagger}
        >
          {FAQ_ITEMS.map((item, i) => (
            <motion.details
              key={item.q}
              variants={fadeUp}
              className="pq-faq-item"
              {...(i === 0 ? { open: true } : {})}
            >
              <summary>
                <span>{item.q}</span>
                <span aria-hidden className="pq-faq-icon" />
              </summary>
              <div
                className="font-serif"
                style={{
                  fontSize: "var(--pq-text-lead)",
                  lineHeight: 1.7,
                  color: "rgba(245,240,232,0.75)",
                  paddingTop: 10,
                  paddingBottom: 18,
                  maxWidth: "62ch",
                }}
              >
                {item.a}
              </div>
            </motion.details>
          ))}
        </motion.div>
      </div>
    </section>
  );
}

/* ═══════════════════════════════════════════════════════════════
   CTA FOOTER + SITE FOOTER
   ═══════════════════════════════════════════════════════════════ */

function CtaFooter() {
  const reduce = useReducedMotion();
  return (
    <section
      className="relative overflow-hidden py-32 md:py-44 lg:py-52"
      style={{ backgroundColor: "#050505" }}
    >
      <FilmGrain opacity={0.03} blendMode="soft-light" />
      {/* Bronze radial glow */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0"
        style={{
          background:
            "radial-gradient(ellipse at 50% 50%, rgba(184,149,106,0.08) 0%, transparent 65%)",
        }}
      />

      <div className="relative mx-auto max-w-3xl px-4 text-center sm:px-6 lg:px-8">
        <motion.div
          initial={reduce ? undefined : "hidden"}
          whileInView={reduce ? undefined : "visible"}
          viewport={{ once: true, margin: "-80px" }}
          variants={fadeUp}
          className="mb-6 flex justify-center"
        >
          <Eyebrow withDashRight>Ready?</Eyebrow>
        </motion.div>

        <motion.h2
          initial={reduce ? undefined : "hidden"}
          whileInView={reduce ? undefined : "visible"}
          viewport={{ once: true, margin: "-80px" }}
          variants={fadeUp}
          className="font-serif"
          style={{
            fontSize: "clamp(2rem, 4.8vw, 3.6rem)",
            lineHeight: 1.05,
            letterSpacing: "-0.025em",
            fontWeight: 500,
            backgroundImage:
              "linear-gradient(180deg, #F5F0E8 0%, #C9C4BC 100%)",
            WebkitBackgroundClip: "text",
            backgroundClip: "text",
            color: "transparent",
            marginBottom: 24,
          }}
        >
          Give your portfolio
          <br />
          someone to report to.
        </motion.h2>

        <motion.p
          initial={reduce ? undefined : "hidden"}
          whileInView={reduce ? undefined : "visible"}
          viewport={{ once: true, margin: "-60px" }}
          variants={fadeUp}
          className="font-serif mx-auto"
          style={{
            fontSize: "clamp(14.5px, 1.2vw, 16px)",
            lineHeight: 1.65,
            color: "rgba(245,240,232,0.6)",
            maxWidth: "32em",
            marginBottom: 36,
          }}
        >
          Cancel anytime. Visa · Master · Naver Pay · Kakao Pay.
        </motion.p>

        <motion.div
          initial={reduce ? undefined : "hidden"}
          whileInView={reduce ? undefined : "visible"}
          viewport={{ once: true, margin: "-60px" }}
          variants={fadeUp}
          className="flex flex-wrap items-center justify-center gap-5"
        >
          <Link
            href="/signup"
            className="group inline-flex items-center gap-2 rounded-sm px-7 py-3.5 font-serif transition-transform active:scale-[0.98]"
            style={{
              backgroundColor: "var(--pq-bronze)",
              color: "var(--pq-ink)",
              fontSize: "var(--pq-text-body)",
              letterSpacing: "0.02em",
            }}
          >
            Notify me at launch
            <ArrowRight
              className="h-4 w-4 transition-transform duration-200 group-hover:translate-x-0.5"
              strokeWidth={1.75}
              aria-hidden
            />
          </Link>
          <Link
            href="/features/reports"
            className="inline-flex items-center gap-2 rounded-sm px-7 py-3.5 font-serif transition-colors"
            style={{
              border: "0.75pt solid var(--pq-bronze)",
              color: "var(--pq-bronze)",
              fontSize: "var(--pq-text-body)",
              letterSpacing: "0.02em",
              backgroundColor: "transparent",
            }}
          >
            Read sample reports
          </Link>
        </motion.div>
      </div>
    </section>
  );
}

function SiteFooter() {
  return (
    <footer
      className="pt-24 pb-16 md:pt-32 md:pb-20"
      style={{
        backgroundColor: "#050505",
        borderTop: "0.5pt solid var(--pq-ivory-line)",
      }}
    >
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="mb-14 grid grid-cols-2 gap-8 md:grid-cols-6 md:gap-10">
          <div className="col-span-2">
            <Link href="/" className="mb-5 inline-block">
              {/* FINDING-030: canonical italic Playfair mixed-case wordmark. */}
              <span
                className="font-serif italic"
                style={{
                  fontSize: "var(--pq-text-h5)",
                  letterSpacing: "0.01em",
                  color: "var(--pq-ivory)",
                  fontWeight: 500,
                }}
              >
                PivoxQuant
              </span>
            </Link>
            <p
              className="font-serif max-w-xs"
              style={{
                fontSize: "var(--pq-text-body-sm)",
                lineHeight: 1.6,
                color: "rgba(245,240,232,0.5)",
              }}
            >
              Research desk for the self-managed portfolio.
            </p>
          </div>

          {[
            {
              title: "Living CFO",
              links: [
                { label: "3-Layer Architecture", href: "/features/engine#three-layers" },
                { label: "Living CFO Loop", href: "/features/engine#loop" },
                { label: "40-Model Engine", href: "/features/engine" },
                { label: "Feature Explorer", href: "/features/explorer" },
              ],
            },
            {
              title: "Personas",
              links: [
                { label: "8 CFO Personas", href: "/features/personas" },
                { label: "Sample Reports", href: "/features/reports" },
                { label: "Dashboard Preview", href: "/features/dashboard" },
              ],
            },
            {
              title: "Signature",
              links: [
                { label: "Pre-Trade Checklist", href: "/features/pre-trade" },
                { label: "Korea × US Desk", href: "/features/global-desk" },
                { label: "Journal Companion", href: "/companion" },
              ],
            },
            {
              title: "Company",
              links: [
                { label: "Pricing", href: "/pricing" },
                { label: "Terms", href: "/terms" },
                { label: "Privacy", href: "/privacy" },
                { label: "Contact", href: "mailto:hello@pivoxquant.com" },
              ],
            },
          ].map((col) => (
            <div key={col.title}>
              <h4
                className="font-serif uppercase"
                style={{
                  fontSize: "var(--pq-text-eyebrow)",
                  letterSpacing: "0.22em",
                  color: "var(--pq-bronze)",
                  marginBottom: 14,
                }}
              >
                {col.title}
              </h4>
              <ul className="space-y-2.5">
                {col.links.map((link) => (
                  <li key={link.label}>
                    <Link
                      href={link.href}
                      className="font-serif transition-colors"
                      style={{
                        fontSize: "var(--pq-text-body-sm)",
                        color: "rgba(245,240,232,0.55)",
                      }}
                    >
                      {link.label}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        {/* 전자상거래법 §13 사업자 정보 표시. 모든 값은 lib/business-info.ts SoT
            (businessInfoRaw) 를 거쳐 읽는다 — SoT 가 landing/business-info 두 벌
            env 키를 fallback OR 체인으로 흡수하므로 CEO 가 어느 키를 설정하든 동시에
            켜진다(2026-05-26 배선 통일). 미설정 항목은 elide — placeholder
            "(등록 후 표시)" 노출은 첫 인상 신뢰 깎고 표시광고법 위반 의심.
            통신판매업 신고번호는 미신고 상태이므로 env 미설정 → 미노출. */}
        <div
          className="pt-6 pb-4"
          style={{ borderTop: "0.5pt solid var(--pq-ivory-line)" }}
        >
          <p
            className="font-serif"
            style={{
              fontSize: "var(--pq-text-eyebrow)",
              lineHeight: 1.7,
              letterSpacing: "0.02em",
              color: "rgba(245,240,232,0.45)",
            }}
          >
            <strong style={{ color: "rgba(245,240,232,0.65)" }}>
              {businessInfoRaw.name || "PivoxQuant"}
            </strong>
            {businessInfoRaw.representative && (
              <>
                &nbsp;·&nbsp; 대표 {businessInfoRaw.representative}
              </>
            )}
            {businessInfoRaw.privacyOfficer && (
              <>
                &nbsp;·&nbsp; 개인정보보호책임자 {businessInfoRaw.privacyOfficer}
              </>
            )}
            {businessInfoRaw.registrationNumber && (
              <>
                &nbsp;·&nbsp; 사업자등록번호 {businessInfoRaw.registrationNumber}
              </>
            )}
            {businessInfoRaw.telesellerNumber && (
              <>
                &nbsp;·&nbsp; 통신판매업 신고번호 {businessInfoRaw.telesellerNumber}
              </>
            )}
            {businessInfoRaw.telesellerNumber && ftcBizInfoUrl() && (
              <>
                &nbsp;·&nbsp;
                {" "}
                <a
                  href={ftcBizInfoUrl()}
                  target="_blank"
                  rel="noopener noreferrer"
                  style={{ color: "inherit", textDecoration: "underline" }}
                >
                  사업자정보확인
                </a>
              </>
            )}
            {(businessInfoRaw.businessType ||
              businessInfoRaw.businessSubtype) && (
              <>
                <br />
                {businessInfoRaw.businessType && (
                  <>업태 {businessInfoRaw.businessType}</>
                )}
                {businessInfoRaw.businessType &&
                  businessInfoRaw.businessSubtype && (
                    <>&nbsp;·&nbsp;</>
                  )}
                {businessInfoRaw.businessSubtype && (
                  <>종목 {businessInfoRaw.businessSubtype}</>
                )}
              </>
            )}
            {businessInfoRaw.address && (
              <>
                <br />
                주소 {businessInfoRaw.address}
              </>
            )}
            {businessInfoRaw.phone && (
              <>
                &nbsp;·&nbsp; 연락처 {businessInfoRaw.phone}
              </>
            )}
            <br />
            이메일{" "}
            <a
              href={`mailto:${businessInfoRaw.supportEmail || SUPPORT_EMAIL_DEFAULT}`}
              style={{ color: "inherit", textDecoration: "underline" }}
            >
              {businessInfoRaw.supportEmail || SUPPORT_EMAIL_DEFAULT}
            </a>
            &nbsp;·&nbsp; 호스팅 Vercel · Railway
          </p>
        </div>

        <div
          className="pt-6"
          style={{ borderTop: "0.5pt solid var(--pq-ivory-line)" }}
        >
          <div className="grid grid-cols-1 items-center gap-6 md:grid-cols-3">
            <p
              className="font-serif italic"
              style={{
                fontSize: "var(--pq-text-eyebrow)",
                letterSpacing: "0.01em",
                color: "rgba(245,240,232,0.5)",
              }}
            >
              © {new Date().getFullYear()} PivoxQuant &nbsp;·&nbsp; All rights
              reserved.
            </p>
            {/* FINDING-LAND-002 (design-audit-20260514): the footer
                compliance disclaimer was 11px (--pq-text-mono-sm) — raised
                to the --pq-text-body-sm (13px) token so the legal notice
                is legible rather than visually minimized. */}
            <p
              className="font-serif italic text-center"
              style={{
                fontSize: "var(--pq-text-body-sm)",
                lineHeight: 1.6,
                color: "rgba(245,240,232,0.4)",
              }}
            >
              PivoxQuant is not a licensed investment advisor, discretionary
              manager, or broker-dealer. Research tool only. Past performance
              does not guarantee future results.
            </p>
            {/* FINDING-LAND-006 (design-audit-20260514): removed the public
                GitHub repo link — PivoxQuant is a private beta on the §101
                exemption track, so the repository is not advertised. The
                ❦ separator was dropped with it since only one link remains. */}
            <div className="flex items-center gap-4 md:justify-end">
              <a
                href="mailto:hello@pivoxquant.com"
                className="font-serif transition-colors"
                style={{
                  fontSize: "var(--pq-text-eyebrow)",
                  letterSpacing: "0.12em",
                  color: "rgba(245,240,232,0.4)",
                }}
              >
                EMAIL
              </a>
            </div>
          </div>
        </div>
      </div>
    </footer>
  );
}

/* ═══════════════════════════════════════════════════════════════
   EXPORT
   ═══════════════════════════════════════════════════════════════ */

export default function LandingV2() {
  return (
    <div
      className="min-h-screen overflow-x-hidden"
      style={{ backgroundColor: "var(--pq-ink)", color: "var(--pq-ivory)" }}
    >
      <MainLandingViewTracker />
      <TopNav />
      <SplashPage />
      <Hero />
      <SectionCurtain divider={false}>
        <MarqueeLogos />
      </SectionCurtain>
      <SectionCurtain>
        <PersonasPreview />
      </SectionCurtain>
      <SectionCurtain>
        <ReportsGallery />
      </SectionCurtain>
      <SectionCurtain>
        <PricingPreview />
      </SectionCurtain>
      <SectionCurtain divider={false}>
        <Faq />
      </SectionCurtain>
      <SectionCurtain revealEnd={0.55}>
        <CtaFooter />
      </SectionCurtain>
      <SiteFooter />
    </div>
  );
}
