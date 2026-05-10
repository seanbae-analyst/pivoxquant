"use client";

/**
 * FeaturePageShell — shared chrome for /features/* pages (new set).
 * ------------------------------------------------------------------
 *  • TopNav at top (fixed, overlays eyebrow spacer).
 *  • Eyebrow (bronze caps) + title + deck paragraph hero.
 *  • Renders children — the page-specific body.
 *  • "See also" row of 3 other feature cards at the bottom.
 *  • CTA footer + site footer (re-uses LandingV2's footer semantics).
 *  • Palette-safe.
 */

import Link from "next/link";
import { motion, useReducedMotion } from "motion/react";
import { ArrowRight } from "lucide-react";

import TopNav from "./top-nav";
import { FilmGrain } from "./film-grain";
import { Eyebrow } from "./eyebrow";
import { fadeUp } from "@/lib/motion";

export type SeeAlsoCard = {
  eyebrow: string;
  title: string;
  description: string;
  href: string;
};

export default function FeaturePageShell({
  eyebrow,
  title,
  deck,
  children,
  seeAlso,
}: {
  eyebrow: string;
  title: string;
  deck: string;
  children: React.ReactNode;
  seeAlso: readonly SeeAlsoCard[];
}) {
  const reduce = useReducedMotion();
  return (
    <div
      className="min-h-screen overflow-x-hidden"
      style={{ backgroundColor: "var(--pq-ink)", color: "var(--pq-ivory)" }}
    >
      <TopNav />

      {/* Hero / title block */}
      <section
        className="relative overflow-hidden pt-32 pb-20 md:pt-40 md:pb-28"
        style={{ backgroundColor: "#050505" }}
      >
        <FilmGrain opacity={0.03} blendMode="soft-light" />
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0"
          style={{
            background:
              "radial-gradient(ellipse at 20% 0%, rgba(184,149,106,0.1) 0%, transparent 55%)",
          }}
        />
        <div className="relative mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <motion.div
            initial={reduce ? undefined : "hidden"}
            animate="visible"
            variants={fadeUp}
            className="mb-5"
          >
            <Eyebrow>{eyebrow}</Eyebrow>
          </motion.div>

          <motion.h1
            initial={reduce ? undefined : "hidden"}
            animate="visible"
            variants={fadeUp}
            className="pq-silver-matte font-serif"
            style={{
              fontSize: "clamp(2.25rem, 5vw, 3.75rem)",
              lineHeight: 1.04,
              letterSpacing: "-0.025em",
              fontWeight: 500,
              marginBottom: 22,
              maxWidth: "20ch",
            }}
          >
            {title}
          </motion.h1>

          <motion.p
            initial={reduce ? undefined : "hidden"}
            animate="visible"
            variants={fadeUp}
            className="font-serif"
            style={{
              fontSize: "clamp(15px, 1.3vw, 17.5px)",
              lineHeight: 1.65,
              color: "rgba(245,240,232,0.72)",
              maxWidth: "60ch",
            }}
          >
            {deck}
          </motion.p>
        </div>
      </section>

      {/* Page body */}
      {children}

      {/* See also */}
      <section
        className="py-20 md:py-28"
        style={{
          backgroundColor: "#080808",
          borderTop: "0.5pt solid rgba(184,149,106,0.14)",
        }}
      >
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <Eyebrow className="mb-10 flex">Continue reading</Eyebrow>
          <div className="grid grid-cols-1 gap-5 md:grid-cols-3">
            {seeAlso.map((s) => (
              <Link
                key={s.href}
                href={s.href}
                className="group relative flex flex-col gap-2 overflow-hidden rounded-sm p-6 transition-all hover:-translate-y-0.5"
                style={{
                  backgroundColor: "#0D0D0D",
                  border: "0.5px solid rgba(184,149,106,0.22)",
                }}
              >
                <span
                  aria-hidden
                  className="pointer-events-none absolute inset-x-0 top-0 h-px opacity-0 transition-opacity duration-500 group-hover:opacity-100"
                  style={{
                    background:
                      "linear-gradient(90deg, transparent 0%, rgba(184,149,106,0.5) 50%, transparent 100%)",
                  }}
                />
                <span
                  className="font-serif uppercase"
                  style={{
                    color: "var(--pq-bronze)",
                    fontSize: "12px",
                    letterSpacing: "0.22em",
                  }}
                >
                  {s.eyebrow}
                </span>
                <h3
                  className="font-serif"
                  style={{
                    color: "var(--pq-ivory)",
                    fontSize: "20px",
                    fontWeight: 500,
                    letterSpacing: "-0.01em",
                  }}
                >
                  {s.title}
                </h3>
                <p
                  className="font-serif"
                  style={{
                    color: "rgba(245,240,232,0.6)",
                    fontSize: "14px",
                    lineHeight: 1.55,
                  }}
                >
                  {s.description}
                </p>
                <span
                  className="mt-2 inline-flex items-center gap-1.5 font-serif italic"
                  style={{
                    color: "var(--pq-bronze)",
                    fontSize: "14px",
                  }}
                >
                  Open
                  <ArrowRight
                    className="h-3.5 w-3.5 transition-transform duration-300 group-hover:translate-x-0.5"
                    aria-hidden
                  />
                </span>
              </Link>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section
        className="relative overflow-hidden py-24 md:py-32"
        style={{ backgroundColor: "#050505" }}
      >
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0"
          style={{
            background:
              "radial-gradient(ellipse at 50% 50%, rgba(184,149,106,0.08) 0%, transparent 65%)",
          }}
        />
        <div className="relative mx-auto max-w-3xl px-4 text-center sm:px-6 lg:px-8">
          <h2
            className="font-serif"
            style={{
              fontSize: "clamp(1.75rem, 4.2vw, 2.75rem)",
              lineHeight: 1.1,
              letterSpacing: "-0.02em",
              fontWeight: 500,
              color: "var(--pq-ivory)",
              marginBottom: 22,
            }}
          >
            Give your portfolio
            <br />
            someone to report to.
          </h2>
          <p
            className="font-serif mx-auto"
            style={{
              fontSize: "15px",
              lineHeight: 1.6,
              color: "rgba(245,240,232,0.58)",
              maxWidth: "32em",
              marginBottom: 32,
            }}
          >
            Cancel anytime. Visa · Master · Naver Pay · Kakao Pay.
          </p>
          <div className="flex flex-wrap items-center justify-center gap-4">
            <Link
              href="/signup"
              className="group inline-flex items-center gap-2 rounded-sm px-6 py-3 font-serif transition-transform active:scale-[0.98]"
              style={{
                backgroundColor: "var(--pq-bronze)",
                color: "var(--pq-ink)",
                fontSize: "14px",
                letterSpacing: "0.02em",
              }}
            >
              Notify me at launch
              <ArrowRight className="h-4 w-4 transition-transform duration-300 group-hover:translate-x-0.5" aria-hidden />
            </Link>
            <Link
              href="/"
              className="inline-flex items-center gap-2 rounded-sm px-6 py-3 font-serif transition-colors"
              style={{
                border: "0.75pt solid var(--pq-bronze)",
                color: "var(--pq-bronze)",
                fontSize: "14px",
                letterSpacing: "0.02em",
              }}
            >
              Back to landing
            </Link>
          </div>
        </div>
      </section>

      {/* Minimal footer */}
      <footer
        className="py-10"
        style={{
          backgroundColor: "#030303",
          borderTop: "0.5pt solid var(--pq-ivory-line-soft)",
        }}
      >
        <div className="mx-auto flex max-w-7xl flex-col items-center justify-between gap-4 px-4 sm:flex-row sm:px-6 lg:px-8">
          <p
            className="font-serif italic"
            style={{ fontSize: "12px", color: "rgba(245,240,232,0.4)" }}
          >
            © {new Date().getFullYear()} PivoxQuant · Research tool only.
          </p>
          <div
            className="font-serif uppercase"
            style={{
              fontSize: "12px",
              letterSpacing: "0.22em",
              color: "rgba(245,240,232,0.4)",
            }}
          >
            <Link href="/terms" className="transition-colors hover:text-[var(--pq-bronze)]">Terms</Link>
            <span aria-hidden style={{ margin: "0 12px", color: "rgba(184,149,106,0.5)" }}>·</span>
            <Link href="/privacy" className="transition-colors hover:text-[var(--pq-bronze)]">Privacy</Link>
            <span aria-hidden style={{ margin: "0 12px", color: "rgba(184,149,106,0.5)" }}>·</span>
            <a href="mailto:hello@pivoxquant.com" className="transition-colors hover:text-[var(--pq-bronze)]">Contact</a>
          </div>

          {/* 법적 고지 — 2026-04-23 legal sweep finding: 7 feature pages shipped
              without DisclaimerBanner. Mandatory across every analysis surface
              per CLAUDE.md + 금투협 투자광고 규정 §4. Inline here (not the
              dashboard DisclaimerBanner component) because /features/* runs
              the landing shell, not the dashboard shell. */}
          <p
            className="mx-auto mt-8 max-w-3xl text-center font-serif italic"
            style={{
              fontSize: "12px",
              lineHeight: 1.7,
              color: "rgba(245,240,232,0.45)",
              letterSpacing: "0.01em",
            }}
          >
            PivoxQuant 는 투자자문업(자본시장법 §6②) 및 금융투자업 인가 업체가 아닙니다.
            본 페이지의 모든 정보는 교육·연구 목적의 관찰이며 특정 종목의 매수·매도·보유를
            권유하지 않습니다. 모든 투자 결정과 그 결과에 대한 책임은 이용자 본인에게 있습니다.
            <br />
            <span style={{ color: "rgba(245,240,232,0.55)" }}>
              PivoxQuant is not a licensed investment adviser. All information on this page is
              observational and educational only; it does not constitute a recommendation to buy,
              sell, or hold any security. Investment decisions and their consequences are your own.
            </span>
          </p>
        </div>
      </footer>
    </div>
  );
}
