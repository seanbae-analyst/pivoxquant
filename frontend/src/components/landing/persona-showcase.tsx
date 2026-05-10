"use client";

/**
 * PersonaShowcase — 8 investor personas (Identity Layer).
 * -----------------------------------------------------------------------
 * Grid of 8 cards. Each: persona name (EN + KR), one-line identity,
 * sample report CTA. Palette-safe (Vantablack + Ivory + Bronze).
 * Mobile: 1 col. Tablet: 2 col. Desktop: 4 col.
 */

import Link from "next/link";
import { motion, useReducedMotion } from "motion/react";
import type { Variants } from "motion/react";

const fadeUp: Variants = {
  hidden: { opacity: 0, y: 18 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.6, ease: [0.16, 1, 0.3, 1] },
  },
};
const stagger: Variants = {
  hidden: {},
  visible: { transition: { staggerChildren: 0.06 } },
};

type Persona = {
  key: string;
  en: string;
  kr: string;
  identity: string;
  ko: string;
  hue: "ivory" | "bronze";
};

const PERSONAS: readonly Persona[] = [
  {
    key: "growth",
    en: "Growth",
    kr: "성장형",
    identity: "High-beta compounders. Narrative-led.",
    ko: "미래 현금흐름에 베팅한다.",
    hue: "ivory",
  },
  {
    key: "value",
    en: "Value",
    kr: "가치형",
    identity: "Margin of safety. Balance-sheet first.",
    ko: "싼 값에 산다. 느리게 부자가 된다.",
    hue: "bronze",
  },
  {
    key: "balanced",
    en: "Balanced",
    kr: "균형형",
    identity: "Classic 60/40. Ballast over bravery.",
    ko: "평온한 복리.",
    hue: "ivory",
  },
  {
    key: "income",
    en: "Income",
    kr: "인컴형",
    identity: "Dividends, coupons, cash yield.",
    ko: "월세 같은 배당.",
    hue: "bronze",
  },
  {
    key: "quant",
    en: "Quant",
    kr: "퀀트형",
    identity: "Factor-driven. Rules over instinct.",
    ko: "숫자가 결정한다.",
    hue: "ivory",
  },
  {
    key: "speculator",
    en: "Speculator",
    kr: "투기형",
    identity: "High conviction. Concentrated bets.",
    ko: "크게 걸고 크게 간다.",
    hue: "bronze",
  },
  {
    key: "daytrader",
    en: "Daytrader",
    kr: "단타형",
    identity: "Intraday. Tape-reader.",
    ko: "하루 안에 매듭.",
    hue: "ivory",
  },
  {
    key: "beginner",
    en: "Beginner CFO",
    kr: "입문 CFO",
    identity: "First year. Learning the ropes.",
    ko: "처음 내 돈을 굴려본다.",
    hue: "bronze",
  },
] as const;

