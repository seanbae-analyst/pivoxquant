"use client";

/**
 * LandingV2 — PivoxQuant public landing.
 * ---------------------------------------------------------------------
 * Structure (measured 2026-09-02 — this list is the render order below):
 *   1. TopNav
 *   2. SplashPage      — wordmark cover
 *   3. Hero            — "부자로 만들어 준다고 약속하지 않습니다"
 *   4. ThreeSteps      — 멈춤 · 기록 · 거울, one card per shipping route
 *   5. ImportInboxPreview — a pasted fill notification becoming tagged rows;
 *                        /journal/import + /settings#import-tokens (2026-09-19).
 *                        Deliberately its own section, not a Faq item: "typing
 *                        every fill by hand" was the unanswered objection.
 *   6. PersonasPreview — the 3 disclosed buckets only (성장형/균형형/수익형);
 *                        engine persona codes never appear (2026-09-13)
 *   7. Faq             — 7 items, answered against what ships
 *   8. CtaFooter       — free closed beta, Google/Kakao only
 *   9. SiteFooter      — 전자상거래법 §13 business disclosure
 *
 * ⚠️ The header this replaced described a nine-section page whose middle
 * was <MarqueeLogos/> ("Built on the methodology of" — twelve quant models
 * with zero implementations, see three-steps.tsx) and <PricingPreview/>
 * (paid tiers listing deleted artifacts + an AI Assistant). It also sent
 * readers to TopNav mega-dropdowns into /features/* — those routes all 308 to
 * "/", and the only dropdown TopNav still has is Docs (FAQ / Terms / Privacy).
 *
 * The rule that keeps it from rotting again: **a section may only claim
 * what a route does.** ThreeSteps prints the route on each card for exactly
 * that reason. Before editing copy here, open the route and read it.
 *
 * Palette: Vantablack #050505 + Bronze #B8956A + Ivory #F5F0E8.
 * Type:    Playfair Display + Source Serif 4 + JetBrains Mono. No italic.
 * Motion:  cubic-bezier(0.16, 1, 0.3, 1) universally.
 * Banned:  purple/violet, BUY/SELL/HOLD/recommend/advice/추천/조언.
 */

import Link from "next/link";
import { motion, useReducedMotion } from "motion/react";
import { ArrowRight } from "lucide-react";

import TopNav from "./top-nav";
import SplashPage from "./splash-page";
import { Hero } from "./hero";
import ThreeSteps from "./three-steps";
import ImportInboxPreview from "./import-inbox-preview";
import PersonasPreview from "./personas-preview";
import { FilmGrain } from "./film-grain";
import { SectionCurtain } from "./section-curtain";
import { Eyebrow } from "./eyebrow";
import { fadeUp, stagger } from "@/lib/motion";
import {
  businessInfoRaw,
  ftcBizInfoUrl,
  SUPPORT_EMAIL_DEFAULT,
} from "@/lib/business-info";
import { useT } from "@/lib/locale";
import { useAuth } from "@/lib/auth";

/* ───────────── pricing: removed 2026-09-02 ─────────────
 *
 * A <PricingPreview/> section and a TIERS array lived here (Free ₩0 / Pro
 * ₩9,900 / Premium ₩19,900). They were env-gated OFF for the Stage 0 free
 * launch, so nothing rendered — but the feature bullets they carried had
 * gone false:
 *
 *   "AI Assistant"  → `services/ai/` deleted 2026-09-01, 0 runtime calls
 *   "1/2/Unlimited broker connections" → BROKER_LINKING_AVAILABLE=false
 *   "Weekly Memo · Morning Brief Plus · Earnings Pre-Brief · DD Checklist ·
 *    Risk Board · Insider Mirror · Capital Allocation · Credit Rating ·
 *    Burn Rate · KPI Dashboard · Year-End Letter · 12 artifacts"
 *                   → every one of these artifact surfaces died in the
 *                     2026-08-31 prune
 *
 * Keeping it behind a flag meant one env var away from publishing a paid
 * price list for a product that does not exist — 표시광고법 §3 and, once
 * money changes hands, 전자상거래법 §21. A dormant landmine is not "kept
 * intact", it is deferred breakage.
 *
 * Reviving Stage 1 pricing needs fresh feature lists measured against the
 * app anyway, so the stale ones buy nothing. Recover the old markup (layout
 * only — never the bullets) with:
 *     git show c1f61809:frontend/src/components/landing/landing-v2.tsx
 * Price SoT stays frontend/src/content/terms-ko.md §8.1.
 * Backend billing remains gated (503 BUSINESS_REGISTRATION_PENDING).
 */

