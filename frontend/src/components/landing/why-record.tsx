"use client";

/**
 * WhyRecord — three public figures that say why a record is worth keeping.
 * ----------------------------------------------------------------------
 * Sits between the Hero and the loop (<ThreeSteps/>): the loop says what the
 * tool does, this says why anyone would want it. Every number is a sourced,
 * observational statement copied from a public release (checked 2026-10-22):
 *
 *   finance   43.4 / 100 '평소 재무상황 점검' (20대 33.2, 2022년 55.8)
 *             금융감독원·한국은행 「2024 전국민 금융이해력 조사」, 만 18~79세 2,400명.
 *             The score is the share answering 동의 이상 (1 point each).
 *   report    65.3% read no fund 운용보고서 they received ('23 57.7, '24 60.0);
 *             top reason "내용이 너무 많아서" 41.9%.
 *             한국금융소비자보호재단 「2025 펀드 투자자 조사」 보도자료 (2026-03-12).
 *   sells     shares above the purchase price were sold with more than twice
 *             the probability of shares below it — ~200,000 individual
 *             accounts, Mar–Oct 2020.
 *             자본시장연구원 연구보고서 22-02 「국내 개인투자자의 행태적 편의와 거래행태」.
 *
 * Claim limits (pinned by src/__tests__/landing-why-copy.test.ts):
 *   - No claim that keeping a record changes returns or behaviour — the deck
 *     says so outright. These are facts about the population, not promises.
 *   - The research term for the third figure is not attached to the user's
 *     own trades: services/behavior/profit_loss_mirror.py keeps that framing
 *     out of the mirror on purpose. The card describes what the mirror shows
 *     (hold days and return of profit-taking vs loss-taking sells) and that it
 *     gives no verdict.
 *   - No public survey asks Korean investors whether they keep a trading
 *     journal (searched 2026-10-22: 금투협 · 금감원 · 한국은행 · 통계청 ·
 *     자본시장연구원 · 금융소비자보호재단). Do not invent a figure for it.
 *
 * Palette and type follow <ThreeSteps/>: Vantablack + Bronze + Ivory, no italic.
 */

import { motion, useReducedMotion } from "motion/react";

import { Eyebrow } from "./eyebrow";
import { fadeUp, stagger } from "@/lib/motion";
import { useT } from "@/lib/locale";

type Fact = {
  /** i18n key prefix under `landing.why` (finance · report · sells). */
  key: string;
  /** The screen the product line points at, so the claim stays checkable. */
  route: string;
};

const FACTS: readonly Fact[] = [
  { key: "finance", route: "/journal" },
  { key: "report", route: "/mirror" },
  { key: "sells", route: "/journal" },
] as const;

export default function WhyRecord() {
  const t = useT();
  const reduce = useReducedMotion();

  return (
    <section
      id="why-record"
      aria-labelledby="pq-why-heading"
      className="relative py-24 md:py-32"
      style={{ backgroundColor: "#050505", color: "var(--pq-ivory)" }}
    >
      <div className="mx-auto max-w-7xl px-5 sm:px-8 lg:px-10">
        <motion.div
          initial={reduce ? undefined : "hidden"}
          whileInView={reduce ? undefined : "visible"}
          viewport={{ once: true, margin: "-80px" }}
          variants={fadeUp}
          className="mb-14 max-w-2xl md:mb-16"
        >
          <Eyebrow className="mb-6">{t("landing.why.eyebrow")}</Eyebrow>
          <h2
            id="pq-why-heading"
            className="pq-silver-matte font-serif"
            style={{
              fontSize: "clamp(1.875rem, 3.6vw, 2.75rem)",
              lineHeight: 1.08,
              letterSpacing: "-0.02em",
              fontWeight: 500,
              marginBottom: 24,
            }}
          >
            {t("landing.why.heading")}
          </h2>
          <p
            className="font-serif"
            style={{
              fontSize: "var(--pq-text-deck)",
              lineHeight: 1.65,
              color: "var(--pq-ivory-mid)",
              maxWidth: 560,
            }}
          >
            {t("landing.why.deck")}
          </p>
        </motion.div>

        <motion.ul
          initial={reduce ? undefined : "hidden"}
          whileInView={reduce ? undefined : "visible"}
          viewport={{ once: true, margin: "-60px" }}
          variants={stagger}
          className="grid grid-cols-1 gap-px md:grid-cols-3"
          style={{ backgroundColor: "rgba(184,149,106,0.18)" }}
        >
          {FACTS.map((f) => (
            <motion.li
              key={f.key}
              variants={fadeUp}
              className="flex flex-col p-7 md:p-8 lg:p-9"
              style={{ backgroundColor: "#050505" }}
            >
              <p
                className="font-serif tabular-nums"
                style={{
                  color: "var(--pq-bronze)",
                  fontSize: "clamp(2.25rem, 4.2vw, 3.25rem)",
                  lineHeight: 1,
                  letterSpacing: "-0.03em",
                  fontWeight: 500,
                  marginBottom: 14,
                }}
              >
                {t(`landing.why.${f.key}Figure`)}
              </p>
              <h3
                className="mb-4 font-serif"
                style={{
                  color: "var(--pq-ivory)",
                  fontSize: "var(--pq-text-body)",
                  fontWeight: 500,
                  lineHeight: 1.45,
                }}
              >
                {t(`landing.why.${f.key}Label`)}
              </h3>
              <p
                className="mb-4 font-serif"
                style={{
                  color: "rgba(245,240,232,0.74)",
                  fontSize: "var(--pq-text-body-sm)",
                  lineHeight: 1.7,
                }}
              >
                {t(`landing.why.${f.key}Body`)}
              </p>
              {/* The source is part of the claim, not a footnote. */}
              <p
                className="mb-7 flex-1 font-serif"
                style={{
                  color: "var(--pq-ivory-faint)",
                  fontSize: "var(--pq-text-eyebrow)",
                  lineHeight: 1.6,
                }}
              >
                {t(`landing.why.${f.key}Source`)}
              </p>
              <div
                className="flex items-baseline gap-3"
                style={{ borderTop: "0.5pt solid var(--pq-ivory-line)", paddingTop: 14 }}
              >
                <p
                  className="font-serif"
                  style={{
                    color: "var(--pq-ivory-mid)",
                    fontSize: "var(--pq-text-body-sm)",
                    lineHeight: 1.6,
                  }}
                >
                  {t(`landing.why.${f.key}Here`)}
                </p>
                <span
                  className="ml-auto shrink-0 font-mono"
                  style={{
                    color: "var(--pq-ivory-faint)",
                    fontSize: "var(--pq-text-eyebrow)",
                    letterSpacing: "0.01em",
                  }}
                >
                  {f.route}
                </span>
              </div>
            </motion.li>
          ))}
        </motion.ul>

        <motion.p
          initial={reduce ? undefined : "hidden"}
          whileInView={reduce ? undefined : "visible"}
          viewport={{ once: true, margin: "-40px" }}
          variants={fadeUp}
          className="mt-8 max-w-2xl font-serif"
          style={{
            color: "var(--pq-ivory-faint)",
            fontSize: "var(--pq-text-eyebrow)",
            lineHeight: 1.6,
          }}
        >
          {t("landing.why.note")}
        </motion.p>
      </div>
    </section>
  );
}