export function PersonaShowcase() {
  const reduce = useReducedMotion();

  return (
    <section
      id="pq-personas"
      className="relative py-24 md:py-32"
      style={{ backgroundColor: "#050505", color: "var(--pq-ivory)" }}
    >
      <div className="mx-auto max-w-7xl px-5 sm:px-8 lg:px-10">
        <motion.div
          initial={reduce ? undefined : "hidden"}
          whileInView={reduce ? undefined : "visible"}
          viewport={{ once: true, margin: "-80px" }}
          variants={fadeUp}
          className="mb-10 inline-flex items-center gap-2.5"
        >
          <span
            aria-hidden
            className="h-px w-7"
            style={{ backgroundColor: "rgba(139, 111, 71, 0.7)" }}
          />
          <span
            className="font-serif text-[11px] uppercase"
            style={{ letterSpacing: "0.22em", color: "var(--pq-bronze)" }}
          >
            Eight Investor Personas
          </span>
        </motion.div>

        <motion.h2
          initial={reduce ? undefined : "hidden"}
          whileInView={reduce ? undefined : "visible"}
          viewport={{ once: true, margin: "-80px" }}
          variants={fadeUp}
          className="pq-silver-matte font-serif mb-6"
          style={{
            fontSize: "clamp(1.875rem, 3.6vw, 2.75rem)",
            lineHeight: 1.08,
            letterSpacing: "-0.02em",
            fontWeight: 500,
          }}
        >
          A CFO that speaks
          <br />
          your investor language.
        </motion.h2>

        <motion.p
          initial={reduce ? undefined : "hidden"}
          whileInView={reduce ? undefined : "visible"}
          viewport={{ once: true, margin: "-80px" }}
          variants={fadeUp}
          className="font-serif mb-16 max-w-xl"
          style={{
            fontSize: "clamp(15px, 1.3vw, 17px)",
            lineHeight: 1.65,
            color: "rgba(245, 240, 232, 0.65)",
          }}
        >
          온보딩 20문항이 당신을 8가지 투자자 유형 중 하나로 분류합니다.
          Drift가 감지되면 페르소나는 자동으로 재조정됩니다.
        </motion.p>

        <motion.div
          initial={reduce ? undefined : "hidden"}
          whileInView={reduce ? undefined : "visible"}
          viewport={{ once: true, margin: "-60px" }}
          variants={stagger}
          className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-4"
        >
          {PERSONAS.map((p) => (
            <motion.article
              key={p.key}
              variants={fadeUp}
              className="group relative flex flex-col justify-between overflow-hidden rounded-sm p-6 md:p-7 transition-transform duration-300 hover:-translate-y-1"
              style={{
                minHeight: 230,
                backgroundColor: "#0D0D0D",
                border: "0.5px solid rgba(139,111,71,0.28)",
                boxShadow: "0 1px 0 0 var(--pq-ivory-line-ghost) inset",
              }}
            >
              {/* Hue bar */}
              <div
                aria-hidden
                className="absolute left-0 top-0 h-full w-[2px]"
                style={{
                  backgroundColor:
                    p.hue === "bronze"
                      ? "rgba(184,149,106,0.7)"
                      : "rgba(245,240,232,0.55)",
                }}
              />

              <div>
                <div className="mb-3 flex items-baseline gap-2.5">
                  <span
                    className="font-mono text-[12px] uppercase tabular-nums"
                    style={{
                      letterSpacing: "0.22em",
                      color: "var(--pq-bronze)",
                    }}
                  >
                    {p.key.slice(0, 2).toUpperCase()}
                  </span>
                  <span
                    className="font-serif text-[12px] italic"
                    style={{ color: "rgba(245,240,232,0.45)" }}
                  >
                    {p.kr}
                  </span>
                </div>
                <h3
                  className="font-serif mb-3"
                  style={{
                    fontSize: "24px",
                    lineHeight: 1.12,
                    color: "var(--pq-ivory)",
                    fontWeight: 500,
                    letterSpacing: "-0.01em",
                  }}
                >
                  {p.en}
                </h3>
                <p
                  className="font-serif mb-2"
                  style={{
                    fontSize: "14px",
                    lineHeight: 1.55,
                    color: "rgba(245,240,232,0.72)",
                  }}
                >
                  {p.identity}
                </p>
                <p
                  className="font-serif italic"
                  style={{
                    fontSize: "12px",
                    lineHeight: 1.5,
                    color: "rgba(139,111,71,0.75)",
                  }}
                >
                  {p.ko}
                </p>
              </div>

              <Link
                href={`/sample-reports/weekly-memo`}
                className="mt-6 inline-flex items-center gap-1.5 self-start font-serif text-[12px] italic"
                style={{
                  letterSpacing: "0.02em",
                  color: "var(--pq-bronze-light, #B8956A)",
                  borderBottom: "0.5px solid rgba(184,149,106,0.4)",
                  paddingBottom: 2,
                }}
              >
                View sample report →
              </Link>
            </motion.article>
          ))}
        </motion.div>
      </div>
    </section>
  );
}

export default PersonaShowcase;