/* ───────────────────────── FAQ data ───────────────────────── */

// Copy lives in messages/{ko,en}.json under `landing.faq`. 2026-09-01 rewrote
// the answers against what ships (they used to describe artifacts, a Risk Board
// and weekly memos — none of which exist). 2026-09-02 moved them out of this
// file: the questions were English with Korean answers, and the Korean rewrite
// left the en locale rendering a half-Korean page.
const FAQ_KEYS = ["1", "2", "3", "4", "5", "6", "7"] as const;

/* ═══════════════════════════════════════════════════════════════
   FAQ
   ═══════════════════════════════════════════════════════════════ */

function Faq() {
  const t = useT();
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
          <Eyebrow className="mb-6">{t("landing.faq.eyebrow")}</Eyebrow>
          {/* 2026-09-02: was "Questions members ask before they subscribe."
              — nobody subscribes. Billing is gated 503 and the beta is free. */}
          <p className="pq-deck mb-4">{t("landing.faq.deck")}</p>
          <h2
            className="pq-silver-matte font-serif"
            style={{
              fontSize: "clamp(1.75rem, 3.4vw, 2.5rem)",
              lineHeight: 1.1,
              letterSpacing: "-0.02em",
              fontWeight: 500,
            }}
          >
            {t("landing.faq.heading")}
          </h2>
        </motion.div>

        <motion.div
          initial={reduce ? undefined : "hidden"}
          whileInView={reduce ? undefined : "visible"}
          viewport={{ once: true, margin: "-60px" }}
          variants={stagger}
        >
          {FAQ_KEYS.map((k, i) => (
            <motion.details
              key={k}
              variants={fadeUp}
              className="pq-faq-item"
              {...(i === 0 ? { open: true } : {})}
            >
              <summary>
                <span>{t(`landing.faq.q${k}`)}</span>
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
                {t(`landing.faq.a${k}`)}
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
  const t = useT();
  const { user } = useAuth();
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
          <Eyebrow withDashRight>{t("landing.cta.eyebrow")}</Eyebrow>
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
          {/* 2026-09-02: was "Give your portfolio someone to report to." —
              that promised an entity that writes to you. Nothing writes to
              you: the artifact pipeline is gone and no AI runs. The mirror
              only replays what you wrote. */}
          {t("landing.cta.heading1")}
          <br />
          {t("landing.cta.heading2")}
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
          {/* 2026-09-02: was "Cancel anytime. Visa · Master · Naver Pay ·
              Kakao Pay." — there is no checkout to cancel. routes/billing.py
              answers 503 BUSINESS_REGISTRATION_PENDING and Stripe.js is not
              even allowed by CSP at Stage 0. Advertising payment methods that
              cannot be used is 표시광고법 §3; naming card brands we have no
              merchant agreement for compounds it. */}
          {t("landing.cta.sub")}
        </motion.p>

        <motion.div
          initial={reduce ? undefined : "hidden"}
          whileInView={reduce ? undefined : "visible"}
          viewport={{ once: true, margin: "-60px" }}
          variants={fadeUp}
          className="flex flex-wrap items-center justify-center gap-5"
        >
          {/* Signed-in users already have an account — offering them 회원가입
              and 로그인 again was the 2026-09-12 sweep finding. Same split as
              hero.tsx and top-nav.tsx.
              2026-09-17: the secondary "로그인" outline pill that used to sit
              beside this one is gone. /login and /signup are one screen, and
              two adjacent pills pointing at the same URL is not a choice. */}
          <Link
            href={user ? "/mirror" : "/login"}
            className="group inline-flex items-center gap-2 rounded-sm px-7 py-3.5 font-serif transition-transform active:scale-[0.98]"
            style={{
              backgroundColor: "var(--pq-bronze)",
              color: "var(--pq-ink)",
              fontSize: "var(--pq-text-body)",
              letterSpacing: "0.02em",
            }}
          >
            {user ? t("landing.hero.ctaOpenMirror") : t("landing.cta.signUp")}
            <ArrowRight
              className="h-4 w-4 transition-transform duration-200 group-hover:translate-x-0.5"
              strokeWidth={1.75}
              aria-hidden
            />
          </Link>
        </motion.div>
      </div>
    </section>
  );
}

function SiteFooter() {
  const t = useT();
  // Same fallback chain as the §13 block below — one address on the whole
  // footer. 2026-09-17: "Contact" and "EMAIL" went to hello@ while the legal
  // block two lines down printed support@, which is the address terms-ko.md,
  // privacy-ko.md and routes/support.py actually use.
  const supportEmail = businessInfoRaw.supportEmail || SUPPORT_EMAIL_DEFAULT;
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
                className="font-serif"
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
                color: "var(--pq-ivory-faint)",
              }}
            >
              {t("landing.footer.tagline")}
            </p>
          </div>

          {[
            {
              title: t("landing.footer.company"),
              // Pricing 링크 제거 (DECISIONS.md ✅확정 2026-05-30: 무료 Stage 0).
              // /pricing 은 next.config.ts 307 redirect → /home. Stage 1 부활 시 복원.
              // Living Mirror / Personas / Signature 열은 /features/* 페이지와
              // 함께 삭제 — 없는 화면을 파는 링크는 남기지 않는다.
              links: [
                { label: t("landing.footer.terms"), href: "/terms" },
                { label: t("landing.footer.privacy"), href: "/privacy" },
                {
                  label: t("landing.footer.contact"),
                  href: `mailto:${supportEmail}`,
                },
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
                        color: "var(--pq-ivory-dim)",
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
              color: "var(--pq-ivory-faint)",
            }}
          >
            <strong style={{ color: "var(--pq-ivory-mid)" }}>
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
              href={`mailto:${supportEmail}`}
              style={{ color: "inherit", textDecoration: "underline" }}
            >
              {supportEmail}
            </a>
            {/* 전자상거래법 §13 은 호스팅사업자를 표시하게 한다 — 즉 이 값은
                장식이 아니라 진술이다. 2026-09-02 까지 "Railway" 라고 적혀
                있었는데 그 계정은 삭제됐고 백엔드는 Render 로 간다. 배포처를
                옮기면 이 줄도 같이 고쳐라. */}
            &nbsp;·&nbsp; 호스팅 Vercel · Render
          </p>
        </div>

        <div
          className="pt-6"
          style={{ borderTop: "0.5pt solid var(--pq-ivory-line)" }}
        >
          <div className="grid grid-cols-1 items-center gap-6 md:grid-cols-3">
            <p
              className="font-serif"
              style={{
                fontSize: "var(--pq-text-eyebrow)",
                letterSpacing: "0.01em",
                color: "var(--pq-ivory-faint)",
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
              className="font-serif text-center"
              style={{
                fontSize: "var(--pq-text-body-sm)",
                lineHeight: 1.6,
                color: "var(--pq-ivory-faint)",
              }}
            >
              {t("landing.footer.disclaimer")}
            </p>
            {/* FINDING-LAND-006 (design-audit-20260514): removed the public
                GitHub repo link — PivoxQuant is a private beta on the §101
                exemption track, so the repository is not advertised. The
                ❦ separator was dropped with it since only one link remains. */}
            <div className="flex items-center gap-4 md:justify-end">
              <a
                href={`mailto:${supportEmail}`}
                className="font-serif uppercase transition-colors"
                style={{
                  fontSize: "var(--pq-text-eyebrow)",
                  letterSpacing: "0.12em",
                  color: "var(--pq-ivory-faint)",
                }}
              >
                {t("landing.footer.email")}
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

// Stage 0 (free launch): there is no pricing section, and NEXT_PUBLIC_SHOW_PRICING
// no longer does anything — the section it gated was deleted 2026-09-02 (see the
// "pricing: removed" note near the top of this file for why the flag was a
// liability rather than an option). Backend billing stays gated at 503
// BUSINESS_REGISTRATION_PENDING, so a visitor still cannot subscribe by any path.
export default function LandingV2() {
  return (
    <div
      className="min-h-screen overflow-x-hidden"
      style={{ backgroundColor: "var(--pq-ink)", color: "var(--pq-ivory)" }}
    >
      <TopNav />
      <SplashPage />
      <Hero />
      <SectionCurtain divider={false}>
        <ThreeSteps />
      </SectionCurtain>
      <SectionCurtain>
        <ImportInboxPreview />
      </SectionCurtain>
      <SectionCurtain>
        <PersonasPreview />
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
